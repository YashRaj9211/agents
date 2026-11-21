import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Card } from '../common';
import { CheckIcon, CloseIcon, SparkleIcon } from '../icons/Icons';
import type { HumanInputAnswer, HumanInputRequest } from '../../services/api';

interface HumanInputCardProps {
  request: HumanInputRequest;
  isSubmitting?: boolean;
  error?: string | null;
  onSubmit: (answer: HumanInputAnswer) => void;
}

const KIND_LABEL: Record<HumanInputRequest['kind'], string> = {
  confirm: 'Confirmation needed',
  choice: 'Choose one',
  multi_choice: 'Choose one or more',
  text: 'Your input is needed'
};

/**
 * The question card an agent blocks on.
 *
 * Rendered from the `human_input_request` event (or from the pending endpoint on
 * reload), so the card is present whenever the run is genuinely paused. Submitting
 * resolves the run's outstanding future and the agent continues on its existing
 * stream -- no new run is created.
 */
export const HumanInputCard: React.FC<HumanInputCardProps> = ({
  request,
  isSubmitting = false,
  error = null,
  onSubmit
}) => {
  const [text, setText] = useState('');
  const [selected, setSelected] = useState<string[]>([]);

  const options = useMemo(() => request.options || [], [request.options]);
  // Submitting disables the controls. The parent keys this card by question id, so
  // a retry after a failed POST gets a fresh card rather than a stuck one.
  const busy = isSubmitting;

  const submit = useCallback(
    (answer: HumanInputAnswer) => {
      if (busy) return;
      onSubmit(answer);
    },
    [busy, onSubmit]
  );

  const toggleOption = (value: string) => {
    setSelected((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  };

  // Yes/No and Enter shortcuts for the common confirm case, mirroring how the
  // harness answers a permission prompt. Ignored while typing so a "y" inside a
  // text box is just a letter.
  useEffect(() => {
    if (request.kind !== 'confirm' || busy) return;

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;
      if (event.key === 'y' || event.key === 'Y') {
        event.preventDefault();
        submit(text.trim() ? `Yes — ${text.trim()}` : true);
      } else if (event.key === 'n' || event.key === 'N') {
        event.preventDefault();
        submit(text.trim() ? `No — ${text.trim()}` : false);
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [request.kind, busy, submit, text]);

  return (
    <Card
      variant="elevated"
      padding="none"
      className={`hitl-card hitl-card-${request.kind}${busy ? ' hitl-card-busy' : ''}`}
      role="group"
      aria-label="Question from the agent"
    >
      <div className="hitl-card-header">
        <span className="hitl-card-icon">
          <SparkleIcon size={15} />
        </span>
        <div className="hitl-card-header-text">
          <span className="hitl-card-kicker">
            {KIND_LABEL[request.kind] || 'Input needed'}
            {request.agent_id ? ` · ${request.agent_id.replace(/_/g, ' ')}` : ''}
          </span>
          <p className="hitl-card-question">{request.question}</p>
        </div>
      </div>

      <div className="hitl-card-body">
        {request.kind === 'confirm' && (
          <>
            <div className="hitl-confirm-actions">
              <Button
                type="button"
                variant="primary"
                size="sm"
                icon={<CheckIcon size={14} />}
                onClick={() => submit(text.trim() ? `Yes — ${text.trim()}` : true)}
                disabled={busy}
              >
                Yes
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<CloseIcon size={14} />}
                onClick={() => submit(text.trim() ? `No — ${text.trim()}` : false)}
                disabled={busy}
              >
                No
              </Button>
              <span className="hitl-shortcut-hint">Y / N</span>
            </div>
            <input
              type="text"
              className="hitl-text-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Add detail (optional)"
              disabled={busy}
              aria-label="Optional detail for your answer"
            />
          </>
        )}

        {request.kind === 'choice' && (
          <div className="hitl-options">
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                className="hitl-option"
                onClick={() => submit(option.value)}
                disabled={busy}
              >
                <span className="hitl-option-label">{option.label}</span>
                {option.description && (
                  <span className="hitl-option-description">{option.description}</span>
                )}
              </button>
            ))}
          </div>
        )}

        {request.kind === 'multi_choice' && (
          <div className="hitl-options">
            {options.map((option) => {
              const checked = selected.includes(option.value);
              return (
                <label
                  key={option.value}
                  className={`hitl-option hitl-option-checkable${checked ? ' hitl-option-checked' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleOption(option.value)}
                    disabled={busy}
                  />
                  <span className="hitl-option-label">{option.label}</span>
                  {option.description && (
                    <span className="hitl-option-description">{option.description}</span>
                  )}
                </label>
              );
            })}
            <div className="hitl-multi-actions">
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => submit(selected)}
                disabled={busy || selected.length === 0}
              >
                Submit {selected.length > 0 ? `(${selected.length})` : ''}
              </Button>
            </div>
          </div>
        )}

        {request.kind === 'text' && (
          <div className="hitl-text-actions">
            <textarea
              className="hitl-textarea"
              rows={3}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type your answer..."
              disabled={busy}
              aria-label="Your answer"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (text.trim()) submit(text.trim());
                }
              }}
            />
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => submit(text.trim())}
              disabled={busy || !text.trim()}
            >
              Send answer
            </Button>
          </div>
        )}

        {isSubmitting && <p className="hitl-card-status">Sending your answer...</p>}
        {error && <p className="hitl-card-status hitl-card-status-error">{error}</p>}
      </div>
    </Card>
  );
};
