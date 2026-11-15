import React from 'react';
import { QuickActionCards, type ActionCardData } from './QuickActionCards';

interface WelcomeHeroProps {
  userName?: string;
  actions?: ActionCardData[];
  onSelectAction: (prompt: string) => void;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({
  userName = 'Allison',
  actions = [],
  onSelectAction
}) => {
  return (
    <div className="welcome-hero-container">
      {/* Central Glowing Star Icon */}
      <div className="star-icon-container">
        <div className="star-icon-glow"></div>
        <svg
          className="star-icon-svg"
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M50 0C50 27.6142 27.6142 50 0 50C27.6142 50 50 72.3858 50 100C50 72.3858 72.3858 50 100 50C72.3858 50 50 27.6142 50 0Z"
            fill="url(#starGradient)"
          />
          <defs>
            <linearGradient
              id="starGradient"
              x1="0"
              y1="0"
              x2="100"
              y2="100"
              gradientUnits="userSpaceOnUse"
            >
              <stop stopColor="#F9A88F" />
              <stop offset="0.45" stopColor="#E2A5D8" />
              <stop offset="0.85" stopColor="#A5B4FC" />
              <stop offset="1" stopColor="#C4B5FD" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      <div className="welcome-text-group">
        <h1 className="welcome-heading">Welcome, {userName}!</h1>
        <p className="welcome-subheading">How can the agent backend assist you today?</p>
      </div>

      <QuickActionCards cards={actions} onSelectAction={onSelectAction} />
    </div>
  );
};
