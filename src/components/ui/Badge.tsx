import React from 'react';

export interface BadgeProps {
  variant?: 'neutral' | 'accent' | 'danger' | 'success';
  size?: 'sm' | 'md';
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  size = 'md',
  children,
  icon,
  className = '',
  onClick,
}) => {
  const variantClasses = {
    neutral: 'bg-[var(--surface-subtle)] text-[var(--text-secondary-color)] border border-[var(--separator)]',
    accent: 'bg-[var(--accent-subtle)] text-[var(--accent)] border border-[var(--accent)]/20',
    danger: 'bg-[var(--danger-subtle)] text-[var(--danger)] border border-[var(--danger)]/20',
    success: 'bg-[var(--success-subtle)] text-[var(--success)] border border-[var(--success)]/20',
  }[variant];

  const sizeClasses = {
    sm: 'text-[12px] px-2 py-0.5 rounded-[6px]',
    md: 'text-[12px] px-2.5 py-1 rounded-[8px]',
  }[size];

  const interactiveClasses = onClick
    ? 'cursor-pointer hover:opacity-80 active:opacity-100 transition-opacity'
    : 'select-none';

  return (
    <span
      onClick={onClick}
      className={`inline-flex items-center gap-1 font-medium leading-none ${variantClasses} ${sizeClasses} ${interactiveClasses} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{children}</span>
    </span>
  );
};
