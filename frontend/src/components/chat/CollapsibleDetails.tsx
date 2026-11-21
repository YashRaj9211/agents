import React, { useState } from 'react';
import { ChevronDownIcon, SparkleIcon } from '../icons/Icons';

interface CollapsibleDetailsProps {
  title?: string;
  thoughtProcess?: string;
  rawText?: string;
  defaultExpanded?: boolean;
}

export const CollapsibleDetails: React.FC<CollapsibleDetailsProps> = ({
  title = 'View thought process & agent reasoning',
  thoughtProcess,
  rawText,
  defaultExpanded = false
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!thoughtProcess && !rawText) return null;

  return (
    <div className={`collapsible-wrapper ${isExpanded ? 'collapsible-open' : 'collapsible-closed'}`}>
      <button
        type="button"
        className="collapsible-trigger"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
      >
        <span className="collapsible-icon-wrap">
          <SparkleIcon size={14} />
        </span>
        <span className="collapsible-label">{title}</span>
        <span className={`collapsible-arrow ${isExpanded ? 'collapsible-arrow-up' : ''}`}>
          <ChevronDownIcon size={14} />
        </span>
      </button>

      {isExpanded && (
        <div className="collapsible-body">
          {thoughtProcess && (
            <div className="thought-section">
              <span className="section-subtitle">Agent Thought Process</span>
              <pre className="thought-code-block">{thoughtProcess}</pre>
            </div>
          )}

          {rawText && rawText !== thoughtProcess && (
            <div className="thought-section">
              <span className="section-subtitle">Raw Output Logs</span>
              <pre className="thought-code-block raw-code-block">{rawText}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
