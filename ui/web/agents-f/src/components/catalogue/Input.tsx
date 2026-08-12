import React from 'react';

export interface InputProps {
  id?: string;
  label?: string;
  value?: string;
  placeholder?: string;
  type?: 'text' | 'password' | 'email' | 'number' | 'search' | 'url';
  disabled?: boolean;
  error?: string;
  onChange?: (value: string) => void;
  className?: string;
}

export const Input: React.FC<InputProps> = ({
  id,
  label,
  value = '',
  placeholder = '',
  type = 'text',
  disabled = false,
  error,
  onChange,
  className = '',
}) => {
  return (
    <div className={`flex flex-col gap-1.5 w-full ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className="typography-label-md text-[#262626] font-medium"
        >
          {label}
        </label>
      )}
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.value)}
        className={`
          firecrawl-input
          w-full
          typography-body-md
          bg-[#FFFFFF]
          text-[#262626]
          placeholder:text-[#6B7280]
          border ${error ? 'border-[#DC2626] focus:border-[#DC2626] focus:ring-1 focus:ring-[#DC2626]' : 'border-[#E5E7EB]'}
          rounded-[16px]
          px-4 py-3
          transition-all duration-150
          disabled:bg-[#F9F9F9] disabled:text-[#6B7280] disabled:cursor-not-allowed
        `.trim()}
      />
      {error && (
        <span className="typography-label-sm text-[#DC2626] mt-0.5">
          {error}
        </span>
      )}
    </div>
  );
};

export default Input;
