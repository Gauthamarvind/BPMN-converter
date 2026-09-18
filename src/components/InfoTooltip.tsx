import React, { useState } from 'react';
import { Info } from 'lucide-react';

interface InfoTooltipProps {
  content: string;
  title?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
}

export const InfoTooltip: React.FC<InfoTooltipProps> = ({
  content,
  title,
  position = 'top',
  className = '',
}) => {
  const [isVisible, setIsVisible] = useState(false);

  // Determine positioning classes
  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  }[position];

  return (
    <span
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      <span
        role="button"
        tabIndex={0}
        aria-label={title || content}
        onClick={(e) => e.stopPropagation()}
        className="inline-flex items-center p-0.5 text-stone-400 hover:text-stone-700 rounded transition-colors focus:outline-none focus:text-stone-700 cursor-help"
      >
        <Info className="w-3.5 h-3.5" />
      </span>

      {isVisible && (
        <span
          role="tooltip"
          className={`absolute ${positionClasses} z-50 w-64 p-2.5 bg-stone-900 text-stone-100 text-[11px] leading-snug rounded-lg shadow-xl border border-stone-800 pointer-events-none animate-in fade-in zoom-in-95 duration-150 text-left`}
        >
          {title && (
            <span className="block font-semibold text-stone-100 mb-1 border-b border-stone-800 pb-0.5">
              {title}
            </span>
          )}
          <span className="block text-stone-300 font-normal">{content}</span>
        </span>
      )}
    </span>
  );
};
