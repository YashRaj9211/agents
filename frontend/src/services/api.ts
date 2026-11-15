export interface AgentInfo {
  id: string;
  name: string;
  description: string;
}

export type TimelineEventType =
  | 'agent_transfer'
  | 'tool_call'
  | 'tool_result'
  | 'thought'
  | 'info'
  | 'human_input';

export interface TimelineEventItem {
  id: string;
  type: TimelineEventType;
  title: string;
  description?: string;
  status: 'running' | 'completed' | 'failed';
  timestamp: string;
  /** One-line rendering of what actually ran ("git status", "/tmp/report.pdf"). */
  detail?: string;
  /** Truncated tool result, shown when a step is expanded. */
  output?: string;
  /** Raw tool name, so the panel can pick an icon without parsing the title. */
  toolName?: string;
  /** Stable identity for merging live steps with persisted timeline rows. */
  stepKey?: string;
  /** Wall-clock duration, once the step has settled. */
  durationMs?: number;
  /** Links a human-input step back to the question that answers it. */
  questionId?: string;
}

/** Shapes a `human_input_request` can take. */
export type HumanInputKind = 'confirm' | 'choice' | 'multi_choice' | 'text';

export interface HumanInputOption {
  label: string;
  value: string;
  description?: string;
}

/** A question an agent is currently blocked on. */
export interface HumanInputRequest {
  question_id: string;
  kind: HumanInputKind;
  question: string;
  options?: HumanInputOption[];
  run_id?: string;
  agent_id?: string;
  created_at?: number;
}

/** The answer value posted back, narrowed per question kind. */
export type HumanInputAnswer = boolean | string | string[];

export interface StreamEventPayload {
  type:
    | 'start'
    | 'attach'
    | 'chunk'
    | 'thought'
    | 'agent_transfer'
    | 'tool_call'
    | 'tool_result'
    | 'agent_spawned'
    | 'agent_result'
    | 'peer_message'
    | 'run_status'
    | 'heartbeat'
    | 'human_input_request'
    | 'done'
    | 'cancelled'
    | 'error';
  agent_id?: string;
  from_agent?: string;
  to_agent?: string;
  tool?: string;
  status?: string;
  text?: string;
  final_output?: string;
  thought_process?: string;
  raw_text?: string;
  /** Emitted on the `start` event: the canonical backend session UUID. */
  session_id?: string;
  /** Emitted on the `start` event: the AgentRun id for this exchange. */
  run_id?: string;
  /** Monotonic position in the run's event buffer, used as the resume cursor. */
  seq?: number;
  /** How this run began: 'user' | 'peer' | 'spawn' | 'delegated'. */
  origin?: string;
  /** Attach frames: where the replay starts and whether the buffer was trimmed. */
  cursor?: number;
  truncated?: boolean;
  /** `agent_spawned`: the runs this run just fanned out to. */
  spawned?: Array<{ run_id: string; session_id: string; agent_id: string }>;
  /** `peer_message`: who spoke and how many messages were folded in. */
  from_session_id?: string;
  message_count?: number;
  cancel_reason?: string;
  failed?: boolean;
  busy?: boolean;
  capacity?: boolean;
  error?: string;
  /** Steps panel: the arguments a tool was called with. */
  args?: Record<string, unknown>;
  /** Steps panel: pre-rendered one-line detail for the tool call. */
  detail?: string;
  /** Steps panel: truncated tool output. */
  output?: string;
  /** HITL: the pending question this run is blocked on. */
  question_id?: string;
  kind?: HumanInputKind;
  question?: string;
  options?: HumanInputOption[];
}

export interface ChatResponsePayload {
  response: string;
  thought_process?: string;
  agent_id: string;
  session_id: string;
  tool_calls: {
    tool: string;
    status: 'running' | 'completed' | 'failed';
    output?: string;
  }[];
}

/**
 * Resolves the backend origin.
 *
 * - `VITE_BACKEND_URL` set  -> use it verbatim (cross-origin / deployed API).
 * - otherwise               -> use a same-origin relative prefix, so requests go to
 *                              `/api/...` on whatever host served the app. In dev the
 *                              Vite proxy (vite.config.ts) forwards `/api` to FastAPI;
 *                              in production nginx.conf reverse-proxies `/api` to
 *                              `backend:8000`. This removes the previously hardcoded
 *                              `http://127.0.0.1:8000`, which broke whenever the
 *                              backend did not happen to own that exact port.
 */
const BACKEND_URL = ((import.meta.env.VITE_BACKEND_URL as string | undefined) || '').replace(/\/+$/, '');

/** Builds an absolute-or-relative URL against the configured backend origin. */
function apiUrl(path: string): string {
  return `${BACKEND_URL}${path}`;
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(apiUrl('/api/health'));
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchAgentList(): Promise<AgentInfo[]> {
  try {
    const res = await fetch(apiUrl('/api/agents'));
    if (!res.ok) throw new Error('Failed to fetch agents');
    return await res.json();
  } catch (err) {
    console.warn('Backend not reachable, using fallback:', err);
    return [
      { id: 'root_agent', name: 'Root Orchestrator', description: 'Central coordinator' },
      { id: 'browser_agent', name: 'Browser Agent', description: 'Playwright automation' },
      { id: 'cli_agent', name: 'CLI Agent', description: 'Terminal & commands' },
      { id: 'scheduler_agent', name: 'Scheduler Agent', description: 'Timers and cron jobs' },
      { id: 'job_assist_agent', name: 'Job Assist', description: 'Resume & applications' },
      { id: 'firecrawl_agent', name: 'Firecrawl Agent', description: 'Web scraping & crawling' },
    ];
  }
}

/**
 * Reads an SSE response body and forwards every decoded payload.
 *
 * Shared by the initial `POST /api/chat/stream` call and by re-attaching to a
 * run with `GET /api/runs/{id}/stream`, so both paths decode frames identically.
 * A frame may carry multiple `data:` lines per the SSE spec; the backend emits
 * one, but joining them keeps this tolerant of either shape.
 */
export async function consumeSse(
  response: Response,
  onEvent?: (event: StreamEventPayload) => void,
  signal?: AbortSignal
): Promise<void> {
  if (!response.ok || !response.body) {
    throw new Error(`Failed to establish SSE stream (HTTP ${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  const handleFrame = (frame: string) => {
    const dataLines = frame
      .split(/\r?\n/)
      .filter((l) => l.startsWith('data:'))
      .map((l) => l.replace(/^data:\s?/, ''));

    if (dataLines.length === 0) return;

    try {
      const parsed: StreamEventPayload = JSON.parse(dataLines.join('\n'));
      if (onEvent) onEvent(parsed);
    } catch (e) {
      console.warn('Error parsing SSE event:', e, frame);
    }
  };

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      // Normalise CRLF so frames split on either line ending.
      buffer = buffer.replace(/\r\n/g, '\n');

      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';

      for (const frame of frames) handleFrame(frame);
    }

    // Flush a trailing frame that arrived without a terminating blank line.
    if (buffer.trim()) handleFrame(buffer);
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // The stream is already gone; nothing to release.
    }
  }
}

/**
 * Stream chat events via Server-Sent Events (SSE).
 *
 * The backend run outlives this request, so aborting the signal (or navigating
 * away) only detaches this viewer -- the agent keeps working.
 */
export async function streamChatMessage(
  message: string,
  agentId: string = 'root_agent',
  sessionId?: string,
  onEvent?: (event: StreamEventPayload) => void,
  artifactIds?: string[],
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(apiUrl('/api/chat/stream'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    signal,
    body: JSON.stringify({
      message,
      agent_id: agentId,
      session_id: sessionId,
      artifact_ids: artifactIds || [],
    }),
  });

  await consumeSse(response, onEvent, signal);
}

/**
 * Attaches to a run that is already executing, replaying buffered events from
 * `cursor` and then live-tailing. Used when the user returns to a running
 * session (including after a full page reload).
 */
export async function streamRunEvents(
  runId: string,
  cursor: number,
  onEvent?: (event: StreamEventPayload) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(apiUrl(`/api/runs/${encodeURIComponent(runId)}/stream?cursor=${cursor}`), {
    method: 'GET',
    headers: { Accept: 'text/event-stream' },
    signal,
  });
  await consumeSse(response, onEvent, signal);
}

export interface ApiRunItem {
  run_id: string;
  session_id?: string;
  session_title?: string;
  agent_id: string;
  status: string;
  origin?: string;
  parent_run_id?: string;
  started_at?: string;
  finished_at?: string;
  elapsed_ms?: number;
  live: boolean;
  error?: string;
}

export interface ApiRunList {
  runs: ApiRunItem[];
  active_count: number;
  limit: number;
}

/** Runs executing right now (or a status/session-filtered slice of the trace). */
export async function fetchActiveRuns(
  status: string = 'running',
  sessionId?: string
): Promise<ApiRunList> {
  try {
    const params = new URLSearchParams({ status });
    if (sessionId) params.append('session_id', sessionId);
    const res = await fetch(apiUrl(`/api/runs?${params.toString()}`));
    if (!res.ok) throw new Error('Failed to fetch runs');
    return await res.json();
  } catch (err) {
    console.warn('Runs endpoint unavailable, reporting no active runs:', err);
    return { runs: [], active_count: 0, limit: 0 };
  }
}

export interface CancelRunResult {
  success: boolean;
  run_id?: string;
  session_id?: string;
  status: string;
  cancelled?: boolean;
  cancelled_children?: string[];
  message?: string;
}

/** Stops a run; `cascade` also stops the runs it spawned. */
export async function cancelRun(runId: string, cascade: boolean = true): Promise<CancelRunResult> {
  const res = await fetch(
    apiUrl(`/api/runs/${encodeURIComponent(runId)}/cancel?cascade=${cascade ? 'true' : 'false'}`),
    { method: 'POST' }
  );
  if (!res.ok) throw new Error(`Failed to cancel run (HTTP ${res.status})`);
  return await res.json();
}

/** Stops whichever run a session currently has in flight. */
export async function cancelSessionRun(sessionId: string): Promise<CancelRunResult> {
  const res = await fetch(apiUrl(`/api/sessions/${encodeURIComponent(sessionId)}/cancel`), {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to cancel session run (HTTP ${res.status})`);
  return await res.json();
}

export interface PendingPeerMessage {
  id: string;
  content: string;
  kind: string;
  status: string;
  hop_count: number;
  expect_reply: boolean;
  sender_agent_id?: string;
  sender_session_id?: string;
  created_at?: string;
}

/** Peer-agent messages queued for a session that has not consumed them yet. */
export async function fetchPendingPeerMessages(sessionId: string): Promise<PendingPeerMessage[]> {
  try {
    const res = await fetch(apiUrl(`/api/sessions/${encodeURIComponent(sessionId)}/messages/pending`));
    if (!res.ok) throw new Error('Failed to fetch pending peer messages');
    const data = await res.json();
    return data.messages || [];
  } catch (err) {
    console.warn('Pending peer messages unavailable:', err);
    return [];
  }
}

export interface ApiSessionItem {
  id: string;
  title: string;
  preview: string;
  primary_agent_id?: string;
  status: string;
  last_message_at: string;
  created_at: string;
}

export interface ApiMessageItem {
  id: string;
  seq: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sender_agent_id?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface ApiSessionDetail {
  id: string;
  title: string;
  primary_agent_id?: string;
  status: string;
  created_at: string;
  messages: ApiMessageItem[];
}

export async function fetchSessions(): Promise<ApiSessionItem[]> {
  try {
    const res = await fetch(apiUrl('/api/sessions'));
    if (!res.ok) throw new Error('Failed to fetch sessions');
    return await res.json();
  } catch (err) {
    console.warn('Sessions endpoint unavailable, returning empty list:', err);
    return [];
  }
}

export async function createSession(title?: string, primaryAgentId?: string): Promise<ApiSessionItem> {
  const res = await fetch(apiUrl('/api/sessions'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, primary_agent_id: primaryAgentId }),
  });
  if (!res.ok) throw new Error('Failed to create session');
  return await res.json();
}

export async function fetchSessionDetails(sessionId: string): Promise<ApiSessionDetail> {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}`));
  if (!res.ok) throw new Error('Failed to fetch session details');
  return await res.json();
}

export async function renameSession(sessionId: string, title: string): Promise<ApiSessionItem> {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to rename session');
  return await res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}`), {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete session');
}

export async function fetchSessionMessages(sessionId: string): Promise<{ session_id: string; total: number; messages: ApiMessageItem[] }> {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}/messages`));
  if (!res.ok) throw new Error('Failed to fetch messages');
  return await res.json();
}

export async function createManualMessage(sessionId: string, content: string, role: string = 'user'): Promise<ApiMessageItem> {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}/messages`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, role }),
  });
  if (!res.ok) throw new Error('Failed to create message');
  return await res.json();
}

export async function deleteMessage(messageId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/messages/${messageId}`), {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete message');
}

export async function clearSessionMessages(sessionId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}/messages`), {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to clear session messages');
}

/**
 * A row from the persisted execution timeline.
 *
 * The backend emits two shapes and neither carries the display fields the steps
 * panel wants, so this is the raw contract rather than a UI model:
 *   {type: 'agent_run', agent_id, status, started_at, finished_at}
 *   {type: 'tool_call', tool,     status, started_at, completed_at, output}
 */
export interface PersistedTimelineRow {
  id?: string;
  step_key?: string;
  type?: string;
  tool?: string;
  agent_id?: string;
  status?: string;
  started_at?: string;
  finished_at?: string;
  completed_at?: string;
  timestamp?: string;
  detail?: string;
  output?: string;
}

export async function fetchSessionTimeline(
  sessionId: string
): Promise<{ session_id: string; timeline: PersistedTimelineRow[] }> {
  const res = await fetch(apiUrl(`/api/sessions/${sessionId}/timeline`));
  if (!res.ok) throw new Error('Failed to fetch session timeline');
  return await res.json();
}

export interface ApiQuickAction {
  id: string;
  title: string;
  description: string;
  prompt: string;
  emoji?: string;
  target_agent_id?: string;
  /** Presentation hints; the UI only reads `color_scheme` today. */
  style?: { color_scheme?: string } & Record<string, unknown>;
}

export async function fetchQuickActions(): Promise<ApiQuickAction[]> {
  try {
    const res = await fetch(apiUrl('/api/quick-actions'));
    if (!res.ok) throw new Error('Failed to fetch quick actions');
    return await res.json();
  } catch (err) {
    console.warn('Quick actions endpoint unavailable:', err);
    return [];
  }
}

export interface ApiArtifactItem {
  id: string;
  workspace_id: string;
  owner_id: string;
  session_id?: string;
  origin: 'user_upload' | 'agent_generated' | 'tool_output';
  name: string;
  kind: 'file' | 'image' | 'code' | 'report' | 'screenshot' | 'pdf';
  created_at: string;
  version: number;
  storage_uri: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  download_url: string;
  content_url: string;
  metadata?: Record<string, unknown>;
}

export async function uploadArtifactToGarage(
  file: File,
  sessionId?: string,
  messageId?: string
): Promise<ApiArtifactItem> {
  const formData = new FormData();
  formData.append('file', file);
  if (sessionId) formData.append('session_id', sessionId);
  if (messageId) formData.append('message_id', messageId);

  const res = await fetch(apiUrl('/api/artifacts/upload'), {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to upload artifact to Garage: ${err}`);
  }
  return await res.json();
}

export async function fetchArtifacts(sessionId?: string, origin?: string): Promise<ApiArtifactItem[]> {
  try {
    const params = new URLSearchParams();
    if (sessionId) params.append('session_id', sessionId);
    if (origin) params.append('origin', origin);
    const qs = params.toString() ? `?${params.toString()}` : '';

    const res = await fetch(apiUrl(`/api/artifacts${qs}`));
    if (!res.ok) throw new Error('Failed to fetch artifacts');
    const data = await res.json();
    return data.artifacts || [];
  } catch (err) {
    console.warn('Artifacts endpoint unavailable:', err);
    return [];
  }
}

export async function deleteArtifact(artifactId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/artifacts/${artifactId}`), {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete artifact');
}

export function getArtifactDownloadUrl(artifactId: string): string {
  return apiUrl(`/api/artifacts/${artifactId}/download`);
}

export function getArtifactContentUrl(artifactId: string): string {
  return apiUrl(`/api/artifacts/${artifactId}/content`);
}

/**
 * Answers an agent's pending question.
 *
 * This resolves the future the `ask_user` tool is blocked on, so the run resumes
 * on its existing SSE stream. No new run or message is created here.
 */
export async function submitHumanAnswer(
  questionId: string,
  answer: HumanInputAnswer
): Promise<{ status: string; question_id: string; answered: boolean; answer?: string }> {
  const res = await fetch(apiUrl(`/api/hitl/${questionId}/answer`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer }),
  });
  if (!res.ok) {
    // The backend wraps HTTPException detail under `message`.
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.message || body?.detail || detail;
    } catch {
      /* non-JSON error body: keep the status text */
    }
    throw new Error(detail);
  }
  return await res.json();
}

/** Questions a session is still waiting on, so a reloaded page can re-render them. */
export async function fetchPendingHumanInput(
  sessionId: string
): Promise<HumanInputRequest[]> {
  try {
    const res = await fetch(apiUrl(`/api/sessions/${sessionId}/hitl/pending`));
    if (!res.ok) throw new Error('Failed to fetch pending questions');
    const data = await res.json();
    return (data.questions || []) as HumanInputRequest[];
  } catch (err) {
    console.warn('Pending HITL questions unavailable:', err);
    return [];
  }
}

/**
 * Renders a tool call as one readable step line.
 *
 * The implementation lives in `utils/steps` (a Vite-env-free module) and is
 * re-exported here so callers can keep importing UI helpers from the API layer.
 */
export { describeToolCall } from '../utils/steps';

/* ── Job Hunt ─────────────────────────────────────────────────────────────── */

export type JobVerdict = 'strong' | 'good' | 'stretch' | 'skip';
export type JobStatus = 'new' | 'shortlisted' | 'tailored' | 'applied' | 'rejected';

export interface JobParameter {
  score: number;
  note: string;
}

export interface JobEvaluation {
  overall: number;
  verdict: JobVerdict;
  parameters: Record<string, JobParameter>;
  why: string[];
  gaps: string[];
  red_flags: string[];
  evaluated_at: string;
}

export interface JobItem {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  salary: string;
  posted: string;
  work_mode: string;
  experience_level: string;
  description: string;
  skills: string[];
  status: JobStatus;
  scraped_at: string;
  evaluation: JobEvaluation | null;
  resume: { template: string; generated_at: string; notes: string[] } | null;
  has_resume?: boolean;
}

export interface JobStats {
  total: number;
  evaluated: number;
  strong: number;
  good: number;
  tailored: number;
  by_status: Record<string, number>;
  has_profile: boolean;
  average_score: number;
}

export interface JobProfile {
  name?: string;
  headline?: string;
  target_roles?: string[];
  locations?: string[];
  years_experience?: number;
  sample?: boolean;
  skills?: { category: string; items: string[] | string }[];
}

export async function fetchJobHunt(): Promise<{ jobs: JobItem[]; stats: JobStats; profile: JobProfile; weights: Record<string, number> }> {
  const [jobsRes, overviewRes] = await Promise.all([
    fetch(apiUrl('/api/jobhunt/jobs')),
    fetch(apiUrl('/api/jobhunt/overview')),
  ]);
  if (!jobsRes.ok || !overviewRes.ok) throw new Error('Failed to load job hunt data');
  const jobs = await jobsRes.json();
  const overview = await overviewRes.json();
  return { jobs: jobs.jobs, stats: jobs.stats, profile: overview.profile, weights: overview.weights };
}

export async function setJobStatus(jobId: string, status: JobStatus): Promise<void> {
  const res = await fetch(apiUrl(`/api/jobhunt/jobs/${encodeURIComponent(jobId)}/status`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error('Failed to update job status');
}

export async function deleteJob(jobId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/jobhunt/jobs/${encodeURIComponent(jobId)}`), { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete job');
}

export async function loadSampleJobs(): Promise<void> {
  const res = await fetch(apiUrl('/api/jobhunt/sample'), { method: 'POST' });
  if (!res.ok) throw new Error('Failed to load sample data');
}

export async function clearSampleJobs(): Promise<void> {
  const res = await fetch(apiUrl('/api/jobhunt/sample'), { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to clear sample data');
}

export function getJobResumeUrl(jobId: string, download = false): string {
  return apiUrl(`/api/jobhunt/jobs/${encodeURIComponent(jobId)}/resume${download ? '?download=true' : ''}`);
}
