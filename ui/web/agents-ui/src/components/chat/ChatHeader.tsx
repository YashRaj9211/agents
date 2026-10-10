import React, { useState } from 'react';
import { BotIcon, EditIcon, CheckIcon, CloseIcon, TrashIcon, ActivityIcon, PlusIcon } from '../icons/Icons';
import { Badge } from '../common';

interface ChatHeaderProps {
  sessionTitle: string;
  agentName: string;
  isBackendOnline: boolean | null;
  timelineCount: number;
  showTimeline: boolean;
  onToggleTimeline: () => void;
  onRenameSession?: (newTitle: string) => void;
  onClearChat?: () => void;
  onNewChat?: () => void;
  hasMessages: boolean;
  /** The run executing for the visible conversation, when there is one. */
  runId?: string;
  /** True once the user has asked that run to stop. */
  isStoppingRun?: boolean;
  onStopRun?: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  sessionTitle,
  agentName,
  isBackendOnline,
  timelineCount,
  showTimeline,
  onToggleTimeline,
  onRenameSession,
  onClearChat,
  onNewChat,
  hasMessages,
  runId,
  isStoppingRun = false,
  onStopRun
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(sessionTitle);
  const [confirmClear, setConfirmClear] = useState(false);

  const handleStartEdit = () => {
    setEditTitle(sessionTitle);
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    if (editTitle.trim() && onRenameSession) {
      onRenameSession(editTitle.trim());
    }
    setIsEditing(false);
  };

  const handleClear = () => {
    if (confirmClear) {
      if (onClearChat) onClearChat();
      setConfirmClear(false);
    } else {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 4000);
    }
  };

  return (
    <div className="chat-top-header">
      <div className="chat-header-left">
        <div className="chat-header-agent-pill">
          <BotIcon size={16} />
          <span className="chat-header-agent-name">{agentName}</span>
          <span className={`status-indicator-dot ${isBackendOnline === false ? 'dot-offline' : 'dot-online'}`} />
        </div>

        <div className="chat-header-divider" />

        {isEditing ? (
          <div className="chat-header-edit-wrap">
            <input
              type="text"
              className="chat-header-title-input"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveEdit();
                if (e.key === 'Escape') setIsEditing(false);
              }}
              autoFocus
            />
            <button
              type="button"
              className="header-action-btn header-btn-confirm"
              onClick={handleSaveEdit}
              title="Save Title"
            >
              <CheckIcon size={14} />
            </button>
            <button
              type="button"
              className="header-action-btn header-btn-cancel"
              onClick={() => setIsEditing(false)}
              title="Cancel"
            >
              <CloseIcon size={14} />
            </button>
          </div>
        ) : (
          <div className="chat-header-title-wrap">
            <h2 className="chat-header-title" title={sessionTitle}>
              {sessionTitle || 'New Conversation'}
            </h2>
            {onRenameSession && (
              <button
                type="button"
                className="header-action-btn header-btn-edit"
                onClick={handleStartEdit}
                title="Rename conversation"
              >
                <EditIcon size={13} />
              </button>
            )}
          </div>
        )}
      </div>

      <div className="chat-header-right">
        {/* Toggle Timeline Drawer */}
        {/* Stop the run this conversation is executing, if any */}
        {runId && onStopRun && (
          <button
            type="button"
            className="chat-header-pill-btn run-stop-btn pill-btn-danger"
            onClick={onStopRun}
            disabled={isStoppingRun}
            title="Stop the agent running in this conversation"
          >
            <CloseIcon size={14} />
            <span>{isStoppingRun ? 'Stopping…' : 'Stop agent'}</span>
          </button>
        )}

        <button
          type="button"
          className={`chat-header-pill-btn ${showTimeline ? 'pill-btn-active' : ''}`}
          onClick={onToggleTimeline}
          title="Toggle execution timeline"
        >
          <ActivityIcon size={14} />
          <span>Timeline</span>
          {timelineCount > 0 && (
            <Badge variant="purple" size="sm">
              {timelineCount}
            </Badge>
          )}
        </button>

        {/* Clear chat */}
        {hasMessages && onClearChat && (
          <button
            type="button"
            className={`chat-header-pill-btn ${confirmClear ? 'pill-btn-danger' : ''}`}
            onClick={handleClear}
            title={confirmClear ? 'Click again to confirm clearing all messages' : 'Clear chat messages'}
          >
            <TrashIcon size={14} />
            <span>{confirmClear ? 'Confirm Clear?' : 'Clear'}</span>
          </button>
        )}

        {/* New chat */}
        {onNewChat && (
          <button
            type="button"
            className="chat-header-pill-btn"
            onClick={onNewChat}
            title="Start fresh conversation"
          >
            <PlusIcon size={14} />
            <span>New</span>
          </button>
        )}
      </div>
    </div>
  );
};
