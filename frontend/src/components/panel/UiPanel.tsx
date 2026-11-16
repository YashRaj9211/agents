import React, { useEffect, useRef, useState } from 'react';
import { fetchUiPanel, getUiPanelRawUrl, type UiPanelMeta } from '../../services/api';
import './UiPanel.css';

interface UiPanelProps {
  panels: UiPanelMeta[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onClose: () => void;
  onDelete: (id: string) => void;
}

const MIN_WIDTH = 340;

/**
 * Side panel beside the chat that renders agent-generated HTML.
 *
 * The HTML is untrusted model output, so it runs in an iframe with `sandbox="allow-scripts"`
 * and deliberately WITHOUT `allow-same-origin`: scripts work, but the page gets an opaque
 * origin and cannot read the app's DOM, cookies or storage or call the API as the user.
 */
export const UiPanel: React.FC<UiPanelProps> = ({ panels, activeId, onSelect, onClose, onDelete }) => {
  const active = panels.find((p) => p.id === activeId) || panels[0];
  // The loaded document is tagged with the panel version it belongs to, so a stale
  // one is never shown for a different panel and no reset-in-effect is needed.
  const [loaded, setLoaded] = useState<{ key: string; html: string | null } | null>(null);
  const [width, setWidth] = useState(() => Math.max(MIN_WIDTH, Math.round(window.innerWidth * 0.42)));
  const [dragging, setDragging] = useState(false);
  const panelRef = useRef<HTMLElement>(null);

  const activeKey = active ? `${active.id}:${active.version}` : '';
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const key = activeKey;
    fetchUiPanel(active.id)
      .then((p) => !cancelled && setLoaded({ key, html: p ? p.html : null }))
      .catch(() => !cancelled && setLoaded({ key, html: null }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey]);

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: PointerEvent) => {
      const right = panelRef.current?.getBoundingClientRect().right ?? window.innerWidth;
      setWidth(Math.min(Math.max(MIN_WIDTH, right - e.clientX), window.innerWidth - 420));
    };
    const onUp = () => setDragging(false);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [dragging]);

  if (!active) return null;
  const current = loaded && loaded.key === activeKey ? loaded : null;
  const html = current?.html ?? null;
  const failed = current !== null && current.html === null;

  return (
    <aside className="ui-panel" ref={panelRef} style={{ width }} aria-label="Agent view">
      <div
        className="ui-panel-resizer"
        onPointerDown={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        role="separator"
        aria-orientation="vertical"
      />
      <header className="ui-panel-header">
        <div className="ui-panel-tabs" role="tablist">
          {panels.map((p) => (
            <button
              key={p.id}
              role="tab"
              aria-selected={p.id === active.id}
              className={`ui-panel-tab${p.id === active.id ? ' active' : ''}`}
              onClick={() => onSelect(p.id)}
              title={p.title}
            >
              {p.title}
            </button>
          ))}
        </div>
        <div className="ui-panel-actions">
          <a
            className="ui-panel-btn"
            href={getUiPanelRawUrl(active.id)}
            target="_blank"
            rel="noopener noreferrer"
            title="Open in a new tab"
          >
            ↗
          </a>
          <button className="ui-panel-btn" onClick={() => onDelete(active.id)} title="Delete this view">
            🗑
          </button>
          <button className="ui-panel-btn" onClick={onClose} title="Close panel" aria-label="Close panel">
            ✕
          </button>
        </div>
      </header>
      <div className="ui-panel-body">
        {failed ? (
          <p className="ui-panel-empty">Could not load this view.</p>
        ) : html === null ? (
          <p className="ui-panel-empty">Loading…</p>
        ) : (
          <iframe
            key={activeKey}
            title={active.title}
            className="ui-panel-frame"
            sandbox="allow-scripts allow-popups allow-forms allow-modals"
            srcDoc={html}
            style={dragging ? { pointerEvents: 'none' } : undefined}
          />
        )}
      </div>
    </aside>
  );
};
