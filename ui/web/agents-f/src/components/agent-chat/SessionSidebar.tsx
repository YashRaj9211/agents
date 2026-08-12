import React from 'react';
import type { AdkSession } from '../../services/adkClient';

interface SessionSidebarProps {
  sessions: AdkSession[];
  activeSessionId: string | null;
  userId: string;
  isLoading: boolean;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
}

function formatTime(timestamp?: number): string {
  if (!timestamp) return '';
  const d = new Date(timestamp * 1000);
  const now = new Date();
  const sameDay =
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export const SessionSidebar: React.FC<SessionSidebarProps> = ({
  sessions,
  activeSessionId,
  userId,
  isLoading,
  onSelectSession,
  onNewSession,
}) => {
  return (
    <aside className="flex flex-col w-64 shrink-0 border-r border-[#E5E7EB] bg-[#FAFAFA] h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#E5E7EB]">
        <div>
          <p className="typography-label-md text-[#262626]">Sessions</p>
          <p className="typography-micro text-[#9CA3AF] mt-0.5 truncate max-w-[140px]">
            user: {userId}
          </p>
        </div>
        <button
          id="new-session-btn"
          onClick={onNewSession}
          disabled={isLoading}
          className="w-8 h-8 flex items-center justify-center rounded-lg bg-[#FA5D19] text-white hover:bg-[#FF6A2A] transition-colors disabled:opacity-50 shrink-0"
          title="New Session"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading && sessions.length === 0 && (
          <div className="px-4 py-3 text-center">
            <div className="inline-block w-4 h-4 border-2 border-[#FA5D19] border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!isLoading && sessions.length === 0 && (
          <p className="px-4 py-6 text-center typography-body-sm text-[#9CA3AF]">
            No sessions yet.
            <br />
            Click + to start.
          </p>
        )}

        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          const shortId = session.id.slice(0, 8);
          const msgCount = session.events?.length ?? 0;

          return (
            <button
              key={session.id}
              id={`session-${shortId}`}
              onClick={() => onSelectSession(session.id)}
              className={`w-full flex flex-col px-4 py-2.5 text-left transition-colors group ${
                isActive
                  ? 'bg-[#FA5D19]/10 border-r-2 border-[#FA5D19]'
                  : 'hover:bg-[#F3F4F6] border-r-2 border-transparent'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`typography-label-sm truncate ${isActive ? 'text-[#FA5D19]' : 'text-[#374151]'}`}
                >
                  Session {shortId}
                </span>
                <span className="typography-micro text-[#9CA3AF] shrink-0">
                  {formatTime(session.last_update_time)}
                </span>
              </div>
              <span className="typography-micro text-[#9CA3AF] mt-0.5">
                {msgCount} event{msgCount !== 1 ? 's' : ''}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
};

export default SessionSidebar;
