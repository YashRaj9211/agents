import { create } from 'zustand';
import {
  streamChatMessage,
  checkBackendHealth,
  fetchAgentList,
  fetchSessions,
  createSession as createSessionApi,
  fetchSessionDetails,
  renameSession as renameSessionApi,
  deleteSession as deleteSessionApi,
  deleteMessage as deleteMessageApi,
  clearSessionMessages as clearSessionMessagesApi,
  fetchSessionTimeline as fetchSessionTimelineApi,
  fetchQuickActions,
  submitHumanAnswer as submitHumanAnswerApi,
  fetchPendingHumanInput,
  describeToolCall,
  cancelRun as cancelRunApi,
  cancelSessionRun as cancelSessionRunApi,
  fetchActiveRuns,
  streamRunEvents,
  type AgentInfo,
  type TimelineEventItem,
  type StreamEventPayload,
  type ApiSessionItem,
  type ApiRunItem,
  type HumanInputAnswer,
  type HumanInputRequest,
  type PersistedTimelineRow as ApiTimelineRow
} from '../services/api';
import type { ChatSession } from '../components/chat/ChatHistorySidebar';
import type { ChatMessage } from '../components/chat/MessageList';
import type { ActionCardData } from '../components/chat/QuickActionCards';

export interface UserProfile {
  name: string;
  handle: string;
  initials: string;
}

/** One agent action in the live run, rendered as a collapsible single-line step. */
export interface RunStep {
  /** Stable identity: tool name plus a monotonic index, so concurrent duplicate
   *  calls to the same tool update *their own* step. */
  stepKey: string;
  type: TimelineEventItem['type'];
  label: string;
  /** What is actually running ("git status", "/tmp/out.pdf"). */
  detail?: string;
  output?: string;
  status: TimelineEventItem['status'];
  timestamp: string;
  durationMs?: number;
  /** Set for human-input steps so the panel can point at the question card. */
  questionId?: string;
  /** True when the row is expanded in the panel. */
  expanded?: boolean;
}

/**
 * A snapshot of a turn that is still executing in a session the user is not
 * currently looking at. Runs outlive the view (the backend owns them), so this
 * is what lets the user leave a running session and come back to it.
 */
export interface SessionRunSnapshot {
  runId: string;
  agentName: string;
  chunkText: string;
  question: HumanInputRequest | null;
  startedAt: number | null;
  updatedAt: number;
}

export interface ChatStoreState {
  activeTab: string;
  user: UserProfile;
  availableAgents: AgentInfo[];
  selectedAgentId: string;
  sessions: ChatSession[];
  activeSessionId: string;
  searchQuery: string;
  messages: ChatMessage[];
  isThinking: boolean;
  isSyncing: boolean;
  backendOnline: boolean | null;
  error: string | null;
  quickActions: ActionCardData[];
  activeTimeline: TimelineEventItem[];
  showTimelineDrawer: boolean;
  /** Live steps for the current turn, shown in the docked panel above the input. */
  runSteps: RunStep[];
  /** When the current turn began (ms epoch), for the elapsed-time readout. */
  runStartedAt: number | null;
  /** Whether the docked steps panel is expanded. */
  stepsExpanded: boolean;
  /** The question the agent is blocked on, if any. */
  pendingHumanInput: HumanInputRequest | null;
  /** True while the run is waiting on a human answer. */
  isWaitingForHuman: boolean;
  /** True while an answer POST is in flight. */
  isSubmittingAnswer: boolean;

  /** Session id -> the run id currently executing for that session. */
  sessionRunId: Record<string, string>;
  /** Every run executing right now, across all sessions (the fleet panel). */
  activeRuns: ApiRunItem[];
  /** Server-side cap on concurrent runs, for the fleet panel's "n / limit". */
  activeRunLimit: number;
  /** Runs the user has asked to stop, so their Stop button can show progress. */
  stoppingRunIds: string[];
  /** Live turns for sessions that are not on screen (see SessionRunSnapshot). */
  sessionRuns: Record<string, SessionRunSnapshot>;

  setActiveTab: (tab: string) => void;
  setSelectedAgentId: (agentId: string) => void;
  setSearchQuery: (query: string) => void;
  toggleTimelineDrawer: () => void;
  toggleSteps: () => void;
  toggleStep: (stepKey: string) => void;
  submitHumanAnswer: (answer: HumanInputAnswer) => Promise<void>;
  /** Stops a run (by run id) or whichever run a session has in flight. */
  stopRun: (sessionIdOrRunId: string) => Promise<void>;
  /** Refreshes the fleet of runs executing right now. */
  loadActiveRuns: () => Promise<ApiRunItem[]>;
  /** Re-attaches to a run that is already executing (e.g. after a reload). */
  attachToRun: (sessionId: string, runId: string) => Promise<void>;
  selectSession: (sessionId: string) => Promise<void> | void;
  createNewChat: () => void;
  createSession: (title?: string) => Promise<string>;
  renameSession: (sessionId: string, newTitle: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  clearSessionMessages: (sessionId?: string) => Promise<void>;
  loadTimeline: (sessionId?: string) => Promise<TimelineEventItem[]>;
  sendMessage: (text: string, artifactIds?: string[]) => Promise<void>;
  checkHealth: () => Promise<void>;

  loadAgents: () => Promise<void>;
  loadSessions: () => Promise<void>;
}

/**
 * A row from `GET /api/sessions/{id}/timeline` (re-exported for convenience).
 * See `services/api.ts` for the two shapes the backend emits.
 */
export type PersistedTimelineRow = ApiTimelineRow;

/** Maps a persisted backend timeline row onto the live step shape. */
export function timelineRowToStep(t: PersistedTimelineRow, idx: number): RunStep {
  const isRun = t.type === 'agent_run';
  const startedAt = t.started_at || t.completed_at || t.timestamp;
  const name = t.tool || t.agent_id || 'step';
  const described = isRun ? { label: humanizeAgentId(name) } : describeToolCall(name);
  const started = startedAt ? new Date(startedAt).getTime() : undefined;
  const finishedRaw = t.finished_at || t.completed_at;
  const finished = finishedRaw ? new Date(finishedRaw).getTime() : undefined;

  return {
    // Persisted rows have no key, so derive one that is stable across reloads.
    stepKey: t.step_key || `${isRun ? 'run' : 'tool'}:${name}:${idx}`,
    type: isRun ? 'agent_transfer' : 'tool_call',
    label: described.label,
    detail: t.detail || described.detail,
    output: t.output ? String(t.output) : undefined,
    status:
      t.status === 'completed' || t.status === 'success'
        ? 'completed'
        : t.status === 'failed' || t.status === 'error'
          ? 'failed'
          : 'running',
    timestamp: startedAt
      ? new Date(startedAt).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        })
      : 'Recent',
    durationMs:
      started !== undefined && finished !== undefined && finished >= started
        ? finished - started
        : undefined
  };
}

/** Merges live steps with persisted ones, so a refresh shows the same list. */
export function reconcileSteps(live: RunStep[], persisted: RunStep[]): RunStep[] {
  const seen = new Set(live.map((s) => s.stepKey));
  return [...live, ...persisted.filter((s) => !seen.has(s.stepKey))];
}

export const INITIAL_CHAT_SESSIONS: ChatSession[] = [
  {
    id: 's-1',
    title: 'Visual exploration',
    preview: 'Exploring visual styles, moods, and generative art agents...',
    timeAgo: '2h ago',
    agent: 'Root Agent',
    avatars: ['AL', 'RA']
  },
  {
    id: 's-2',
    title: 'Image generation & vision',
    preview: 'Creating a futuristic portrait using vision subagents and local models...',
    timeAgo: '3h ago',
    agent: 'Browser Agent',
    thumbnail: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&auto=format&fit=crop&q=60'
  },
  {
    id: 's-3',
    title: 'Team session orchestration',
    preview: 'Collaborative prompt editing and subagent task chaining...',
    timeAgo: '3h ago',
    agent: 'CLI Agent',
    avatars: ['YR', 'BA', 'CA']
  },
  {
    id: 's-4',
    title: 'Visualisation & charts',
    preview: 'Creating interactive performance graphs from backend logs...',
    timeAgo: '5h ago',
    agent: 'Job Assist Agent'
  }
];

// Offline fallbacks. These intentionally mirror the backend seed catalog in
// app/core/config.py (DEFAULT_QUICK_ACTIONS) so the UI looks identical whether or
// not the API is reachable — previously the two lists disagreed on colourScheme
// and omitted target_agent_id, so quick actions silently lost agent routing.
export const INITIAL_QUICK_ACTIONS: ActionCardData[] = [
  {
    id: 'firecrawl_laya',
    emoji: '🔍',
    title: 'Crawl GitHub repository',
    description: 'Scrape repo & extract description using firecrawl_agent',
    prompt: 'crawl https://github.com/NandhaKishorM/laya this link and provide me one description about this repository',
    colorScheme: 'orange',
    target_agent_id: 'firecrawl_agent'
  },
  {
    id: 'browser_action',
    emoji: '🌐',
    title: 'Run browser task',
    description: 'Automate forms, research, or scrape data with Playwright',
    prompt: 'Browse to news.ycombinator.com and summarize the top 5 articles with browser_agent',
    colorScheme: 'purple',
    target_agent_id: 'browser_agent'
  },
  {
    id: 'job_assist',
    emoji: '📄',
    title: 'Generate resume',
    description: 'Craft tailored PDF resume using job_assist_agent',
    prompt: 'Generate an updated resume PDF tailored for an AI Research Engineer position',
    colorScheme: 'green',
    target_agent_id: 'job_assist_agent'
  },
  {
    id: 'cli_diagnostics',
    emoji: '💻',
    title: 'System diagnostics',
    description: 'Run shell inspection and resource report with cli_agent',
    prompt: 'Show system status and disk space using cli_agent',
    colorScheme: 'blue',
    target_agent_id: 'cli_agent'
  }
];

/** Narrows a backend `style.color_scheme` value to a supported accent colour. */
function normalizeColorScheme(raw?: string): ActionCardData['colorScheme'] {
  const allowed: NonNullable<ActionCardData['colorScheme']>[] = ['orange', 'purple', 'blue', 'green'];
  const candidate = (raw || '').toLowerCase() as NonNullable<ActionCardData['colorScheme']>;
  return allowed.includes(candidate) ? candidate : 'blue';
}

/** Turns `job_assist_agent` into `Job Assist Agent` for display. */
function humanizeAgentId(rawId?: string | null): string {
  if (!rawId) return 'Agent';
  return rawId
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** True for the offline placeholder sessions below, which are not backend-backed. */
function isMockSessionId(sessionId: string): boolean {
  return INITIAL_CHAT_SESSIONS.some((s) => s.id === sessionId);
}

function formatTimeAgo(dateString?: string): string {  if (!dateString) return 'Recent';
  try {
    const d = new Date(dateString);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return `${Math.floor(diffSec / 86400)}d ago`;
  } catch {
    return 'Recent';
  }
}

function mapApiSession(s: ApiSessionItem): ChatSession {
  return {
    id: s.id,
    title: s.title || 'Untitled Session',
    preview: s.preview || 'No messages yet',
    timeAgo: formatTimeAgo(s.last_message_at || s.created_at),
    agent: humanizeAgentId(s.primary_agent_id || 'root_agent'),
    avatars: ['AL', 'AG']
  };
}

export const useChatStore = create<ChatStoreState>((set, get) => {
  /**
   * Applies a patch only when `sessionId` is the conversation on screen.
   *
   * Agent runs execute in the backend and keep streaming after the user moves to
   * another conversation. Their events must therefore never leak into whichever
   * session happens to be open -- the old code let a background run flip the
   * visible session's "thinking" state and append its steps to that session's
   * panel.
   */
  const applyForSession = (
    sessionId: string,
    patch: (state: ChatStoreState) => Partial<ChatStoreState>
  ) => {
    if (get().activeSessionId !== sessionId) return;
    set(patch);
  };

  /** Records the live turn for a session the user is not looking at. */
  const cacheSessionRun = (
    sessionId: string,
    patch: Partial<SessionRunSnapshot> & { runId: string; agentName: string }
  ) => {
    set((state) => {
      const previous = state.sessionRuns[sessionId];
      return {
        sessionRuns: {
          ...state.sessionRuns,
          [sessionId]: {
            runId: patch.runId,
            agentName: patch.agentName || previous?.agentName || 'Agent',
            chunkText: patch.chunkText ?? previous?.chunkText ?? '',
            question: patch.question !== undefined ? patch.question : previous?.question ?? null,
            startedAt: patch.startedAt ?? previous?.startedAt ?? null,
            updatedAt: Date.now()
          }
        },
        sessionRunId: { ...state.sessionRunId, [sessionId]: patch.runId }
      };
    });
  };

  /** Clears a session's live-run bookkeeping once its run has settled. */
  const clearSessionRun = (sessionId: string) => {
    set((state) => {
      const { [sessionId]: _dropped, ...restRuns } = state.sessionRuns;
      return { sessionRuns: restRuns };
    });
    set((state) => {
      const { [sessionId]: _dropped, ...restIds } = state.sessionRunId;
      return { sessionRunId: restIds };
    });
  };

  return {
  activeTab: 'home',
  user: {
    name: 'Allison',
    handle: '@allison_4_li',
    initials: 'AL'
  },
  availableAgents: [
    { id: 'root_agent', name: 'Root Orchestrator', description: 'Central coordinator' },
    { id: 'browser_agent', name: 'Browser Agent', description: 'Playwright automation' },
    { id: 'cli_agent', name: 'CLI Agent', description: 'Terminal & commands' },
    { id: 'scheduler_agent', name: 'Scheduler Agent', description: 'Timers and cron jobs' },
    { id: 'job_assist_agent', name: 'Job Assist', description: 'Resume & applications' },
    { id: 'firecrawl_agent', name: 'Firecrawl Agent', description: 'Web scraping & crawling' },
  ],
  selectedAgentId: 'root_agent',
  sessions: INITIAL_CHAT_SESSIONS,
  activeSessionId: '',
  searchQuery: '',
  messages: [],
  isThinking: false,
  isSyncing: false,
  backendOnline: null,
  error: null,
  quickActions: INITIAL_QUICK_ACTIONS,
  activeTimeline: [],
  showTimelineDrawer: false,
  runSteps: [],
  runStartedAt: null,
  stepsExpanded: true,
  pendingHumanInput: null,
  isWaitingForHuman: false,
  isSubmittingAnswer: false,
  sessionRunId: {},
  activeRuns: [],
  activeRunLimit: 0,
  stoppingRunIds: [],
  sessionRuns: {},

  setActiveTab: (tab: string) => set({ activeTab: tab }),

  setSelectedAgentId: (agentId: string) => set({ selectedAgentId: agentId }),

  setSearchQuery: (query: string) => set({ searchQuery: query }),

  toggleTimelineDrawer: () => set((s) => ({ showTimelineDrawer: !s.showTimelineDrawer })),

  toggleSteps: () => set((s) => ({ stepsExpanded: !s.stepsExpanded })),

  toggleStep: (stepKey: string) =>
    set((s) => ({
      runSteps: s.runSteps.map((step) =>
        step.stepKey === stepKey ? { ...step, expanded: !step.expanded } : step
      )
    })),

  submitHumanAnswer: async (answer: HumanInputAnswer) => {
    const question = get().pendingHumanInput;
    if (!question || get().isSubmittingAnswer) return;

    set({ isSubmittingAnswer: true, error: null });
    // Mark the question's step as answered optimistically; the agent resumes on
    // the still-open SSE stream, so the real confirmation arrives there.
    set((s) => ({
      runSteps: s.runSteps.map((step) =>
        step.questionId === question.question_id ? { ...step, status: 'completed' } : step
      )
    }));

    try {
      await submitHumanAnswerApi(question.question_id, answer);
      set({
        pendingHumanInput: null,
        isWaitingForHuman: false,
        isSubmittingAnswer: false
      });
    } catch (err) {
      // Roll the card back so the user can retry rather than losing the question.
      set((s) => ({
        pendingHumanInput: question,
        isWaitingForHuman: true,
        isSubmittingAnswer: false,
        error: err instanceof Error ? err.message : String(err),
        runSteps: s.runSteps.map((step) =>
          step.questionId === question.question_id ? { ...step, status: 'running' } : step
        )
      }));
    }
  },

  selectSession: async (sessionId: string) => {
    const { sessions } = get();
    set({
      activeSessionId: sessionId,
      isSyncing: true,
      error: null,
      // Reset turn-scoped state before the fetch so the panel cannot show the
      // previous session's steps while this one loads.
      runSteps: [],
      pendingHumanInput: null,
      isWaitingForHuman: false
    });

    // Restore the live turn for the session being opened: either what we cached
    // while it streamed in the background, or by re-attaching to the run the
    // backend still owns (the page may have been reloaded in between).
    //
    // "Thinking" is derived from the session being opened, never inherited: an
    // agent running in some other conversation must not disable this one's input.
    const cachedRun = get().sessionRuns[sessionId];
    const liveRunId = get().sessionRunId[sessionId];
    if (cachedRun) {
      set({
        runStartedAt: cachedRun.startedAt,
        pendingHumanInput: cachedRun.question,
        isWaitingForHuman: Boolean(cachedRun.question),
        isThinking: true
      });
    } else if (liveRunId) {
      set({ isThinking: true, runStartedAt: Date.now() });
      void get().attachToRun(sessionId, liveRunId);
    } else {
      set({ isThinking: false, runStartedAt: null });
    }

    try {
      const details = await fetchSessionDetails(sessionId);
      if (details && details.messages) {
        const mappedMessages: ChatMessage[] = details.messages.map((m) => ({
          id: m.id,
          sender: m.role === 'user' ? 'user' : 'agent',
          agentName: humanizeAgentId(m.sender_agent_id),
          text: m.content,
          // Message metadata is free-form; only these two keys are ever read, and
          // they are coerced so a non-string value cannot reach ReactMarkdown.
          thoughtProcess:
            typeof m.metadata?.thought_process === 'string' ? m.metadata.thought_process : undefined,
          rawText: typeof m.metadata?.raw_text === 'string' ? m.metadata.raw_text : undefined,
          timestamp: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Just now'
        }));
        set({ messages: mappedMessages, isSyncing: false });
        // Restore this session's execution history and any question it is still
        // blocked on (the run outlives the page, so the card must survive a reload).
        get().loadTimeline(sessionId);
        void fetchPendingHumanInput(sessionId).then((questions) => {
          const active = questions[0];
          if (!active) return;
          set((s) => ({
            // Only adopt a question for the session still in view.
            pendingHumanInput: s.activeSessionId === sessionId ? active : s.pendingHumanInput,
            isWaitingForHuman: s.activeSessionId === sessionId ? true : s.isWaitingForHuman
          }));
        });
        return;
      }
    } catch {
      // Fallback if session is a local mock
    } finally {
      set({ isSyncing: false });
    }

    const session = sessions.find((s) => s.id === sessionId);
    if (session) {
      set({
        messages: [
          {
            id: 'm-1',
            sender: 'user',
            text: `Continue session: ${session.title}`,
            timestamp: session.timeAgo
          },
          {
            id: 'm-2',
            sender: 'agent',
            agentName: session.agent,
            text: `Resumed session context for "${session.title}". ${session.preview} How can I assist you?`,
            timestamp: 'Just now',
            timelineEvents: [
              {
                id: 'tl-init',
                type: 'info',
                title: 'Session restored',
                status: 'completed',
                timestamp: 'Just now'
              }
            ]
          }
        ]
      });
    }
  },

  createNewChat: () => {
    set({
      activeSessionId: '',
      messages: [],
      error: null,
      activeTimeline: [],
      runSteps: [],
      pendingHumanInput: null,
      isWaitingForHuman: false
    });
  },

  createSession: async (title?: string) => {
    const { selectedAgentId } = get();
    try {
      const newSession = await createSessionApi(title || 'New conversation', selectedAgentId);
      const mapped = mapApiSession(newSession);
      set((state) => ({
        sessions: [mapped, ...state.sessions.filter((s) => s.id !== mapped.id)],
        activeSessionId: mapped.id,
        messages: [],
        error: null,
        activeTimeline: []
      }));
      return mapped.id;
    } catch {
      const fallbackId = `s-${Date.now()}`;
      const fallbackSession: ChatSession = {
        id: fallbackId,
        title: title || 'New conversation',
        preview: 'Brand new session',
        timeAgo: 'Just now',
        agent: selectedAgentId === 'root_agent' ? 'Root Agent' : selectedAgentId,
        avatars: ['AL', 'AG']
      };
      set((state) => ({
        sessions: [fallbackSession, ...state.sessions],
        activeSessionId: fallbackId,
        messages: []
      }));
      return fallbackId;
    }
  },

  renameSession: async (sessionId: string, newTitle: string) => {
    const trimmed = newTitle.trim();
    if (!trimmed) return;

    // Optimistic UI update
    set((state) => ({
      sessions: state.sessions.map((s) => (s.id === sessionId ? { ...s, title: trimmed } : s))
    }));

    try {
      await renameSessionApi(sessionId, trimmed);
    } catch (err) {
      console.warn('Backend rename session error:', err);
    }
  },

  deleteSession: async (sessionId: string) => {
    const { sessions, activeSessionId } = get();
    const remaining = sessions.filter((s) => s.id !== sessionId);
    const wasActive = activeSessionId === sessionId;
    const nextSession = wasActive ? remaining[0] : null;

    set({
      sessions: remaining,
      activeSessionId: nextSession ? nextSession.id : (wasActive ? '' : activeSessionId),
      messages: wasActive && !nextSession ? [] : get().messages
    });

    try {
      await deleteSessionApi(sessionId);
    } catch (err) {
      console.warn('Backend delete session error:', err);
    }

    if (wasActive && nextSession) {
      get().selectSession(nextSession.id);
    }
  },

  deleteMessage: async (messageId: string) => {
    // Optimistic update
    set((state) => ({
      messages: state.messages.filter((m) => m.id !== messageId)
    }));

    try {
      await deleteMessageApi(messageId);
    } catch (err) {
      console.warn('Backend delete message error:', err);
    }
  },

  clearSessionMessages: async (sessionId?: string) => {
    const targetSessionId = sessionId || get().activeSessionId;
    set({ messages: [] });

    if (targetSessionId) {
      try {
        await clearSessionMessagesApi(targetSessionId);
      } catch (err) {
        console.warn('Backend clear messages error:', err);
      }
    }
  },

  loadTimeline: async (sessionId?: string) => {
    const targetId = sessionId || get().activeSessionId;
    if (!targetId) {
      set({ activeTimeline: [] });
      return [];
    }

    try {
      const res = await fetchSessionTimelineApi(targetId);
      const rows: PersistedTimelineRow[] = res.timeline || [];
      const events: TimelineEventItem[] = rows.map((t) => {
        const step = timelineRowToStep(t, 0);
        return {
          id: t.id || step.stepKey,
          type: step.type,
          title: step.label,
          description: step.output || step.detail,
          status: step.status,
          timestamp: step.timestamp,
          detail: step.detail,
          output: step.output,
          stepKey: step.stepKey
        };
      });
      set({ activeTimeline: events });

      // Persisted steps are the source of truth after a reload; keep any live
      // steps that have not been written yet, then append the rest.
      const persisted = rows.map((t, idx: number) => timelineRowToStep(t, idx));
      set((s) => ({ runSteps: reconcileSteps(s.runSteps, persisted) }));
      return events;
    } catch {
      set({ activeTimeline: [] });
      return [];
    }
  },

  loadSessions: async () => {
    try {
      const apiSessions = await fetchSessions();
      // A reachable backend with zero sessions is a real answer: show an empty
      // sidebar rather than resurrecting the offline placeholder conversations.
      const mapped = apiSessions.map(mapApiSession);
      set({ sessions: mapped });
    } catch (err) {
      console.warn('Failed to refresh sessions:', err);
    }
  },

  checkHealth: async () => {
    const online = await checkBackendHealth();
    set({ backendOnline: online });
  },

  loadAgents: async () => {
    try {
      const [agentsRes, sessionsRes, actionsRes] = await Promise.allSettled([
        fetchAgentList(),
        fetchSessions(),
        fetchQuickActions()
      ]);

      if (agentsRes.status === 'fulfilled' && agentsRes.value && agentsRes.value.length > 0) {
        set({ availableAgents: agentsRes.value });
      }

      if (sessionsRes.status === 'fulfilled' && sessionsRes.value && sessionsRes.value.length > 0) {
        const mappedSessions: ChatSession[] = sessionsRes.value.map(mapApiSession);
        set({ sessions: mappedSessions });
      }

      if (actionsRes.status === 'fulfilled' && actionsRes.value && actionsRes.value.length > 0) {
        const mappedActions: ActionCardData[] = actionsRes.value.map((a) => ({
          id: a.id,
          title: a.title,
          description: a.description,
          prompt: a.prompt,
          emoji: a.emoji || '⚡',
          colorScheme: normalizeColorScheme(a.style?.color_scheme),
          target_agent_id: a.target_agent_id
        }));
        set({ quickActions: mappedActions });
      }
    } catch {
      // Fallback handled gracefully
    }
  },

  sendMessage: async (text: string, artifactIds?: string[]) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    const { activeSessionId, selectedAgentId } = get();

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text: trimmed,
      timestamp: 'Just now'
    };

    // The backend stores conversations under a server-generated session UUID and
    // derives a *different* UUID when handed an arbitrary client string. Sending a
    // fabricated "s-<timestamp>" id therefore filed the conversation under an id the
    // UI never knew about, so history, rename, delete and timeline all missed it.
    // Create the session server-side first and stream against its real id.
    let sessionId = activeSessionId;
    if (!sessionId) {
      sessionId = await get().createSession(
        trimmed.length > 40 ? `${trimmed.slice(0, 40)}...` : trimmed
      );
    }

    const agentMsgId = `msg-${Date.now() + 1}`;
    const initialAgentMessage: ChatMessage = {
      id: agentMsgId,
      sender: 'agent',
      agentName: humanizeAgentId(selectedAgentId),
      text: '',
      timestamp: 'Just now',
      timelineEvents: [],
      isStreaming: true
    };

    set({
      messages: [...get().messages, userMessage, initialAgentMessage],
      isThinking: true,
      error: null,
      activeSessionId: sessionId,
      // A new turn starts a fresh step list; the previous turn's steps are
      // persisted and come back through loadTimeline once this run settles.
      runSteps: [],
      runStartedAt: Date.now(),
      pendingHumanInput: null,
      isWaitingForHuman: false,
      // Drop offline placeholders, but keep the real session createSession just
      // added so the sidebar shows it immediately (before the post-stream refresh).
      sessions: get().sessions.filter((s) => !isMockSessionId(s.id))
    });

    let currentTimeline: TimelineEventItem[] = [];
    let streamedChunkText = '';
    let doneReceived = false;
    // Tool calls are tracked per-name through their lifecycle. The result event
    // carries no call id, so a FIFO queue per tool name resolves concurrent or
    // repeated calls correctly -- the old substring match could not.
    const openCalls: Record<string, string[]> = {};
    const startedAt = new Map<string, number>();

    try {
      await streamChatMessage(
        trimmed,
        selectedAgentId,
        sessionId,
        (evt: StreamEventPayload) => {

          const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

          if (evt.type === 'start') {
            // The backend echoes the authoritative session UUID here. If it differs
            // from what we sent (e.g. the request omitted one), adopt its id so the
            // follow-up session/timeline fetches address the row that was created.
            const canonicalId = evt.session_id;
            if (canonicalId && canonicalId !== sessionId) {
              const previousId = sessionId;
              sessionId = canonicalId;
              set((state) => ({
                activeSessionId:
                  state.activeSessionId === previousId ? canonicalId : state.activeSessionId,
                sessions: state.sessions.map((s) =>
                  s.id === previousId ? { ...s, id: canonicalId } : s
                )
              }));
            }
            // Remember which run this conversation is executing so the stop
            // button, the fleet panel and re-attach can all address it.
            if (evt.run_id) {
              cacheSessionRun(sessionId, {
                runId: evt.run_id,
                agentName: humanizeAgentId(evt.agent_id || selectedAgentId),
                startedAt: Date.now()
              });
              if (get().activeSessionId === sessionId) {
                set((state) => ({
                  sessions: state.sessions.map((s) =>
                    s.id === sessionId ? { ...s, running: true, runId: evt.run_id } : s
                  )
                }));
              }
            }
            return;
          }

          if (evt.type === 'heartbeat') {
            // Keeps an idle-but-waiting stream alive; nothing to render.
            return;
          }

          if (evt.type === 'agent_transfer') {
            const targetAgent = evt.to_agent || 'Sub-Agent';
            const stepKey = `agent:${targetAgent}:${startedAt.size}`;
            const step: RunStep = {
              stepKey,
              type: 'agent_transfer',
              label: `Delegated to ${humanizeAgentId(targetAgent)}`,
              detail: evt.from_agent ? `from ${humanizeAgentId(evt.from_agent)}` : undefined,
              status: 'completed',
              timestamp: nowStr
            };
            startedAt.set(stepKey, Date.now());
            applyForSession(sessionId, (state) => ({ runSteps: [...state.runSteps, step] }));
            currentTimeline = [
              ...currentTimeline,
              {
                id: `tl-${stepKey}`,
                type: 'agent_transfer',
                title: step.label,
                description: step.detail,
                status: 'completed',
                timestamp: nowStr,
                stepKey
              }
            ];
          } else if (evt.type === 'tool_call') {
            const toolName = evt.tool || 'tool';
            const stepKey = `tool:${toolName}:${startedAt.size}`;
            const { label, detail } = describeToolCall(toolName, evt.args);
            startedAt.set(stepKey, Date.now());
            openCalls[toolName] = [...(openCalls[toolName] || []), stepKey];

            const step: RunStep = {
              stepKey,
              type: 'tool_call',
              label,
              detail: evt.detail || detail,
              status: 'running',
              timestamp: nowStr
            };
            applyForSession(sessionId, (state) => ({ runSteps: [...state.runSteps, step] }));
            currentTimeline = [
              ...currentTimeline,
              {
                id: `tl-${stepKey}`,
                type: 'tool_call',
                title: label,
                description: step.detail,
                status: 'running',
                timestamp: nowStr,
                stepKey
              }
            ];
          } else if (evt.type === 'tool_result') {
            const toolName = evt.tool || 'tool';
            const queue = openCalls[toolName] || [];
            const stepKey = queue.shift();
            if (!stepKey) return;

            const began = startedAt.get(stepKey);
            const durationMs = began === undefined ? undefined : Date.now() - began;

            applyForSession(sessionId, (state) => ({
              runSteps: state.runSteps.map((step) =>
                step.stepKey === stepKey
                  ? {
                      ...step,
                      status: 'completed',
                      output: evt.output || step.output,
                      durationMs
                    }
                  : step
              )
            }));
            currentTimeline = currentTimeline.map((item) =>
              item.stepKey === stepKey
                ? { ...item, status: 'completed', output: evt.output, durationMs }
                : item
            );
          } else if (evt.type === 'human_input_request') {
            const request: HumanInputRequest = {
              question_id: evt.question_id || `q-${Date.now()}`,
              kind: evt.kind || 'confirm',
              question: evt.question || 'The agent needs your input to continue.',
              options: evt.options || [],
              run_id: evt.run_id,
              agent_id: evt.agent_id
            };
            const stepKey = `human:${request.question_id}`;
            startedAt.set(stepKey, Date.now());

            // The question belongs to this session, so it must not surface while
            // the user is reading a different conversation; it is cached instead
            // and restored when they return.
            cacheSessionRun(sessionId, {
              runId: get().sessionRunId[sessionId] || '',
              agentName: get().sessionRuns[sessionId]?.agentName || 'Agent',
              question: request
            });

            applyForSession(sessionId, (state) => ({
              pendingHumanInput: request,
              isWaitingForHuman: true,
              stepsExpanded: true,
              runSteps: [
                ...state.runSteps,
                {
                  stepKey,
                  type: 'human_input',
                  label: 'Waiting for your input',
                  detail: request.question,
                  status: 'running',
                  timestamp: nowStr,
                  questionId: request.question_id
                }
              ]
            }));
            currentTimeline = [
              ...currentTimeline,
              {
                id: `tl-${stepKey}`,
                type: 'human_input',
                title: 'Waiting for your input',
                description: request.question,
                status: 'running',
                timestamp: nowStr,
                stepKey,
                questionId: request.question_id
              }
            ];
          } else if (evt.type === 'chunk') {
            streamedChunkText += evt.text || '';
          } else if (evt.type === 'done' || evt.type === 'cancelled') {
            doneReceived = true;
            const cancelled = evt.type === 'cancelled';
            const finalAns = cancelled
              ? evt.final_output || streamedChunkText || '(stopped by user)'
              : evt.final_output || streamedChunkText;
            const thought = evt.thought_process || '';
            const raw = evt.raw_text || streamedChunkText;

            applyForSession(sessionId, (state) => ({
              messages: state.messages.map((m) =>
                m.id === agentMsgId
                  ? {
                      ...m,
                      text: finalAns,
                      thoughtProcess: thought,
                      rawText: raw,
                      timelineEvents: currentTimeline,
                      isStreaming: false,
                      cancelled
                    }
                  : m
              ),
              isThinking: false,
              runStartedAt: null,
              // A finished run cannot still be waiting on a person; clear the card
              // so a timed-out or cancelled question cannot linger.
              pendingHumanInput: null,
              isWaitingForHuman: false,
              runSteps: state.runSteps.map((step) =>
                step.status === 'running'
                  ? { ...step, status: cancelled ? 'failed' : 'completed' }
                  : step
              )
            }));

            // Bookkeeping is session-agnostic: the sidebar and the fleet panel
            // must reflect completion even when the user is elsewhere.
            clearSessionRun(sessionId);
            set((state) => ({
              sessions: state.sessions.map((s) =>
                s.id === sessionId ? { ...s, running: false, runId: undefined } : s
              )
            }));

            // Sync sessions, the fleet and the timeline with the backend.
            void get().loadSessions();
            void get().loadActiveRuns();
            if (get().activeSessionId === sessionId) get().loadTimeline(sessionId);
            return;
          }

          // Live update during stream
          if (!doneReceived) {
            applyForSession(sessionId, (state) => ({
              messages: state.messages.map((m) =>
                m.id === agentMsgId
                  ? {
                      ...m,
                      text: streamedChunkText,
                      timelineEvents: currentTimeline
                    }
                  : m
              )
            }));
            // Keep the off-screen copy in step so returning shows the live text.
            const cached = get().sessionRuns[sessionId];
            if (cached) {
              cacheSessionRun(sessionId, {
                runId: cached.runId,
                agentName: cached.agentName,
                chunkText: streamedChunkText
              });
            }
          }
        },
        artifactIds
      );

    } catch (err) {
      applyForSession(sessionId, (state) => ({
        messages: state.messages.map((m) =>
          m.id === agentMsgId
            ? {
                ...m,
                text: streamedChunkText || `Error connecting to agent: ${err instanceof Error ? err.message : String(err)}`,
                timelineEvents: currentTimeline,
                isStreaming: false
              }
            : m
        ),
        isThinking: false,
        error: String(err),
        runStartedAt: null,
        // A dropped connection means no more events; do not leave a question card
        // or running steps implying the agent is still alive.
        pendingHumanInput: null,
        isWaitingForHuman: false,
        runSteps: state.runSteps.map((step) =>
          step.status === 'running' ? { ...step, status: 'failed' } : step
        )
      }));
      clearSessionRun(sessionId);
      void get().loadActiveRuns();
    } finally {
      // Only the session that owns this run may lose its "thinking" flag; a run
      // finishing in the background must not re-enable/disable another session.
      applyForSession(sessionId, () => ({ isThinking: false }));
    }
  },

  loadActiveRuns: async () => {
    const runs = await fetchActiveRuns('running');
    const list = runs.runs || [];

    // Mirror the server's view of liveness into the sidebar and the per-session
    // run map, so a run that started before this page load is still addressable.
    set((state) => {
      const sessionRunId = { ...state.sessionRunId };
      for (const run of list) {
        if (run.session_id) sessionRunId[run.session_id] = run.run_id;
      }
      for (const [sessionId, runId] of Object.entries(sessionRunId)) {
        if (!list.some((run) => run.run_id === runId)) delete sessionRunId[sessionId];
      }
      return {
        activeRuns: list,
        activeRunLimit: runs.limit ?? 0,
        sessionRunId,
        sessions: state.sessions.map((session) => {
          const live = list.find((run) => run.session_id === session.id);
          return live
            ? { ...session, running: true, runId: live.run_id, runAgent: humanizeAgentId(live.agent_id) }
            : session.running
              ? { ...session, running: false, runId: undefined, runAgent: undefined }
              : session;
        })
      };
    });

    return list;
  },

  stopRun: async (sessionIdOrRunId: string) => {
    const state = get();
    const sessionId = state.sessionRunId[sessionIdOrRunId]
      ? sessionIdOrRunId
      : Object.keys(state.sessionRunId).find((key) => state.sessionRunId[key] === sessionIdOrRunId);
    const runId = sessionId ? state.sessionRunId[sessionId] : sessionIdOrRunId;

    if (state.stoppingRunIds.includes(runId)) return;
    set({ stoppingRunIds: [...get().stoppingRunIds, runId] });

    try {
      // Stop by run id when we know it, so the UI can stop a run it did not start.
      if (sessionId && runId) {
        await cancelRunApi(runId, true);
      } else {
        await cancelSessionRunApi(sessionIdOrRunId);
      }
    } catch (err) {
      console.warn('Stop run failed:', err);
      set({ error: err instanceof Error ? err.message : String(err) });
    } finally {
      set((prev) => ({ stoppingRunIds: prev.stoppingRunIds.filter((id) => id !== runId) }));
      // Re-sync rather than trusting the optimistic view.
      await get().loadActiveRuns();
      await get().loadSessions();
    }
  },

  attachToRun: async (sessionId: string, runId: string) => {
    // Re-attach after leaving the page (or a full reload). The buffered events
    // replay from the start, so the answer and step list rebuild; chunks are
    // merged into the session cache and only rendered when it is on screen.
    let settled = false;
    try {
      await streamRunEvents(runId, 0, (evt: StreamEventPayload) => {
        if (evt.type === 'attach') {
          cacheSessionRun(sessionId, {
            runId,
            agentName: evt.agent_id ? humanizeAgentId(evt.agent_id) : 'Agent'
          });
          return;
        }
        if (evt.type === 'chunk') {
          const existing = get().sessionRuns[sessionId];
          cacheSessionRun(sessionId, {
            runId,
            agentName: existing?.agentName || 'Agent',
            chunkText: (existing?.chunkText || '') + (evt.text || '')
          });
          return;
        }
        if (evt.type === 'human_input_request') {
          cacheSessionRun(sessionId, {
            runId,
            agentName: 'Agent',
            question: {
              question_id: evt.question_id || `q-${Date.now()}`,
              kind: evt.kind || 'confirm',
              question: evt.question || 'The agent needs your input to continue.',
              options: evt.options || [],
              run_id: evt.run_id,
              agent_id: evt.agent_id
            }
          });
          return;
        }
        if (evt.type === 'done' || evt.type === 'cancelled' || evt.type === 'error') {
          settled = true;
          clearSessionRun(sessionId);
          void get().loadActiveRuns();
          void get().loadSessions();
          // The persisted transcript is authoritative once the run is over.
          if (get().activeSessionId === sessionId) void get().selectSession(sessionId);
        }
      });
    } catch (err) {
      console.warn('Re-attach to run failed:', err);
    } finally {
      if (!settled) clearSessionRun(sessionId);
    }
  }
  };
});
