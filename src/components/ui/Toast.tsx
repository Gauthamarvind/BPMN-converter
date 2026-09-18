import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertCircle, CheckCircle, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type?: 'error' | 'success' | 'info';
  title?: string;
  message: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export interface ToastProps {
  toast: ToastMessage | null;
  onDismiss: () => void;
  duration?: number;
}

export const Toast: React.FC<ToastProps> = ({
  toast,
  onDismiss,
  duration = 6000,
}) => {
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      onDismiss();
    }, duration);
    return () => clearTimeout(timer);
  }, [toast, onDismiss, duration]);

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 pointer-events-none flex flex-col items-center">
      <AnimatePresence>
        {toast && (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="pointer-events-auto max-w-md bg-[var(--surface-elevated)] backdrop-blur-[20px] text-[var(--text)] border border-[var(--separator)] rounded-[12px] shadow-[var(--shadow-popover)] px-4 py-3 flex items-start gap-3 select-none"
          >
            <div className="shrink-0 mt-0.5">
              {toast.type === 'error' ? (
                <AlertCircle className="w-4 h-4 text-[var(--danger)]" />
              ) : toast.type === 'success' ? (
                <CheckCircle className="w-4 h-4 text-[var(--success)]" />
              ) : (
                <Info className="w-4 h-4 text-[var(--accent)]" />
              )}
            </div>

            <div className="flex-1 min-w-0 text-left">
              {toast.title && (
                <div className="text-[13px] font-semibold text-[var(--text)]">
                  {toast.title}
                </div>
              )}
              <div className="text-[13px] text-[var(--text-secondary-color)] leading-snug">
                {toast.message}
              </div>

              {toast.action && (
                <button
                  onClick={() => {
                    toast.action?.onClick();
                    onDismiss();
                  }}
                  className="mt-1.5 text-[12px] font-semibold text-[var(--accent)] hover:underline cursor-pointer"
                >
                  {toast.action.label}
                </button>
              )}
            </div>

            <button
              onClick={onDismiss}
              className="shrink-0 p-1 text-[var(--text-tertiary)] hover:text-[var(--text)] rounded-[6px] transition-colors cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
