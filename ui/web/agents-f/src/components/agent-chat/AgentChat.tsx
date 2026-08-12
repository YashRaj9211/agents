import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { AdkEvent, AdkSession } from '../../services/adkClient';
import {
  createSession,
  listSessions,
  runSse,
} from '../../services/adkClient';
import { SessionSidebar } from './SessionSidebar';
import { EventInspector } from './EventInspector';

// ─── Message model ─────────────────────────────────────────────────────────────

/**
 * A "ChatMessage" groups one or more ADK events into a single displayed row.
 * We merge consecutive partial text events from the same author into one bubble.
 */
interface ChatMessage {
  id: string;
  author: string;
  /** 'user' | 'agent' | 'tool_call' | 'tool_result' | 'transfer' | 'error' */
  role: string;
  text: string;
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  toolResult?: unknown;
  transferTo?: string;
  isStreaming?: boolean;
  timestamp: number;
}

const DEFAULT_USER_ID = 'user_1';

// ─── Component helpers ─────────────────────────────────────────────────────────

const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <path d="M15.75 9L2.25 2.25 5.625 9l-3.375 6.75L15.75 9z" fill="currentColor" />
  </svg>
);

const InspectorToggleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <rect x="1" y="3" width="16" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
    <path d="M11 3v12" stroke="currentColor" strokeWidth="1.5" />
    <path d="M13 7h2M13 11h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const SpinnerIcon = () => (
  <div className="w-4 h-4 border-2 border-[#FA5D19] border-t-transparent rounded-full animate-spin" />
);

function deriveMessages(events: AdkEvent[]): ChatMessage[] {
  const msgs: ChatMessage[] = [];

  for (const evt of events) {
    const ts = evt.timestamp ?? Date.now() / 1000;

    // Agent transfer
    if (evt._type === 'agent_transfer' && evt.actions?.transfer_to_agent) {
      msgs.push({
        id: evt.id ?? `transfer-${ts}`,
        author: evt.author,
        role: 'transfer',
        text: `Delegating to ${evt.actions.transfer_to_agent}`,
        transferTo: evt.actions.transfer_to_agent as string,
        timestamp: ts,
      });
      continue;
    }

    // Error
    if (evt._type === 'error') {
      msgs.push({
        id: evt.id ?? `err-${ts}`,
        author: evt.author,
        role: 'error',
        text: evt.error_message ?? 'Unknown error',
        timestamp: ts,
      });
      continue;
    }

    const parts = evt.content?.parts ?? [];

    // Tool call
    const toolCallPart = parts.find((p) => p.functionCall);
    if (toolCallPart?.functionCall) {
      msgs.push({
        id: evt.id ?? `tc-${ts}`,
        author: evt.author,
        role: 'tool_call',
        text: toolCallPart.functionCall.name,
        toolName: toolCallPart.functionCall.name,
        toolArgs: toolCallPart.functionCall.args,
        timestamp: ts,
      });
      continue;
    }

    // Tool result
    const toolResultPart = parts.find((p) => p.functionResponse);
    if (toolResultPart?.functionResponse) {
      msgs.push({
        id: evt.id ?? `tr-${ts}`,
        author: evt.author,
        role: 'tool_result',
        text: toolResultPart.functionResponse.name,
        toolName: toolResultPart.functionResponse.name,
        toolResult: toolResultPart.functionResponse.response,
        timestamp: ts,
      });
      continue;
    }

    // Text
    const textParts = parts.filter((p) => p.text);
    if (textParts.length > 0) {
      const text = textParts.map((p) => p.text ?? '').join('');
      if (!text.trim()) continue;

      const isUser = evt.author === 'user';

      // Merge consecutive streaming text from same author
      const last = msgs[msgs.length - 1];
      if (
        !isUser &&
        last &&
        last.role === 'agent' &&
        last.author === evt.author &&
        last.isStreaming
      ) {
        last.text += text;
        last.isStreaming = evt.partial ?? false;
        continue;
      }

      msgs.push({
        id: evt.id ?? `txt-${ts}`,
        author: evt.author,
        role: isUser ? 'user' : 'agent',
        text,
        isStreaming: evt.partial ?? false,
        timestamp: ts,
      });
    }
  }

  return msgs;
}

// ─── Bubble components ─────────────────────────────────────────────────────────

const ToolCallCard: React.FC<{ msg: ChatMessage }> = ({ msg }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="flex justify-start mb-2">
      <div className="max-w-[80%] w-fit">
        <p className="typography-micro text-[#9CA3AF] mb-1 ml-1">{msg.author}</p>
        <div className="border border-[#FED7AA] bg-[#FFF7ED] rounded-xl overflow-hidden">
          <button
            onClick={() => setExpanded((p) => !p)}
            className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[#FEF3C7] transition-colors"
          >
            <span className="w-5 h-5 flex items-center justify-center rounded bg-[#FA5D19] shrink-0">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 5h6M5 2l3 3-3 3" stroke="white" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
            </span>
            <span className="typography-label-sm text-[#C2410C] flex-1">
              {msg.toolName}
            </span>
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              className={`transition-transform text-[#C2410C] ${expanded ? 'rotate-90' : ''}`}
            >
              <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          {expanded && (
            <pre className="px-3 pb-3 text-[10px] font-mono text-[#92400E] whitespace-pre-wrap break-all border-t border-[#FED7AA] pt-2">
              {JSON.stringify(msg.toolArgs, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
};

const ToolResultCard: React.FC<{ msg: ChatMessage }> = ({ msg }) => {
  const [expanded, setExpanded] = useState(false);
  const resultStr =
    typeof msg.toolResult === 'string'
      ? msg.toolResult
      : JSON.stringify(msg.toolResult, null, 2);
  const preview = resultStr.slice(0, 120);

  return (
    <div className="flex justify-start mb-2">
      <div className="max-w-[80%] w-fit">
        <div className="border border-[#BBF7D0] bg-[#F0FDF4] rounded-xl overflow-hidden">
          <button
            onClick={() => setExpanded((p) => !p)}
            className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[#DCFCE7] transition-colors"
          >
            <span className="w-5 h-5 flex items-center justify-center rounded bg-[#16A34A] shrink-0">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 5l2.5 2.5L8 2" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </span>
            <span className="typography-label-sm text-[#15803D] flex-1">
              ✓ {msg.toolName}
            </span>
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              className={`transition-transform text-[#15803D] ${expanded ? 'rotate-90' : ''}`}
            >
              <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          {expanded ? (
            <pre className="px-3 pb-3 text-[10px] font-mono text-[#14532D] whitespace-pre-wrap break-all border-t border-[#BBF7D0] pt-2 max-h-48 overflow-y-auto">
              {resultStr}
            </pre>
          ) : (
            <p className="px-3 pb-2 text-[10px] font-mono text-[#14532D] truncate border-t border-[#BBF7D0] pt-1">
              {preview}{resultStr.length > 120 ? '…' : ''}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

const TransferBadge: React.FC<{ msg: ChatMessage }> = ({ msg }) => (
  <div className="flex justify-center mb-3">
    <div className="flex items-center gap-2 bg-[#FAF5FF] border border-[#E9D5FF] rounded-full px-3 py-1">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <circle cx="3" cy="6" r="2" fill="#7E22CE" />
        <path d="M5 6h5M8 4l2 2-2 2" stroke="#7E22CE" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
      <span className="typography-micro text-[#7E22CE]">
        {msg.author} → {msg.transferTo}
      </span>
    </div>
  </div>
);

const ChatBubble: React.FC<{ msg: ChatMessage }> = ({ msg }) => {
  const isUser = msg.role === 'user';

  return (
    <div className={`flex mb-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[75%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        {!isUser && (
          <p className="typography-micro text-[#9CA3AF] ml-1">{msg.author}</p>
        )}
        <div
          className={`px-4 py-2.5 rounded-2xl typography-body-sm leading-relaxed whitespace-pre-wrap break-words ${
            isUser
              ? 'bg-[#FA5D19] text-white rounded-br-sm'
              : 'bg-white border border-[#E5E7EB] text-[#262626] rounded-bl-sm'
          }`}
        >
          {msg.text}
          {msg.isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-current opacity-70 animate-pulse ml-1 align-middle" />
          )}
        </div>
      </div>
    </div>
  );
};

const ErrorBubble: React.FC<{ msg: ChatMessage }> = ({ msg }) => (
  <div className="flex justify-start mb-3">
    <div className="max-w-[75%] bg-[#FEF2F2] border border-[#FECACA] rounded-xl px-4 py-2.5">
      <p className="typography-micro text-[#DC2626] font-bold mb-1">Error — {msg.author}</p>
      <p className="typography-body-sm text-[#DC2626]">{msg.text}</p>
    </div>
  </div>
);

// ─── Main AgentChat component ──────────────────────────────────────────────────

export const AgentChat: React.FC = () => {
  const [userId] = useState(DEFAULT_USER_ID);
  const [sessions, setSessions] = useState<AdkSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionLoading, setSessionLoading] = useState(false);

  const [events, setEvents] = useState<AdkEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputText, setInputText] = useState('');
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const streamAbortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // ── Load / create initial session ─────────────────────────────────────────

  const loadSessions = useCallback(async () => {
    setSessionLoading(true);
    try {
      const list = await listSessions(userId);
      setSessions(list.sort((a, b) => (b.last_update_time ?? 0) - (a.last_update_time ?? 0)));
    } catch (err) {
      console.warn('Could not list sessions:', err);
    } finally {
      setSessionLoading(false);
    }
  }, [userId]);

  const handleNewSession = useCallback(async () => {
    setSessionLoading(true);
    try {
      const session = await createSession(userId);
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setEvents([]);
    } catch (err) {
      console.error('Failed to create session:', err);
    } finally {
      setSessionLoading(false);
    }
  }, [userId]);

  const handleSelectSession = useCallback(async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setEvents([]); // Could load existing events here if needed
  }, []);

  // On mount: load sessions and auto-create one if none exist
  useEffect(() => {
    (async () => {
      setSessionLoading(true);
      try {
        const list = await listSessions(userId);
        const sorted = list.sort((a, b) => (b.last_update_time ?? 0) - (a.last_update_time ?? 0));
        setSessions(sorted);
        if (sorted.length > 0) {
          setActiveSessionId(sorted[0].id);
        } else {
          const session = await createSession(userId);
          setSessions([session]);
          setActiveSessionId(session.id);
        }
      } catch (err) {
        console.error('Init error:', err);
      } finally {
        setSessionLoading(false);
      }
    })();
  }, [userId]);

  // ── Auto-scroll ────────────────────────────────────────────────────────────

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  // ── Send message ───────────────────────────────────────────────────────────

  const handleSend = useCallback(() => {
    const text = inputText.trim();
    if (!text || !activeSessionId || isStreaming) return;

    // Add user event immediately for responsiveness
    const userEvent: AdkEvent = {
      id: `user-${Date.now()}`,
      author: 'user',
      timestamp: Date.now() / 1000,
      content: { role: 'user', parts: [{ text }] },
      _type: 'text',
    };
    setEvents((prev) => [...prev, userEvent]);
    setInputText('');
    setIsStreaming(true);

    // Cancel any previous stream
    streamAbortRef.current?.abort();

    streamAbortRef.current = runSse({
      userId,
      sessionId: activeSessionId,
      message: text,
      onEvent: (evt) => {
        // Skip echoed user events from the server
        if (evt.author === 'user') return;
        setEvents((prev) => [...prev, evt]);
      },
      onDone: () => {
        setIsStreaming(false);
        loadSessions(); // Refresh session list to update timestamps
      },
      onError: (err) => {
        console.error('SSE error:', err);
        setIsStreaming(false);
        setEvents((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            author: 'system',
            timestamp: Date.now() / 1000,
            error_message: err.message,
            _type: 'error',
          } as AdkEvent,
        ]);
      },
    });
  }, [inputText, activeSessionId, isStreaming, userId, loadSessions]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Derive display messages ────────────────────────────────────────────────

  const messages = deriveMessages(events);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full overflow-hidden" style={{ height: 'calc(100vh - 68px)' }}>
      {/* Session Sidebar */}
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        userId={userId}
        isLoading={sessionLoading}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />

      {/* Main chat area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#E5E7EB] bg-white shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#22C55E] animate-pulse" />
            <span className="typography-label-sm text-[#374151]">root_agent</span>
            {activeSessionId && (
              <span className="typography-micro text-[#9CA3AF] bg-[#F3F4F6] px-2 py-0.5 rounded-full">
                {activeSessionId.slice(0, 12)}…
              </span>
            )}
          </div>
          <button
            id="toggle-inspector-btn"
            onClick={() => setInspectorOpen((p) => !p)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg typography-label-sm transition-colors ${
              inspectorOpen
                ? 'bg-[#FA5D19]/10 text-[#FA5D19]'
                : 'text-[#6B7280] hover:bg-[#F3F4F6]'
            }`}
            title="Toggle Event Inspector"
          >
            <InspectorToggleIcon />
            Events {events.length > 0 && `(${events.length})`}
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 bg-[#F9F9F9]">
          {messages.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
              <div className="w-12 h-12 rounded-2xl bg-[#FA5D19] flex items-center justify-center text-white text-2xl font-bold shadow-lg">
                A
              </div>
              <div>
                <p className="typography-headline-sm text-[#262626]">Agent Explorer</p>
                <p className="typography-body-sm text-[#9CA3AF] mt-1">
                  Chat with your root_agent and all its sub-agents.
                  <br />
                  All events, tool calls and transfers appear in real-time.
                </p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center mt-2">
                {['Search for jobs in Bangalore', 'Scrape https://example.com', 'What time is it?'].map(
                  (s) => (
                    <button
                      key={s}
                      onClick={() => setInputText(s)}
                      className="px-3 py-1.5 bg-white border border-[#E5E7EB] rounded-full typography-body-sm text-[#374151] hover:border-[#FA5D19] hover:text-[#FA5D19] transition-colors"
                    >
                      {s}
                    </button>
                  ),
                )}
              </div>
            </div>
          )}

          {messages.map((msg) => {
            if (msg.role === 'transfer') return <TransferBadge key={msg.id} msg={msg} />;
            if (msg.role === 'error') return <ErrorBubble key={msg.id} msg={msg} />;
            if (msg.role === 'tool_call') return <ToolCallCard key={msg.id} msg={msg} />;
            if (msg.role === 'tool_result') return <ToolResultCard key={msg.id} msg={msg} />;
            return <ChatBubble key={msg.id} msg={msg} />;
          })}

          {isStreaming && messages[messages.length - 1]?.role !== 'agent' && (
            <div className="flex justify-start mb-3">
              <div className="bg-white border border-[#E5E7EB] rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2">
                <SpinnerIcon />
                <span className="typography-body-sm text-[#9CA3AF]">Thinking…</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="shrink-0 px-4 py-3 border-t border-[#E5E7EB] bg-white">
          {!activeSessionId && (
            <p className="typography-body-sm text-[#DC2626] text-center mb-2">
              Could not connect to ADK server at http://localhost:8000. Is the server running?
            </p>
          )}
          <div className="flex items-end gap-2 bg-[#F9F9F9] border border-[#E5E7EB] rounded-2xl px-4 py-2 focus-within:border-[#FA5D19] focus-within:ring-2 focus-within:ring-[#FA5D19]/20 transition-all">
            <textarea
              id="chat-input"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={!activeSessionId || isStreaming}
              placeholder={
                !activeSessionId
                  ? 'Waiting for session…'
                  : isStreaming
                  ? 'Agent is responding…'
                  : 'Message root_agent… (Enter to send, Shift+Enter for newline)'
              }
              className="flex-1 bg-transparent resize-none outline-none typography-body-sm text-[#262626] placeholder-[#9CA3AF] max-h-32 leading-relaxed"
              style={{ minHeight: '24px' }}
            />
            <button
              id="send-btn"
              onClick={handleSend}
              disabled={!inputText.trim() || !activeSessionId || isStreaming}
              className="w-9 h-9 flex items-center justify-center rounded-xl bg-[#FA5D19] text-white hover:bg-[#FF6A2A] transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
            >
              {isStreaming ? <SpinnerIcon /> : <SendIcon />}
            </button>
          </div>
          <p className="typography-micro text-[#9CA3AF] text-center mt-1.5">
            Shift + Enter for new line · Enter to send
          </p>
        </div>
      </div>

      {/* Event Inspector panel */}
      <EventInspector
        events={events}
        isOpen={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
      />
    </div>
  );
};

export default AgentChat;
