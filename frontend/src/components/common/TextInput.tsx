import React from 'react';

export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
  clearable?: boolean;
  onClear?: () => void;
}

export const TextInput: React.FC<TextInputProps> = ({
  icon,
  clearable,
  onClear,
  value,
  className = '',
  ...props
}) => {
  return (
    <div className={`input-wrapper ${className}`}>
      {icon && <span className="input-icon">{icon}</span>}
      <input
        className="input-field"
        value={value}
        {...props}
      />
      {clearable && value && (
        <button
          type="button"
          onClick={onClear}
          className="input-clear-btn"
          aria-label="Clear input"
        >
          ×
        </button>
      )}
    </div>
  );
};
