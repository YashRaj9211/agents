import React, { useState } from 'react';
import { SearchIcon, PlusIcon, TrashIcon, EditIcon, CheckIcon, CloseIcon, RefreshIcon } from '../icons/Icons';
import { TextInput, Button } from '../common';

export interface ChatSession {
  id: string;
  title: string;
  preview: string;
  timeAgo: string;
  agent: string;
  thumbnail?: string;
  avatars?: string[];
  unread?: boolean;
  /** True while this conversation has an agent run executing. */
  running?: boolean;
  /** The run currently executing for this conversation, when known. */
  runId?: string;
  /** Agent driving the live run, when known. */
  runAgent?: string;
}

interface ChatHistorySidebarProps {
  sessions: ChatSession[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onRenameSession?: (id: string, newTitle: string) => void;
  onDeleteSession?: (id: string) => void;
  onRefresh?: () => void;
}

export const ChatHistorySidebar: React.FC<ChatHistorySidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  searchQuery,
  onSearchChange,
  onRenameSession,
  onDeleteSession,
  onRefresh
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const filtered = sessions.filter(
    (s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.preview.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const startEditing = (e: React.MouseEvent, session: ChatSession) => {
    e.stopPropagation();
    setEditingId(session.id);
    setEditTitle(session.title);
  };

  const cancelEditing = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setEditingId(null);
    setEditTitle('');
  };

  const saveEditing = (e: React.MouseEvent | React.KeyboardEvent, id: string) => {
    e.stopPropagation();
    if (editTitle.trim() && onRenameSession) {
      onRenameSession(id, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirmDeleteId === id) {
      if (onDeleteSession) onDeleteSession(id);
      setConfirmDeleteId(null);
    } else {
      setConfirmDeleteId(id);
      // Auto-revert confirmation after 4s
      setTimeout(() => {
        setConfirmDeleteId((cur) => (cur === id ? null : cur));
      }, 4000);
    }
  };

  return (
    <aside className="chat-history-sidebar">
      {/* Header */}
      <div className="history-header">
        <h3 className="history-title">Chat history</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              className="history-header-btn"
              title="Refresh sessions from backend"
            >
              <RefreshIcon size={14} />
            </button>
          )}
          <button
            type="button"
            onClick={onNewChat}
            className="history-header-btn"
            title="New conversation"
          >
            <PlusIcon size={16} />
          </button>
        </div>
      </div>

      {/* Search Input */}
      <div className="history-search-container">
        <TextInput
          placeholder="Search..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          icon={<SearchIcon size={15} />}
          clearable
          onClear={() => onSearchChange('')}
        />
      </div>

      {/* History Items List */}
      <div className="history-list">
        {filtered.map((session) => {
          const isActive = session.id === activeSessionId;
          const isEditing = editingId === session.id;
          const isConfirmingDelete = confirmDeleteId === session.id;

          return (
            <div
              key={session.id}
              className={`history-card ${isActive ? 'history-card-active' : ''}`}
              onClick={() => !isEditing && onSelectSession(session.id)}
            >
              <div className="history-card-header">
                {isEditing ? (
                  <div
                    className="history-card-edit-wrap"
                    onClick={(e) => e.stopPropagation()}
                    style={{ display: 'flex', alignItems: 'center', gap: '4px', width: '100%' }}
                  >
                    <input
                      type="text"
                      className="history-inline-edit-input"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveEditing(e, session.id);
                        if (e.key === 'Escape') cancelEditing();
                      }}
                      autoFocus
                    />
                    <button
                      type="button"
                      className="history-card-action-btn btn-save"
                      onClick={(e) => saveEditing(e, session.id)}
                      title="Save"
                    >
                      <CheckIcon size={13} />
                    </button>
                    <button
                      type="button"
                      className="history-card-action-btn btn-cancel"
                      onClick={(e) => cancelEditing(e)}
                      title="Cancel"
                    >
                      <CloseIcon size={13} />
                    </button>
                  </div>
                ) : (
                  <>
                    <span className="history-card-title" title={session.title}>
                      {session.title}
                    </span>
                    <div className="history-card-actions">
                      <span className="history-card-time">{session.timeAgo}</span>
                      {onRenameSession && (
                        <button
                          type="button"
                          className="history-card-action-btn"
                          onClick={(e) => startEditing(e, session)}
                          title="Rename session"
                        >
                          <EditIcon size={12} />
                        </button>
                      )}
                      {onDeleteSession && (
                        <button
                          type="button"
                          className={`history-card-action-btn ${isConfirmingDelete ? 'btn-delete-confirm' : ''}`}
                          onClick={(e) => handleDelete(e, session.id)}
                          title={isConfirmingDelete ? 'Click again to confirm delete' : 'Delete session'}
                        >
                          <TrashIcon size={12} />
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>

              {!isEditing && (
                <p className="history-card-preview">{session.preview}</p>
              )}

              {/* Optional image preview */}
              {session.thumbnail && !isEditing && (
                <div className="history-card-media">
                  <img src={session.thumbnail} alt={session.title} />
                </div>
              )}

              {/* Avatars row or Agent badge */}
              <div className="history-card-footer">
                <div className="history-card-tag">{session.agent}</div>
                {session.running && (
                  <span className="history-card-running-tag" title={`Running${session.runAgent ? ` · ${session.runAgent}` : ''}`}>
                    <span className="run-status-dot dot-live" />
                    Running
                  </span>
                )}
                {session.avatars && (
                  <div className="history-card-avatars">
                    {session.avatars.map((initial, idx) => (
                      <span key={idx} className="avatar-chip">
                        {initial}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="history-empty-state">
            <p>No conversations found</p>
          </div>
        )}
      </div>

      {/* Create New Chat primary action button */}
      <div className="history-footer">
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onClick={onNewChat}
          className="create-chat-button"
        >
          Create new chat
        </Button>
      </div>
    </aside>
  );
};
