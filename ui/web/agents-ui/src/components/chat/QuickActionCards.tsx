import React from 'react';
import { Card } from '../common';

export interface ActionCardData {
  id: string;
  emoji: string;
  title: string;
  description: string;
  prompt: string;
  /** Accent colour; values mirror backend `style.color_scheme`. */
  colorScheme?: 'orange' | 'purple' | 'blue' | 'green';
  /** Agent the backend recommends running this action with. */
  target_agent_id?: string;
}

interface QuickActionCardsProps {
  cards: ActionCardData[];
  onSelectAction: (prompt: string) => void;
}

export const QuickActionCards: React.FC<QuickActionCardsProps> = ({
  cards,
  onSelectAction
}) => {
  return (
    <div className="quick-actions-grid">
      {cards.map((card) => (
        <Card
          key={card.id}
          variant="interactive"
          padding="md"
          className={`quick-action-card card-accent-${card.colorScheme || 'purple'}`}
          onClick={() => onSelectAction(card.prompt)}
        >
          <div className="quick-action-icon-wrap">
            <span className="quick-action-emoji">{card.emoji}</span>
          </div>
          <h4 className="quick-action-title">{card.title}</h4>
          <p className="quick-action-desc">{card.description}</p>
        </Card>
      ))}
    </div>
  );
};
