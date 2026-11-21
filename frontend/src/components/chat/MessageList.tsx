import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BotIcon, SparkleIcon, TrashIcon, CopyIcon, CheckIcon } from '../icons/Icons';
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
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const bottomRef = useRef<HTMLDivElement>(null);
  const firstId = messages[0]?.id;

  // Jump to the latest message when a chat is opened/switched.
  useLayoutEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' });
  }, [firstId]);

  // Follow new messages as they arrive.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [messages.length, isThinking]);

  return (
    <div className="message-list-container">
      {messages.map((msg) => {
        const isUser = msg.sender === 'user';

        let displayMain = msg.text;
        let displayThoughts = msg.thoughtProcess || '';
        let showPlaceholder = !msg.text;

        if (!isUser && msg.text) {
          let text = msg.text;

          // Strip <think>...</think> or <thought>...</thought> tags
          const thinkMatches = text.match(/<(?:think|thought)>([\s\S]*?)<\/(?:think|thought)>/gi);
          if (thinkMatches) {
            for (const match of thinkMatches) {
              const inner = match.replace(/<\/?(?:think|thought)>/gi, '').trim();
              displayThoughts = (displayThoughts ? displayThoughts + '\n\n' : '') + inner;
            }
            text = text.replace(/<(?:think|thought)>[\s\S]*?<\/(?:think|thought)>/gi, '').trim();
          }

          // Strip <DONE> tags
          const doneMatch = text.match(/<DONE>([\s\S]*?)(?:<\/DONE>|$)/i);
          if (doneMatch) {
            displayMain = doneMatch[1].trim();
            const leftover = text.replace(/<DONE>[\s\S]*?(?:<\/DONE>|$)/i, '').trim();
            if (leftover) {
              displayThoughts = (displayThoughts ? displayThoughts + '\n\n' : '') + leftover;
            }
          } else {
            displayMain = text;
          }
          showPlaceholder = !displayMain;
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
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="message-time">{msg.timestamp}</span>
                    {displayMain && (
                      <button
                        type="button"
                        className={`message-action-btn ${copiedId === msg.id ? 'message-action-btn-active' : ''}`}
                        onClick={() => handleCopy(msg.id, displayMain)}
                        title={copiedId === msg.id ? 'Copied to clipboard!' : 'Copy response'}
                      >
                        {copiedId === msg.id ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
                        <span className="btn-label-text">{copiedId === msg.id ? 'Copied' : 'Copy'}</span>
                      </button>
                    )}
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
                          a: ({ ...props }) => (
                            <a {...props} target="_blank" rel="noopener noreferrer" className="markdown-link" />
                          ),
                          table: ({ children, ...props }) => (
                            <div className="markdown-table-wrapper">
                              <table className="markdown-table" {...props}>
                                {children}
                              </table>
                            </div>
                          ),
                          thead: ({ children, ...props }) => <thead className="markdown-thead" {...props}>{children}</thead>,
                          tbody: ({ children, ...props }) => <tbody className="markdown-tbody" {...props}>{children}</tbody>,
                          tr: ({ children, ...props }) => <tr className="markdown-tr" {...props}>{children}</tr>,
                          th: ({ children, ...props }) => <th className="markdown-th" {...props}>{children}</th>,
                          td: ({ children, ...props }) => {
                            const t = typeof children === 'string' ? children.trim().toLowerCase() : '';
                            const tone = ['ok', 'success', 'done', 'passed'].includes(t) ? 'ok'
                              : ['failed', 'error', 'fail'].includes(t) ? 'bad'
                              : ['warning', 'pending', 'partial', 'skipped'].includes(t) ? 'warn' : '';
                            return (
                              <td className="markdown-td" {...props}>
                                {tone ? <span className={`status-badge status-${tone}`}>{children}</span> : children}
                              </td>
                            );
                          },
                          blockquote: ({ children, ...props }) => (
                            <blockquote className="md-callout" {...props}>{children}</blockquote>
                          ),
                          code: ({ className, children, ...props }) => {
                            const isInline = !className && !String(children).includes('\n');
                            return isInline ? (
                              <code className="markdown-inline-code" {...props}>
                                {children}
                              </code>
                            ) : (
                              <div className="markdown-code-wrapper">
                                <pre className="markdown-pre">
                                  <code className="markdown-block-code" {...props}>
                                    {children}
                                  </code>
                                </pre>
                              </div>
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

                {/* Collapsible Reasoning & Thought Logs */}
                {!isUser && (displayThoughts || (msg.rawText && msg.rawText !== msg.text && msg.rawText !== displayMain)) && (
                  <CollapsibleDetails
                    thoughtProcess={displayThoughts}
                    rawText={msg.rawText !== displayMain ? msg.rawText : undefined}
                    title="Thinking process & reasoning"
                    defaultExpanded={false}
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
      <div ref={bottomRef} />
    </div>
  );
};
