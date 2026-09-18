import React, { forwardRef } from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  caption?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, caption, error, className = '', id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full flex flex-col gap-1.5 text-left">
        {label && (
          <label
            htmlFor={inputId}
            className="text-[13px] font-medium text-[var(--text)] select-none"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`h-8 w-full px-3 text-[13px] bg-[var(--surface-solid)] text-[var(--text)] border border-[var(--separator-strong)] rounded-[8px] placeholder:text-[var(--text-tertiary)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 disabled:opacity-50 disabled:bg-[var(--surface-subtle)] ${
            error ? 'border-[var(--danger)] focus-visible:ring-[var(--danger)]' : ''
          } ${className}`}
          {...props}
        />
        {error ? (
          <span className="text-[12px] text-[var(--danger)] font-normal">{error}</span>
        ) : caption ? (
          <span className="text-[12px] text-[var(--text-secondary-color)] font-normal">
            {caption}
          </span>
        ) : null}
      </div>
    );
  }
);
Input.displayName = 'Input';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  caption?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, caption, error, className = '', id, rows = 4, ...props }, ref) => {
    const textareaId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full flex flex-col gap-1.5 text-left">
        {label && (
          <label
            htmlFor={textareaId}
            className="text-[13px] font-medium text-[var(--text)] select-none"
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          rows={rows}
          className={`w-full p-3 text-[13px] bg-[var(--surface-solid)] text-[var(--text)] border border-[var(--separator-strong)] rounded-[8px] placeholder:text-[var(--text-tertiary)] transition-colors resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 disabled:opacity-50 disabled:bg-[var(--surface-subtle)] ${
            error ? 'border-[var(--danger)] focus-visible:ring-[var(--danger)]' : ''
          } ${className}`}
          {...props}
        />
        {error ? (
          <span className="text-[12px] text-[var(--danger)] font-normal">{error}</span>
        ) : caption ? (
          <span className="text-[12px] text-[var(--text-secondary-color)] font-normal">
            {caption}
          </span>
        ) : null}
      </div>
    );
  }
);
Textarea.displayName = 'Textarea';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  caption?: string;
  error?: string;
  options?: { value: string; label: string }[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, caption, error, options, children, className = '', id, ...props }, ref) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full flex flex-col gap-1.5 text-left">
        {label && (
          <label
            htmlFor={selectId}
            className="text-[13px] font-medium text-[var(--text)] select-none"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={`h-8 w-full px-2.5 text-[13px] bg-[var(--surface-solid)] text-[var(--text)] border border-[var(--separator-strong)] rounded-[8px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 cursor-pointer ${
            error ? 'border-[var(--danger)] focus-visible:ring-[var(--danger)]' : ''
          } ${className}`}
          {...props}
        >
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        {error ? (
          <span className="text-[12px] text-[var(--danger)] font-normal">{error}</span>
        ) : caption ? (
          <span className="text-[12px] text-[var(--text-secondary-color)] font-normal">
            {caption}
          </span>
        ) : null}
      </div>
    );
  }
);
Select.displayName = 'Select';
