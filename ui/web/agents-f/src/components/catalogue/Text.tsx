import React from 'react';

export type TextVariant =
  | 'headline-display'
  | 'headline-lg'
  | 'headline-md'
  | 'headline-sm'
  | 'body-lg'
  | 'body-md'
  | 'body-sm'
  | 'label-lg'
  | 'label-md'
  | 'label-sm'
  | 'micro'
  | 'h1'
  | 'h2'
  | 'h3'
  | 'p';

export interface TextProps {
  id?: string;
  text: string;
  variant?: TextVariant;
  muted?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const variantClassMap: Record<TextVariant, string> = {
  'headline-display': 'typography-headline-display text-[#262626]',
  'headline-lg': 'typography-headline-lg text-[#262626]',
  'headline-md': 'typography-headline-md text-[#262626]',
  'headline-sm': 'typography-headline-sm text-[#262626]',
  'body-lg': 'typography-body-lg text-[#262626]',
  'body-md': 'typography-body-md text-[#262626]',
  'body-sm': 'typography-body-sm text-[#262626]',
  'label-lg': 'typography-label-lg text-[#262626]',
  'label-md': 'typography-label-md text-[#262626]',
  'label-sm': 'typography-label-sm text-[#262626]',
  'micro': 'typography-micro text-[#6B7280]',
  'h1': 'typography-headline-display text-[#262626]',
  'h2': 'typography-headline-lg text-[#262626]',
  'h3': 'typography-headline-md text-[#262626]',
  'p': 'typography-body-md text-[#262626]',
};

export const Text: React.FC<TextProps> = ({
  id,
  text,
  variant = 'body-md',
  muted = false,
  className = '',
  style,
}) => {
  const baseClass = variantClassMap[variant] || 'typography-body-md text-[#262626]';
  const mutedClass = muted ? '!text-[#6B7280]' : '';

  // Select semantic HTML tag based on variant
  const getTag = () => {
    if (variant === 'headline-display' || variant === 'h1') return 'h1';
    if (variant === 'headline-lg' || variant === 'h2') return 'h2';
    if (variant === 'headline-md' || variant === 'h3') return 'h3';
    if (variant === 'headline-sm') return 'h4';
    if (variant.startsWith('label') || variant === 'micro') return 'span';
    return 'p';
  };

  const Tag = getTag();

  return (
    <Tag
      id={id}
      style={style}
      className={`${baseClass} ${mutedClass} ${className}`.trim()}
    >
      {text}
    </Tag>
  );
};

export default Text;
