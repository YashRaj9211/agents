import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BotIcon, SparkleIcon, TrashIcon } from '../icons/Icons';
import { Badge } from '../common';
import { CollapsibleDetails } from './CollapsibleDetails';
import type { TimelineEventItem } from '../../services/api';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  agentName?: string;
  text: string;
  timestamp: string;
  thoughtProcess?: string;
  rawText?: string;
  timelineEvents?: TimelineEventItem[];
  isStreaming?: boolean;
  /** Set when the user (or a peer agent) stopped this run before it finished. */
  cancelled?: boolean;
}

interface MessageListProps {
  messages: ChatMessage[];
  isThinking?: boolean;
  onDeleteMessage?: (messageId: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isThinking, onDeleteMessage }) => {
  return (
    <div className="message-list-container">
      {messages.map((msg) => {
        const isUser = msg.sender === 'user';

        let displayMain = msg.text;
        let displayThoughts = msg.thoughtProcess || '';
        let showPlaceholder = !msg.text;

        if (!isUser && msg.text) {
          const doneMatch = msg.text.match(/<DONE>([\s\S]*?)(?:<\/DONE>|$)/i);
          if (doneMatch) {
            displayMain = doneMatch[1].trim();
            const leftover = msg.text.replace(/<DONE>[\s\S]*?(?:<\/DONE>|$)/i, '').trim();
            displayThoughts = leftover + (displayThoughts ? '\n\n' + displayThoughts : '');
            showPlaceholder = !displayMain;
          } else {
            // Fallback: if there's no DONE tag, display it as main so it's not hidden
            displayMain = msg.text;
            showPlaceholder = false;
          }
        }

        return (
          <div
            key={msg.id}
            className={`message-row ${isUser ? 'message-row-user' : 'message-row-agent'}`}
          >
            {!isUser && (
              <div className="message-avatar-agent">
                <BotIcon size={18} />
              </div>
            )}

            <div className="message-bubble-wrapper" style={{ width: '100%' }}>
              {!isUser && (
                <div className="message-meta-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="message-agent-name">{msg.agentName || 'Root Agent'}</span>
                    <Badge variant="purple" size="sm">Active</Badge>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="message-time">{msg.timestamp}</span>
                    {onDeleteMessage && (
                      <button
                        type="button"
                        className="message-delete-btn"
                        onClick={() => onDeleteMessage(msg.id)}
                        title="Delete message"
                      >
                        <TrashIcon size={12} />
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Steps for this turn are shown in the docked RunStepsPanel above
                  the input bar, so the bubble does not duplicate them here. */}

              {/* Chat Output Bubble with Markdown Rendering */}
              <div className={`message-bubble ${isUser ? 'bubble-user' : 'bubble-agent'}`} style={{ width: '100%' }}>
                {!showPlaceholder ? (
                  <div className="message-markdown-content">
                    {isUser ? (
                      <p className="message-user-text">{displayMain}</p>
                    ) : (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          // `node` is dropped (not destructured) so it is not passed
                          // to the DOM element nor flagged as an unused binding.
                          a: ({ ...props }) => (
                            <a {...props} target="_blank" rel="noopener noreferrer" className="markdown-link" />
                          ),
                          code: ({ className, children, ...props }) => {
                            const isInline = !className && !String(children).includes('\n');
                            return isInline ? (
                              <code className="markdown-inline-code" {...props}>
                                {children}
                              </code>
                            ) : (
                              <pre className="markdown-pre">
                                <code className="markdown-block-code" {...props}>
                                  {children}
                                </code>
                              </pre>
                            );
                          }
                        }}
                      >
                        {displayMain}
                      </ReactMarkdown>
                    )}
                  </div>
                ) : (
                  <div className="streaming-cursor-wrap">
                    <span className="streaming-placeholder">Agent is coordinating tools...</span>
                  </div>
                )}

                {/* 3. Collapsible Reasoning & Thought Logs */}                {!isUser && (displayThoughts || (msg.rawText && msg.rawText !== msg.text)) && (
                  <CollapsibleDetails
                    thoughtProcess={displayThoughts}
                    rawText={msg.rawText}
                    title="View thought process & agent reasoning"
                  />
                )}
              </div>

              {isUser && (
                <div className="message-user-footer">
                  <span className="message-time-user">{msg.timestamp}</span>
                  {onDeleteMessage && (
                    <button
                      type="button"
                      className="message-delete-btn"
                      onClick={() => onDeleteMessage(msg.id)}
                      title="Delete message"
                    >
                      <TrashIcon size={12} />
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {isThinking && (
        <div className="message-row message-row-agent">
          <div className="message-avatar-agent message-avatar-thinking">
            <SparkleIcon size={18} />
          </div>
          <div className="thinking-bubble">
            <span className="thinking-dot"></span>
            <span className="thinking-dot"></span>
            <span className="thinking-dot"></span>
          </div>
        </div>
      )}
    </div>
  );
};
