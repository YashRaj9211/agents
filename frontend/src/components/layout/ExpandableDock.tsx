import React, { useEffect, useRef, useState } from 'react';
import { PlusIcon } from '../icons/Icons';

export interface DockItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  badge?: number | string;
}

interface ExpandableDockProps {
  items: DockItem[];
  activeId: string;
  onSelect: (id: string) => void;
  /** How many items stay visible while collapsed. */
  pinnedCount?: number;
  /** Columns in the expanded grid. */
  columns?: number;
}

export const ExpandableDock: React.FC<ExpandableDockProps> = ({
  items,
  activeId,
  onSelect,
  pinnedCount = 3,
  columns = 3,
}) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Pinned items are the first N, but the active item always stays visible.
  const pinned = items.slice(0, pinnedCount);
  const activeExtra = items.slice(pinnedCount).find((i) => i.id === activeId);
  const collapsed = activeExtra ? [...pinned.slice(0, pinnedCount - 1), activeExtra] : pinned;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const select = (id: string) => {
    onSelect(id);
    setOpen(false);
  };

  const hiddenBadge = items.some((i) => i.badge && !collapsed.includes(i));

  return (
    <div ref={rootRef} className={`dock ${open ? 'dock-open' : ''}`}>
      {/* Expanded grid: grows upward with a blurred glass backdrop */}
      <div
        className="dock-panel"
        id="dock-panel"
        aria-hidden={!open}
        style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}
      >
        {items.map((item, idx) => (
          <button
            key={item.id}
            type="button"
            tabIndex={open ? 0 : -1}
            className={`dock-tile ${item.id === activeId ? 'dock-tile-active' : ''}`}
            style={{ transitionDelay: open ? `${40 + idx * 25}ms` : '0ms' }}
            onClick={() => select(item.id)}
          >
            <span className="dock-tile-icon">
              {item.icon}
              {item.badge ? <span className="dock-badge">{item.badge}</span> : null}
            </span>
            <span className="dock-tile-label">{item.label}</span>
          </button>
        ))}
      </div>

      {/* Collapsed bar */}
      <div className="dock-bar">
        {collapsed.map((item) => (
          <button
            key={item.id}
            type="button"
            title={item.label}
            aria-label={item.label}
            className={`dock-item ${item.id === activeId ? 'dock-item-active' : ''}`}
            onClick={() => select(item.id)}
          >
            {item.icon}
            {item.badge ? <span className="dock-badge">{item.badge}</span> : null}
          </button>
        ))}
        <button
          type="button"
          className="dock-toggle"
          aria-expanded={open}
          aria-controls="dock-panel"
          aria-label={open ? 'Close menu' : 'More'}
          onClick={() => setOpen((o) => !o)}
        >
          <PlusIcon size={18} />
          {!open && hiddenBadge ? <span className="dock-badge dock-badge-dot" /> : null}
        </button>
      </div>
    </div>
  );
};
