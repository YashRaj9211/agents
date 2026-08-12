/**
 * ADK API Client
 * Wraps the `adk api_server` endpoints for session management and SSE streaming.
 * Base URL: http://localhost:8000
 */

export const ADK_BASE_URL = 'http://localhost:8000';
export const APP_NAME = 'root_agent';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AdkEventPart {
  text?: string;
  functionCall?: {
    id?: string;
    name: string;
    args: Record<string, unknown>;
  };
  functionResponse?: {
    id?: string;
    name: string;
    response: Record<string, unknown>;
  };
}

export interface AdkEvent {
  id?: string;
  invocation_id?: string;
  author: string;
  timestamp?: number;
  partial?: boolean;
  content?: {
    role?: string;
    parts: AdkEventPart[];
  };
  actions?: {
    transfer_to_agent?: string;
    escalate?: boolean;
    skip_summarization?: boolean;
    state_delta?: Record<string, unknown>;
  };
  error_code?: string;
  error_message?: string;
  // Synthetic field set by the client to classify event for display
  _type?: 'text' | 'tool_call' | 'tool_result' | 'agent_transfer' | 'error' | 'status';
}

export interface AdkSession {
  id: string;
  app_name: string;
  user_id: string;
  state?: Record<string, unknown>;
  events?: AdkEvent[];
  last_update_time?: number;
}

// ─── Session management ───────────────────────────────────────────────────────

/**
 * Create a new session for a user. Returns the created session object.
 */
export async function createSession(userId: string): Promise<AdkSession> {
  const res = await fetch(
    `${ADK_BASE_URL}/apps/${APP_NAME}/users/${encodeURIComponent(userId)}/sessions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    },
  );
  if (!res.ok) {
    throw new Error(`Failed to create session: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * List all sessions for a user.
 */
export async function listSessions(userId: string): Promise<AdkSession[]> {
  const res = await fetch(
    `${ADK_BASE_URL}/apps/${APP_NAME}/users/${encodeURIComponent(userId)}/sessions`,
  );
  if (!res.ok) {
    throw new Error(`Failed to list sessions: ${res.status} ${res.statusText}`);
  }
  const data = await res.json();
  // The api_server returns { sessions: [...] } or just an array depending on version
  if (Array.isArray(data)) return data;
  if (data.sessions) return data.sessions;
  return [];
}

/**
 * Get a single session by ID including its event history.
 */
export async function getSession(userId: string, sessionId: string): Promise<AdkSession> {
  const res = await fetch(
    `${ADK_BASE_URL}/apps/${APP_NAME}/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to get session: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ─── SSE Streaming ────────────────────────────────────────────────────────────

export interface RunSseOptions {
  userId: string;
  sessionId: string;
  message: string;
  onEvent: (event: AdkEvent) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

/**
 * Sends a user message to the agent via /run_sse and streams events back.
 * Returns an AbortController so the caller can cancel the stream.
 */
export function runSse({
  userId,
  sessionId,
  message,
  onEvent,
  onDone,
  onError,
}: RunSseOptions): AbortController {
  const controller = new AbortController();

  const payload = {
    app_name: APP_NAME,
    user_id: userId,
    session_id: sessionId,
    new_message: {
      role: 'user',
      parts: [{ text: message }],
    },
    streaming: true,
  };

  (async () => {
    try {
      const res = await fetch(`${ADK_BASE_URL}/run_sse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`SSE request failed: ${res.status} ${res.statusText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE lines look like:  data: {...}\n\n
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(':')) continue; // heartbeat/comment

          if (trimmed.startsWith('data:')) {
            const raw = trimmed.slice(5).trim();
            if (raw === '[DONE]') continue;
            try {
              const evt: AdkEvent = JSON.parse(raw);
              // Classify event type for easy rendering
              evt._type = classifyEvent(evt);
              onEvent(evt);
            } catch {
              // Malformed JSON — ignore
            }
          }
        }
      }

      onDone();
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return; // User cancelled
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  })();

  return controller;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function classifyEvent(evt: AdkEvent): AdkEvent['_type'] {
  if (evt.error_code || evt.error_message) return 'error';
  if (evt.actions?.transfer_to_agent) return 'agent_transfer';

  const parts = evt.content?.parts ?? [];
  if (parts.some((p) => p.functionCall)) return 'tool_call';
  if (parts.some((p) => p.functionResponse)) return 'tool_result';
  if (parts.some((p) => p.text)) return 'text';

  return 'status';
}
