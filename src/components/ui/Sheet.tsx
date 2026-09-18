import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X } from 'lucide-react';

export interface SheetProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: string;
  side?: 'right' | 'bottom' | 'left';
  id?: string;
}

export const Sheet: React.FC<SheetProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = 'w-full sm:max-w-[480px]',
  side = 'right',
  id,
}) => {
  // Close on Esc key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const slideVariants = {
    right: {
      initial: { x: '100%' },
      animate: { x: 0 },
      exit: { x: '100%' },
    },
    left: {
      initial: { x: '-100%' },
      animate: { x: 0 },
      exit: { x: '-100%' },
    },
    bottom: {
      initial: { y: '100%' },
      animate: { y: 0 },
      exit: { y: '100%' },
    },
  }[side];

  const positionClasses = {
    right: `fixed top-0 right-0 bottom-0 ${width} rounded-l-[16px] border-l border-[var(--separator)]`,
    left: `fixed top-0 left-0 bottom-0 ${width} rounded-r-[16px] border-r border-[var(--separator)]`,
    bottom: `fixed bottom-0 left-0 right-0 max-h-[85vh] rounded-t-[16px] border-t border-[var(--separator)]`,
  }[side];

  return (
    <AnimatePresence>
      {isOpen && (
        <div id={id} className="fixed inset-0 z-50 flex overflow-hidden">
          {/* Scrim */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-40 cursor-pointer"
          />

          {/* Sheet Panel */}
          <motion.div
            initial={slideVariants.initial}
            animate={slideVariants.animate}
            exit={slideVariants.exit}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className={`z-50 bg-[var(--surface)] backdrop-blur-[20px] shadow-[var(--shadow-sheet)] flex flex-col overflow-hidden ${positionClasses}`}
          >
            {/* Header */}
            <div className="px-6 py-4 border-b border-[var(--separator)] flex items-center justify-between shrink-0 bg-[var(--surface-solid)]">
              <div>
                <h2 className="text-[20px] font-semibold text-[var(--text)] tracking-tight">
                  {title}
                </h2>
                {subtitle && (
                  <p className="text-[13px] text-[var(--text-secondary-color)] mt-0.5">
                    {subtitle}
                  </p>
                )}
              </div>
              <button
                onClick={onClose}
                title="Close (Esc)"
                className="w-8 h-8 rounded-[8px] flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto px-6 py-5 text-[15px] space-y-5">
              {children}
            </div>

            {/* Footer */}
            {footer && (
              <div className="px-6 py-3.5 border-t border-[var(--separator)] bg-[var(--surface-solid)] flex items-center justify-end gap-2.5 shrink-0">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
