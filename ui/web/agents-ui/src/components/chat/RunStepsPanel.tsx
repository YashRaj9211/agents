import React, { useEffect, useRef, useState } from 'react';
import { ChevronDownIcon } from '../icons/Icons';
import { StepRow } from './StepRow';
import { formatElapsed } from '../../utils/time';
import type { RunStep } from '../../store/chatStore';

interface RunStepsPanelProps {
  steps: RunStep[];
  expanded: boolean;
  isRunning: boolean;
  isWaitingForHuman: boolean;
  /** When the current turn began, for the elapsed-time readout. */
  startedAt: number | null;
  hasError?: boolean;
  onToggleExpanded: () => void;
  onToggleStep: (stepKey: string) => void;
}

/**
 * The collapsible steps container docked directly above the chat textarea.
 *
 * Collapsed it is a single header line describing the run; expanded it lists one
 * line per agent action, each of which can reveal its command and output. It is
 * deliberately always present (rather than behind a header toggle) so the user
 * can see what an agent is doing without asking for it.
 */
export const RunStepsPanel: React.FC<RunStepsPanelProps> = ({
  steps,
  expanded,
  isRunning,
  isWaitingForHuman,
  startedAt,
  hasError = false,
  onToggleExpanded,
  onToggleStep
}) => {
  // `now` is the only state: elapsed is derived from it, so there is no state to
  // reset when a run starts or ends.
  const [now, setNow] = useState(() => Date.now());
  const tickRef = useRef<number | null>(null);

  const active = isRunning || isWaitingForHuman;

  // Tick only while something is actually happening, so an idle page is not
  // re-rendering every second.
  useEffect(() => {
    if (!active) {
      if (tickRef.current !== null) {
        window.clearInterval(tickRef.current);
        tickRef.current = null;
      }
      return;
    }
    tickRef.current = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      if (tickRef.current !== null) {
        window.clearInterval(tickRef.current);
        tickRef.current = null;
      }
    };
  }, [active]);

  const elapsedSeconds =
    startedAt === null ? 0 : Math.max(0, Math.floor((now - startedAt) / 1000));

  const runningCount = steps.filter((s) => s.status === 'running').length;
  const failedCount = steps.filter((s) => s.status === 'failed').length;
  const latest = steps.length > 0 ? steps[steps.length - 1] : null;

  const state = isWaitingForHuman
    ? 'waiting'
    : failedCount > 0 || hasError
      ? 'failed'
      : isRunning
        ? 'running'
        : 'idle';

  const title = isWaitingForHuman
    ? 'Waiting for your input'
    : isRunning
      ? 'Running steps'
      : steps.length === 0
        ? 'Steps'
        : `${steps.length} step${steps.length === 1 ? '' : 's'}`;

  // Collapsed, the header still shows what is happening right now.
  const collapsedSummary =
    latest && !expanded
      ? `${latest.label}${latest.detail ? ` · ${latest.detail}` : ''}`
      : null;

  return (
    <section
      className={`run-steps-panel run-steps-panel-${state}`}
      aria-label="Agent execution steps"
    >
      <button
        type="button"
        className="run-steps-header"
        onClick={onToggleExpanded}
        aria-expanded={expanded}
        aria-controls="run-steps-body"
      >
        <span className={`run-steps-dot run-steps-dot-${state}`} />

        <span className="run-steps-title">{title}</span>

        {collapsedSummary && (
          <span className="run-steps-collapsed-summary">{collapsedSummary}</span>
        )}

        <span className="run-steps-header-meta">
          {(isRunning || isWaitingForHuman) && (
            <span className="run-steps-elapsed">{formatElapsed(elapsedSeconds)}</span>
          )}
          {runningCount > 0 && (
            <span className="run-steps-count">{runningCount} running</span>
          )}
          {failedCount > 0 && (
            <span className="run-steps-count run-steps-count-failed">{failedCount} failed</span>
          )}
          <span className={`run-steps-chevron${expanded ? ' run-steps-chevron-up' : ''}`}>
            <ChevronDownIcon size={15} />
          </span>
        </span>
      </button>

      {expanded && (
        <div className="run-steps-body" id="run-steps-body">
          {steps.length === 0 ? (
            <p className="run-steps-empty">No steps yet for this session.</p>
          ) : (
            <div className="run-steps-list">
              {steps.map((step) => (
                <StepRow key={step.stepKey} step={step} onToggle={onToggleStep} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
};
