import React, { forwardRef } from 'react';
import { motion, HTMLMotionProps } from 'motion/react';

export interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  icon?: React.ReactNode;
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'secondary',
      size = 'md',
      children,
      icon,
      isLoading,
      disabled,
      className = '',
      ...props
    },
    ref
  ) => {
    const baseClasses =
      'inline-flex items-center justify-center gap-1.5 font-medium cursor-pointer transition-colors duration-150 select-none disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2';

    // Sizes
    const sizeClasses = {
      sm: 'h-7 min-w-[28px] px-2 text-[12px] rounded-[8px]',
      md: 'h-8 min-w-[32px] px-3 text-[13px] rounded-[8px]',
      lg: 'h-9 min-w-[36px] px-4 text-[15px] rounded-[8px]',
    }[size];

    // Variants
    const variantClasses = {
      primary:
        'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] shadow-xs active:bg-[var(--accent)]',
      secondary:
        'bg-[var(--surface-solid)] text-[var(--text)] border border-[var(--separator-strong)] hover:bg-[var(--surface-subtle)] active:bg-[var(--surface-subtle)]',
      ghost:
        'bg-transparent text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)]',
      danger:
        'bg-[var(--danger)] text-white hover:opacity-90 active:opacity-100 shadow-xs',
    }[variant];

    return (
      <motion.button
        ref={ref}
        whileTap={disabled ? undefined : { scale: 0.98 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        disabled={disabled || isLoading}
        className={`${baseClasses} ${sizeClasses} ${variantClasses} ${className}`}
        {...props}
      >
        {isLoading ? (
          <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin mr-1" />
        ) : icon ? (
          <span className="shrink-0">{icon}</span>
        ) : null}
        <span>{children}</span>
      </motion.button>
    );
  }
);

Button.displayName = 'Button';
