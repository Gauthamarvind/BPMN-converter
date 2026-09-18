import React from 'react';

export interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  rounded?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className = '',
  width,
  height,
  rounded = 'rounded-[8px]',
}) => {
  return (
    <div
      style={{ width, height }}
      className={`animate-pulse bg-[var(--surface-subtle)] ${rounded} ${className}`}
    />
  );
};
