import React from 'react';

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string;
  name: string;
  size?: 'sm' | 'md' | 'lg';
  status?: 'online' | 'idle' | 'busy' | 'offline';
}

export const Avatar: React.FC<AvatarProps> = ({
  src,
  name,
  size = 'md',
  status,
  className = '',
  ...props
}) => {
  const initials = name
    .split(' ')
    .map(n => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const classes = [
    'avatar',
    `avatar-${size}`,
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={classes} {...props}>
      {src ? (
        <img src={src} alt={name} className="avatar-img" />
      ) : (
        <span className="avatar-initials">{initials}</span>
      )}
      {status && <span className={`avatar-status avatar-status-${status}`} />}
    </div>
  );
};
