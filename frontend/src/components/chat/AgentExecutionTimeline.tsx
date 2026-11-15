import React, { useState } from 'react';
import { BotIcon, SparkleIcon, GlobeIcon, TerminalIcon } from '../icons/Icons';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { TimelineEventItem } from '../../services/api';

interface AgentExecutionTimelineProps {
  events: TimelineEventItem[];
}

export const AgentExecutionTimeline: React.FC<AgentExecutionTimelineProps> = ({ events }) => {
  const [isOpen, setIsOpen] = useState(true);

  if (!events || events.length === 0) return null;

  const getIcon = (title: string, type: string) => {
    if (type === 'agent_transfer') return <SparkleIcon size={14} />;
    if (title.includes('firecrawl') || title.includes('scrape') || title.includes('browser')) return <GlobeIcon size={14} />;
    if (title.includes('cli') || title.includes('terminal')) return <TerminalIcon size={14} />;
    return <BotIcon size={14} />;
  };

  return (
    <div className="timeline-container" style={{ width: '100%' }}>
      <div 
        className="timeline-header" 
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="timeline-header-dot"></span>
          <span className="timeline-header-title">Live Execution Flow</span>
        </div>
        {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </div>

      {isOpen && (
        <div className="timeline-track">
        {events.map((evt) => {
          const isTransfer = evt.type === 'agent_transfer';
          const isRunning = evt.status === 'running';

          return (
            <div
              key={evt.id}
              className={`timeline-item timeline-type-${evt.type} timeline-status-${evt.status}`}
            >
              <div className="timeline-node">
                <span className="timeline-icon">{getIcon(evt.title, evt.type)}</span>
                {isRunning && <span className="timeline-pulse"></span>}
              </div>

              <div className="timeline-content">
                <div className="timeline-content-row">
                  <span className={`timeline-title ${isTransfer ? 'timeline-title-transfer' : ''}`}>
                    {evt.title}
                  </span>
                  <span className={`timeline-badge timeline-badge-${evt.status}`}>
                    {evt.status}
                  </span>
                  <span className="timeline-time">{evt.timestamp}</span>
                </div>
                {evt.description && (
                  <p className="timeline-description">{evt.description}</p>
                )}
              </div>
            </div>
          );
        })}
        </div>
      )}
    </div>
  );
};
