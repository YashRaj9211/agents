import React from 'react';
import type { ActionCardData } from './QuickActionCards';

interface WelcomeHeroProps {
  userName?: string;
  actions?: ActionCardData[];
  onSelectAction: (prompt: string) => void;
  /** The composer, rendered inside the hero so it sits under the headline. */
  children?: React.ReactNode;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({ actions = [], onSelectAction, children }) => {
  return (
    <div className="hero">
      <h1 className="hero-title">
        Your agents,
        <br />
        one conversation.
      </h1>
      <p className="hero-sub">Describe what you need and the right agent picks it up.</p>

      <div className="hero-composer">{children}</div>

      {actions.length > 0 && (
        <div className="hero-chips">
          {actions.slice(0, 4).map((a) => (
            <button key={a.id} type="button" className="hero-chip" onClick={() => onSelectAction(a.prompt)}>
              {a.title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
