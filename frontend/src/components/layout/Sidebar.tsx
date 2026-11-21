import React from 'react';
import { PlusIcon, PanelLeftIcon } from '../icons/Icons';
import { ChatHistorySidebar, type ChatSession } from '../chat/ChatHistorySidebar';
import type { AgentInfo } from '../../services/api';

interface SidebarProps {
  activeTab: string;
  onSelectTab: (id: string) => void;
  agents: AgentInfo[];
  selectedAgent: string;
  onSelectAgent: (id: string) => void;
  backendOnline: boolean | null;
  onNewChat: () => void;
  onCollapse: () => void;
  open: boolean;

  sessions: ChatSession[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onRenameSession: (id: string, title: string) => void;
  onDeleteSession: (id: string) => void;
}

const TABS = [
  { id: 'home', label: 'Chat' },
  { id: 'jobs', label: 'Job Hunt' },
  { id: 'artifacts', label: 'Artifacts' },
];

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  agents,
  selectedAgent,
  onSelectAgent,
  backendOnline,
  onNewChat,
  onCollapse,
  open,
  sessions,
  activeSessionId,
  onSelectSession,
  searchQuery,
  onSearchChange,
  onRenameSession,
  onDeleteSession,
}) => {
  const isChat = activeTab !== 'jobs' && activeTab !== 'artifacts';

  return (
    <aside className={`sidebar ${open ? 'is-open' : ''}`} aria-hidden={!open} inert={!open}>
      <div className="sidebar-inner">
      <div className="sidebar-brand">
        <span
          className={`sidebar-status ${backendOnline === false ? 'is-offline' : 'is-online'}`}
          title={backendOnline === false ? 'Backend offline' : 'Backend online'}
        />
        Agents
        <button type="button" className="panel-toggle sidebar-collapse" onClick={onCollapse} title="Hide sidebar" aria-label="Hide sidebar">
          <PanelLeftIcon size={16} />
        </button>
      </div>

      <button
        type="button"
        className="sidebar-new"
        onClick={() => {
          onSelectTab('home');
          onNewChat();
        }}
      >
        <PlusIcon size={14} />
        New chat
      </button>

      <nav className="sidebar-nav" aria-label="Primary">
        {TABS.map((tab) => {
          const active = tab.id === 'home' ? isChat : activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              className={`sidebar-tab ${active ? 'is-active' : ''}`}
              onClick={() => onSelectTab(tab.id)}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-history">
        <ChatHistorySidebar
          sessions={sessions}
          activeSessionId={isChat ? activeSessionId : ''}
          onSelectSession={(id) => {
            onSelectTab('home');
            onSelectSession(id);
          }}
          searchQuery={searchQuery}
          onSearchChange={onSearchChange}
          onRenameSession={onRenameSession}
          onDeleteSession={onDeleteSession}
        />
      </div>

      {agents.length > 0 && (
        <div className="sidebar-footer">
          <label className="sidebar-agent">
            <span>Agent</span>
            <select value={selectedAgent} onChange={(e) => onSelectAgent(e.target.value)}>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
      </div>
    </aside>
  );
};
