import React, { useState } from 'react';
import type { AdkEvent } from '../../services/adkClient';

interface EventInspectorProps {
  events: AdkEvent[];
  isOpen: boolean;
  onClose: () => void;
}

const EVENT_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
  text: {
    bg: 'bg-[#EFF6FF]',
    text: 'text-[#1D4ED8]',
    border: 'border-[#BFDBFE]',
    label: 'TEXT',
  },
  tool_call: {
    bg: 'bg-[#FFF7ED]',
    text: 'text-[#C2410C]',
    border: 'border-[#FED7AA]',
    label: 'TOOL CALL',
  },
  tool_result: {
    bg: 'bg-[#F0FDF4]',
    text: 'text-[#15803D]',
    border: 'border-[#BBF7D0]',
    label: 'TOOL RESULT',
  },
  agent_transfer: {
    bg: 'bg-[#FAF5FF]',
    text: 'text-[#7E22CE]',
    border: 'border-[#E9D5FF]',
    label: 'TRANSFER',
  },
  error: {
    bg: 'bg-[#FEF2F2]',
    text: 'text-[#DC2626]',
    border: 'border-[#FECACA]',
    label: 'ERROR',
  },
  status: {
    bg: 'bg-[#F9F9F9]',
    text: 'text-[#6B7280]',
    border: 'border-[#E5E7EB]',
    label: 'STATUS',
  },
};

const CollapseIcon: React.FC<{ open: boolean }> = ({ open }) => (
  <svg
    width="12"
    height="12"
    viewBox="0 0 12 12"
    fill="none"
    className={`transition-transform ${open ? 'rotate-90' : ''}`}
  >
    <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const EventRow: React.FC<{ event: AdkEvent; index: number }> = ({ event, index }) => {
  const [expanded, setExpanded] = useState(false);
  const type = event._type ?? 'status';
  const colors = EVENT_COLORS[type] ?? EVENT_COLORS['status'];

  const ts = event.timestamp
    ? new Date(event.timestamp * 1000).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : '';

  return (
    <div className={`border rounded-lg overflow-hidden ${colors.border}`}>
      <button
        className={`w-full flex items-center gap-2 px-3 py-2 text-left ${colors.bg} hover:opacity-90 transition-opacity`}
        onClick={() => setExpanded((p) => !p)}
        id={`event-row-${index}`}
      >
        <CollapseIcon open={expanded} />
        <span className={`typography-micro font-bold uppercase ${colors.text}`}>{colors.label}</span>
        <span className="typography-micro text-[#374151] flex-1 truncate ml-1">
          {event.author}
          {event.actions?.transfer_to_agent
            ? ` → ${event.actions.transfer_to_agent}`
            : ''}
        </span>
        {ts && (
          <span className="typography-micro text-[#9CA3AF] shrink-0">{ts}</span>
        )}
        {event.partial && (
          <span className="typography-micro text-[#9CA3AF] shrink-0 italic">partial</span>
        )}
      </button>

      {expanded && (
        <pre
          className={`text-[10px] font-mono p-3 overflow-x-auto max-h-64 overflow-y-auto ${colors.bg} border-t ${colors.border} whitespace-pre-wrap break-all`}
        >
          {JSON.stringify(event, null, 2)}
        </pre>
      )}
    </div>
  );
};

export const EventInspector: React.FC<EventInspectorProps> = ({ events, isOpen, onClose }) => {
  if (!isOpen) return null;

  const counts = events.reduce<Record<string, number>>((acc, e) => {
    const t = e._type ?? 'status';
    acc[t] = (acc[t] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <aside className="flex flex-col w-80 shrink-0 border-l border-[#E5E7EB] bg-[#FAFAFA] h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#E5E7EB]">
        <div>
          <p className="typography-label-md text-[#262626]">Event Inspector</p>
          <p className="typography-micro text-[#9CA3AF] mt-0.5">{events.length} events</p>
        </div>
        <button
          id="close-inspector-btn"
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-[#F3F4F6] text-[#6B7280] transition-colors"
          title="Close inspector"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path
              d="M1 1l12 12M13 1L1 13"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>

      {/* Type summary pills */}
      {Object.keys(counts).length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-3 py-2 border-b border-[#E5E7EB]">
          {Object.entries(counts).map(([type, count]) => {
            const c = EVENT_COLORS[type] ?? EVENT_COLORS['status'];
            return (
              <span key={type} className={`${c.bg} ${c.text} border ${c.border} rounded-full px-2 py-0.5 typography-micro font-bold`}>
                {c.label} {count}
              </span>
            );
          })}
        </div>
      )}

      {/* Event list */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
        {events.length === 0 && (
          <p className="text-center typography-body-sm text-[#9CA3AF] py-8">
            No events yet.
          </p>
        )}
        {[...events].reverse().map((evt, i) => (
          <EventRow key={`${evt.id ?? ''}-${i}`} event={evt} index={i} />
        ))}
      </div>
    </aside>
  );
};

export default EventInspector;
