import React from 'react';

export interface RangeProps {
  id?: string;
  label?: string;
  value?: number;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  onChange?: (value: number) => void;
  className?: string;
}

export const Range: React.FC<RangeProps> = ({
  id,
  label,
  value = 50,
  min = 0,
  max = 100,
  step = 1,
  disabled = false,
  onChange,
  className = '',
}) => {
  const percentage = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

  return (
    <div className={`flex flex-col gap-2 w-full ${className}`}>
      <div className="flex justify-between items-center">
        {label && (
          <label
            htmlFor={id}
            className="typography-label-md text-[#262626] font-medium"
          >
            {label}
          </label>
        )}
        <span className="firecrawl-chip font-mono !py-0.5 !px-2.5 text-[#FA5D19] border-[#FA5D19]/30">
          {value}
        </span>
      </div>
      <div className="relative flex items-center h-6">
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange?.(Number(e.target.value))}
          style={{
            background: `linear-gradient(to right, #FA5D19 0%, #FA5D19 ${percentage}%, #E5E7EB ${percentage}%, #E5E7EB 100%)`,
          }}
          className={`
            w-full h-2 rounded-[9999px] appearance-none cursor-pointer outline-none
            accent-[#FA5D19]
            disabled:opacity-50 disabled:cursor-not-allowed
          `.trim()}
        />
      </div>
      <div className="flex justify-between typography-micro text-[#6B7280]">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
};

export default Range;
