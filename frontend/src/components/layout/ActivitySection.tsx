import React, { useState } from 'react';
import { ChevronDownIcon } from '../icons/Icons';

interface ActivitySectionProps {
  title: string;
  /** Short status shown on the right of the header, e.g. "3 running". */
  summary?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

/** One collapsible row of the right-hand panel: title, summary, chevron. */
export const ActivitySection: React.FC<ActivitySectionProps> = ({
  title,
  summary,
  defaultOpen = false,
  children,
}) => {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={`act-section ${open ? 'is-open' : ''}`}>
      <button type="button" className="act-section-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className={`act-chevron ${open ? 'is-open' : ''}`}>
          <ChevronDownIcon size={14} />
        </span>
        <span className="act-section-title">{title}</span>
        {summary !== undefined && <span className="act-section-summary">{summary}</span>}
      </button>
      {open && <div className="act-section-body">{children}</div>}
    </section>
  );
};
