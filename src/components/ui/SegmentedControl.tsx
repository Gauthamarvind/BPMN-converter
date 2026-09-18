import React from 'react';
import { motion } from 'motion/react';

export interface SegmentedOption<T extends string = string> {
  id: T;
  label: string;
  icon?: React.ReactNode;
  badge?: number | string;
}

export interface SegmentedControlProps<T extends string = string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  id?: string;
  className?: string;
  size?: 'sm' | 'md';
}

export function SegmentedControl<T extends string = string>({
  options,
  value,
  onChange,
  id,
  className = '',
  size = 'md',
}: SegmentedControlProps<T>) {
  const containerId = id || 'segmented-control';

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      const nextIndex = (index + 1) % options.length;
      onChange(options[nextIndex].id);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      const prevIndex = (index - 1 + options.length) % options.length;
      onChange(options[prevIndex].id);
    }
  };

  const heightClass = size === 'sm' ? 'h-7 p-0.5' : 'h-8 p-1';

  return (
    <div
      id={containerId}
      role="tablist"
      className={`inline-flex items-center bg-[var(--surface-subtle)] rounded-[8px] border border-[var(--separator)] select-none ${heightClass} ${className}`}
    >
      {options.map((option, idx) => {
        const isSelected = option.id === value;
        return (
          <button
            key={option.id}
            role="tab"
            aria-selected={isSelected}
            tabIndex={isSelected ? 0 : -1}
            onClick={() => onChange(option.id)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={`relative px-2.5 h-full rounded-[8px] text-[13px] transition-colors duration-150 flex items-center justify-center gap-1.5 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] z-10 ${
              isSelected
                ? 'font-medium text-[var(--text)]'
                : 'text-[var(--text-secondary-color)] hover:text-[var(--text)]'
            }`}
          >
            {isSelected && (
              <motion.div
                layoutId={`${containerId}-active-pill`}
                className="absolute inset-0 bg-[var(--surface-solid)] rounded-[8px] shadow-xs -z-10"
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              />
            )}
            {option.icon && <span className="shrink-0">{option.icon}</span>}
            <span className="truncate">{option.label}</span>
            {option.badge !== undefined && (
              <span
                className={`ml-1 px-1.5 py-0.2 rounded-full text-[12px] font-medium ${
                  isSelected
                    ? 'bg-[var(--accent)] text-white'
                    : 'bg-[var(--separator-strong)] text-[var(--text-secondary-color)]'
                }`}
              >
                {option.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
