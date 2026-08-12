import React from 'react';

export interface CheckboxProps {
  id?: string;
  label?: string;
  checked?: boolean;
  disabled?: boolean;
  onChange?: (checked: boolean) => void;
  className?: string;
}

export const Checkbox: React.FC<CheckboxProps> = ({
  id,
  label,
  checked = false,
  disabled = false,
  onChange,
  className = '',
}) => {
  return (
    <label
      htmlFor={id}
      className={`
        inline-flex items-center gap-3 cursor-pointer select-none
        ${disabled ? 'cursor-not-allowed opacity-50' : ''}
        ${className}
      `.trim()}
    >
      <div className="relative flex items-center justify-center">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange?.(e.target.checked)}
          className="sr-only peer"
        />
        <div
          className={`
            w-5 h-5 rounded-[4px] border transition-all duration-150 flex items-center justify-center
            peer-focus-visible:ring-2 peer-focus-visible:ring-[#FA5D19] peer-focus-visible:ring-offset-1
            ${
              checked
                ? 'bg-[#FA5D19] border-[#FA5D19]'
                : 'bg-[#FFFFFF] border-[#E5E7EB] hover:border-[#FA5D19]'
            }
          `.trim()}
        >
          {checked && (
            <svg
              className="w-3.5 h-3.5 text-white stroke-current"
              viewBox="0 0 14 14"
              fill="none"
            >
              <path
                d="M3 7L5.5 9.5L11 4"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
      </div>
      {label && (
        <span className="typography-body-md text-[#262626]">
          {label}
        </span>
      )}
    </label>
  );
};

export default Checkbox;
