import React from 'react';
import { Badge, Card } from '../common';
import {
  ActivityIcon,
  BotIcon,
  ChevronDownIcon,
  FileIcon,
  GlobeIcon,
  SparkleIcon,
  TerminalIcon
} from '../icons/Icons';
import type { RunStep } from '../../store/chatStore';
import { formatDuration, cleanStepDetail } from '../../utils/steps';

interface StepRowProps {
  step: RunStep;
  onToggle?: (stepKey: string) => void;
}

/** Picks an icon from the step's category, falling back to a generic tool icon. */
function StepIcon({ step }: { step: RunStep }) {
  if (step.type === 'agent_transfer') return <SparkleIcon size={14} />;
  if (step.type === 'human_input') return <ActivityIcon size={14} />;
  const haystack = `${step.label} ${step.detail || ''}`.toLowerCase();
  if (haystack.includes('browser') || haystack.includes('scrape') || haystack.includes('http')) {
    return <GlobeIcon size={14} />;
  }
  if (/command|powershell|python|shell|terminal|cli/.test(haystack)) {
    return <TerminalIcon size={14} />;
  }
  if (/file|path|directory|artifact|garage|resume|pdf/.test(haystack)) {
    return <FileIcon size={14} />;
  }
  return <BotIcon size={14} />;
}

/**
 * One agent action, rendered as a single collapsible line.
 *
 * Collapsed it is exactly one line (icon, label, status, duration) as the steps
 * panel is meant to be scannable; expanded it reveals the command/target that
 * actually ran plus any captured output.
 */
export const StepRow: React.FC<StepRowProps> = ({ step, onToggle }) => {
  const hasDetail = Boolean(step.detail || step.output);
  const duration = formatDuration(step.durationMs);
  const isRunning = step.status === 'running';

  // Steps with nothing to reveal are not interactive.
  const interactive = hasDetail && Boolean(onToggle);
  const expanded = interactive && Boolean(step.expanded);

  const badgeVariant =
    step.status === 'completed' ? 'success' : step.status === 'failed' ? 'warning' : 'purple';

  const handleToggle = () => {
    if (interactive) onToggle?.(step.stepKey);
  };

  return (
    <Card
      variant="flat"
      padding="none"
      className={`run-step-row run-step-${step.status}${expanded ? ' run-step-expanded' : ''}`}
    >
      <button
        type="button"
        className="run-step-line"
        onClick={handleToggle}
        aria-expanded={interactive ? expanded : undefined}
        aria-controls={interactive ? `step-detail-${step.stepKey}` : undefined}
        disabled={!interactive}
      >
        <span className="run-step-icon">
          <StepIcon step={step} />
          {isRunning && <span className="timeline-pulse" />}
        </span>

        <span className="run-step-label">{step.label}</span>
        {step.tool && <code className="run-step-tool">{step.tool}</code>}

        {cleanStepDetail(step.detail) && !expanded && (
          <span className="run-step-inline-detail" title={cleanStepDetail(step.detail)}>
            {cleanStepDetail(step.detail)}
          </span>
        )}

        <span className="run-step-meta">
          {duration && <span className="run-step-duration">{duration}</span>}
          <Badge variant={badgeVariant} size="sm">
            {isRunning ? 'running' : step.status === 'completed' ? 'done' : 'failed'}
          </Badge>
          {interactive && (
            <span className={`run-step-chevron${expanded ? ' run-step-chevron-up' : ''}`}>
              <ChevronDownIcon size={13} />
            </span>
          )}
        </span>
      </button>

      {expanded && (
        <div className="run-step-detail" id={`step-detail-${step.stepKey}`}>
          {step.tool && (
            <div className="run-step-detail-block">
              <span className="run-step-detail-title">Tool</span>
              <pre className="run-step-code">{step.tool}</pre>
            </div>
          )}
          {step.detail && (
            <div className="run-step-detail-block">
              <span className="run-step-detail-title">Input</span>
              <pre className="run-step-code">{step.detail}</pre>
            </div>
          )}
          {step.output && (
            <div className="run-step-detail-block">
              <span className="run-step-detail-title">Output</span>
              <pre className="run-step-code run-step-output">{step.output}</pre>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
