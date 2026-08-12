import React from 'react';

export interface DropdownOption {
  label: string;
  value: string;
}

export interface DropdownProps {
  id?: string;
  label?: string;
  value?: string;
  options: DropdownOption[];
  placeholder?: string;
  disabled?: boolean;
  onChange?: (value: string) => void;
  className?: string;
}

export const Dropdown: React.FC<DropdownProps> = ({
  id,
  label,
  value = '',
  options = [],
  placeholder = 'Select an option...',
  disabled = false,
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
      <div className="relative">
        <select
          id={id}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange?.(e.target.value)}
          className={`
            w-full appearance-none
            bg-[#FFFFFF] text-[#262626]
            border border-[#E5E7EB] rounded-[16px]
            px-4 py-3 pr-10
            typography-body-md
            outline-none
            transition-all duration-150
            focus:border-[#FA5D19] focus:ring-2 focus:ring-[#FA5D19]/15
            disabled:bg-[#F9F9F9] disabled:text-[#6B7280] disabled:cursor-not-allowed
            cursor-pointer
          `.trim()}
        >
          {placeholder && (
            <option value="" disabled hidden>
              {placeholder}
            </option>
          )}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-[#6B7280]">
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </div>
      </div>
    </div>
  );
};

export default Dropdown;
