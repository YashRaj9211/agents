import React from 'react';
import {
  HomeIcon,
  StudioIcon,
  UsersIcon,
  FolderIcon,
  GridIcon,
  BellIcon,
  SettingsIcon,
  ChevronDownIcon,
  BotIcon,
  TerminalIcon,
  SparkleIcon
} from '../icons/Icons';
import { ExpandableDock } from './ExpandableDock';
import type { AgentInfo } from '../../services/api';
import type { UserProfile } from '../../store';

export interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  badge?: number | string;
}

interface SidebarProps {
  activeTab: string;
  onSelectTab: (id: string) => void;
  selectedAgent: string;
  onSelectAgent: (agentId: string) => void;
  agents?: AgentInfo[];
  user?: UserProfile;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  selectedAgent,
  onSelectAgent,
  agents = [],
  user = { name: 'Allison', handle: '@allison_4_li', initials: 'AL' }
}) => {
  const mainNavItems: NavItem[] = [
    { id: 'home', label: 'Home', icon: <HomeIcon /> },
    { id: 'orchestrator', label: 'Orchestrator', icon: <StudioIcon /> },
    { id: 'agents', label: 'Agent Fleet', icon: <UsersIcon /> },
    { id: 'jobs', label: 'Job Hunt', icon: <SparkleIcon size={18} /> },
    { id: 'artifacts', label: 'Artifacts', icon: <FolderIcon /> },
    { id: 'logs', label: 'Run Logs', icon: <GridIcon /> },
    { id: 'notifications', label: 'Notifications', icon: <BellIcon />, badge: 3 },
    { id: 'settings', label: 'Settings', icon: <SettingsIcon /> },
  ];

  const getAgentIcon = (id: string) => {
    if (id.includes('root')) return <SparkleIcon size={16} />;
    if (id.includes('cli')) return <TerminalIcon size={16} />;
    return <BotIcon size={16} />;
  };

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="brand-header">
        <div className="brand-logo-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <span className="brand-title">AGENTS</span>
      </div>

      {/* Sub-Agents Section from Props/Store */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <span>Active Agents</span>
          <ChevronDownIcon size={14} />
        </div>
        <div className="agent-list">
          {agents.map((ag) => {
            const isSelected = selectedAgent === ag.id;
            return (
              <button
                key={ag.id}
                type="button"
                className={`agent-item-btn ${isSelected ? 'agent-item-active' : ''}`}
                onClick={() => onSelectAgent(ag.id)}
              >
                <div className="agent-item-icon">{getAgentIcon(ag.id)}</div>
                <div className="agent-item-info">
                  <span className="agent-item-name">{ag.name}</span>
                  <span className="agent-item-desc">{ag.description}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Expandable bottom dock: 3 pinned tabs + plus that opens the full grid */}
      <div className="sidebar-footer">
        <ExpandableDock items={mainNavItems} activeId={activeTab} onSelect={onSelectTab} />

        <div className="user-profile-card">
          <div className="user-profile-avatar-wrap">
            <div className="user-profile-avatar">
              <span>{user.initials}</span>
            </div>
          </div>
          <div className="user-profile-details">
            <span className="user-profile-name">{user.name}</span>
            <span className="user-profile-handle">{user.handle}</span>
          </div>
          <button type="button" className="user-profile-action" title="Settings">
            <SparkleIcon size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
};
