import React, { useState, useRef, useEffect } from 'react';
import {
  ArrowUpIcon,
  PaperclipIcon,
  CloseIcon,
  FileIcon,
  StopIcon
} from '../icons/Icons';
import { Button } from '../common';
import { uploadArtifactToGarage, type ApiArtifactItem } from '../../services/api';

interface ChatInputBarProps {
  onSendMessage: (text: string, attachedArtifacts?: ApiArtifactItem[]) => void;
  disabled?: boolean;
  /** True while a run is in flight; swaps the send button for a stop button. */
  isRunning?: boolean;
  onStop?: () => void;
  activeAgent?: string;
  sessionId?: string;
}

export const ChatInputBar: React.FC<ChatInputBarProps> = ({
  onSendMessage,
  disabled = false,
  isRunning = false,
  onStop,
  sessionId
}) => {
  const [inputText, setInputText] = useState('');
  const [attachedArtifacts, setAttachedArtifacts] = useState<ApiArtifactItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [inputText]);

  const handleAttachClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      const artifact = await uploadArtifactToGarage(file, sessionId);
      setAttachedArtifacts((prev) => [...prev, artifact]);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload to Garage S3');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemoveAttachment = (artId: string) => {
    setAttachedArtifacts((prev) => prev.filter((a) => a.id !== artId));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((!inputText.trim() && attachedArtifacts.length === 0) || disabled || isUploading) return;
    const msgText = inputText.trim() || `[Attached ${attachedArtifacts.map((a) => a.name).join(', ')}]`;
    onSendMessage(msgText, attachedArtifacts);
    setInputText('');
    setAttachedArtifacts([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <form className="chat-input-bar-container" onSubmit={handleSubmit}>
      {/* Hidden File Picker for Garage S3 Direct Upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      <div className="chat-input-bar-inner">
        {/* Attached Artifacts Chips stored in Garage */}
        {attachedArtifacts.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '8px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            {attachedArtifacts.map((art) => (
              <div
                key={art.id}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'rgba(59, 130, 246, 0.15)',
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                  color: '#93c5fd',
                  borderRadius: '16px',
                  padding: '4px 10px',
                  fontSize: '12px',
                }}
              >
                <FileIcon size={13} />
                <span style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {art.name}
                </span>
                <span style={{ opacity: 0.7, fontSize: '11px' }}>({formatSize(art.size_bytes)})</span>
                <button
                  type="button"
                  onClick={() => handleRemoveAttachment(art.id)}
                  style={{ background: 'none', border: 'none', color: '#93c5fd', cursor: 'pointer', padding: 0, display: 'flex' }}
                  title="Remove attachment"
                >
                  <CloseIcon size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Uploading Status / Error Indicator */}
        {isUploading && (
          <div style={{ padding: '6px 14px', fontSize: '12px', color: '#60a5fa' }}>
            Uploading…
          </div>
        )}
        {uploadError && (
          <div style={{ padding: '6px 14px', fontSize: '12px', color: '#f87171' }}>
            {uploadError}
          </div>
        )}

        <div className="chat-input-row">
          <textarea
            ref={textareaRef}
            rows={1}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything…"
            className="chat-textarea"
            disabled={disabled}
          />
        </div>

        <div className="chat-input-bottom-actions">
          <div className="chat-input-pill-actions">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={<PaperclipIcon size={14} />}
              className="chat-pill-btn"
              onClick={handleAttachClick}
              disabled={disabled || isUploading}
              title="Attach document or file"
            >
              {isUploading ? 'Uploading…' : 'Attach'}
            </Button>
          </div>

          <div className="chat-input-right-buttons">
            {isRunning && onStop ? (
              <button
                type="button"
                onClick={onStop}
                className="chat-submit-btn chat-submit-btn-ready chat-stop-btn"
                title="Stop response"
                aria-label="Stop response"
              >
                <StopIcon size={14} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={(!inputText.trim() && attachedArtifacts.length === 0) || disabled || isUploading}
                className={`chat-submit-btn ${inputText.trim() || attachedArtifacts.length > 0 ? 'chat-submit-btn-ready' : ''}`}
                title="Send message"
              >
                <ArrowUpIcon size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </form>
  );
};

