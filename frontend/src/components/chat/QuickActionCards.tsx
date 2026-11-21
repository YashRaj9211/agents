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
