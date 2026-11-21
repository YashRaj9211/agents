import React from 'react';
import type { ApiRunItem } from '../../services/api';
import type { ChatSession } from '../chat/ChatHistorySidebar';
import { BotIcon, CloseIcon, PlayIcon } from '../icons/Icons';

interface RunningAgentsPanelProps {
  runs: ApiRunItem[];
  sessions: ChatSession[];
  activeSessionId: string;
  stoppingRunIds: string[];
  activeCount?: number;
  limit: number;
  onOpenSession: (sessionId: string) => void;
  onStopRun: (runId: string) => void;
  onRefresh?: () => void;
}

/** Human label for how a run began, so parallel work is explainable. */
function originLabel(origin?: string): string {
  switch (origin) {
    case 'peer':
      return 'peer message';
    case 'spawn':
      return 'spawned';
    case 'delegated':
      return 'delegated';
    default:
      return 'you';
  }
}

function humanizeAgentId(rawId?: string | null): string {
  if (!rawId) return 'Agent';
  return rawId.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function elapsedLabel(run: ApiRunItem): string {
  const ms = run.elapsed_ms ?? 0;
  const seconds = Math.max(0, Math.floor(ms / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${rest}s`;
}

/**
 * Fleet view of the agents executing right now.
 *
 * This is the control surface for parallel work: every run is listed with the
 * conversation it belongs to, so the user can jump into a running session
 * ("Open") or stop just that run without leaving the current one.
 */
export const RunningAgentsPanel: React.FC<RunningAgentsPanelProps> = ({
  runs,
  sessions,
  activeSessionId,
  stoppingRunIds,
  limit,
  onOpenSession,
  onStopRun,
  onRefresh
}) => {
  const titleFor = (run: ApiRunItem): string => {
    if (run.session_title) return run.session_title;
    const match = sessions.find((s) => s.id === run.session_id);
    return match?.title || 'Conversation';
  };

  if (runs.length === 0) {
    return null;
  }

  return (
    <section className="running-agents-panel" aria-label="Running agents">
      <header className="running-agents-header">
        <span className="running-agents-title">
          <span className="run-status-dot dot-live" />
          Active agents
          <span className="running-agents-count">
            {runs.length}
            {limit > 0 ? ` / ${limit}` : ''}
          </span>
        </span>
        <span className="fleet-header-actions">
          {onRefresh && (
            <button type="button" className="running-agents-refresh" onClick={onRefresh} title="Refresh">
              Refresh
            </button>
          )}
        </span>
      </header>

      <ul className="running-agents-list">
        {runs.map((run) => {
          const isActiveSession = run.session_id === activeSessionId;
          const isStopping = stoppingRunIds.includes(run.run_id);
          return (
            <li
              key={run.run_id}
              className={`running-agent-row ${isActiveSession ? 'running-agent-row-active' : ''}`}
            >
              <div className="running-agent-icon">
                <BotIcon size={15} />
              </div>
              <div className="running-agent-info">
                <span className="running-agent-name">
                  {humanizeAgentId(run.agent_id)}
                  <span className="running-agent-origin">· {originLabel(run.origin)}</span>
                </span>
                <span className="running-agent-session" title={titleFor(run)}>
                  {titleFor(run)}
                </span>
              </div>
              <span className="running-agent-elapsed">{elapsedLabel(run)}</span>
              {run.session_id && !isActiveSession && run.origin !== 'spawn' && (
                <button
                  type="button"
                  className="running-agent-open"
                  onClick={() => run.session_id && onOpenSession(run.session_id)}
                  title="Open this conversation"
                >
                  <PlayIcon size={12} />
                  <span>Open</span>
                </button>
              )}
              <button
                type="button"
                className="running-agent-stop run-stop-btn"
                onClick={() => onStopRun(run.run_id)}
                disabled={isStopping}
                title="Stop this agent run"
              >
                <CloseIcon size={12} />
                <span>{isStopping ? 'Stopping…' : 'Stop'}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
};
