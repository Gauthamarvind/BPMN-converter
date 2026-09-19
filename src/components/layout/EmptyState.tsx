import React, { useRef, useState } from 'react';
import { Upload, BookOpen, ArrowRight } from 'lucide-react';
import { ACCEPTED_EXTENSIONS } from '../../lib/files';

export interface EmptyStateProps {
  onFileUpload: (file: File) => void;
  onOpenTemplate?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  onFileUpload,
  onOpenTemplate,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      onFileUpload(file);
    }
  };

  return (
    <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center select-none max-w-2xl mx-auto space-y-6">
      <div>
        {/* Title */}
        <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-[-0.01em]">
          Turn any process description into BPMN
        </h1>

        {/* Secondary Description */}
        <p className="text-[15px] text-[var(--text-secondary-color)] mt-2 max-w-lg leading-relaxed mx-auto">
          Drop your SOP, Excel, Word, or PDF document to automatically generate
          standards-compliant BPMN 2.0 diagrams — or drop a .bpmn file exported from
          another modelling tool to clean it up and re-export it.
        </p>
      </div>

      {/* Large Drop Zone */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileUpload(file);
        }}
        accept={ACCEPTED_EXTENSIONS}
        className="hidden"
      />

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`w-full max-w-lg p-8 rounded-[16px] border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center gap-3 ${
          isDragging
            ? 'border-[var(--accent)] bg-[var(--accent-subtle)] scale-[1.01]'
            : 'border-[var(--separator-strong)] bg-[var(--surface-subtle)] hover:bg-[var(--surface-solid)] hover:border-[var(--accent)]'
        }`}
      >
        <div className="w-12 h-12 rounded-full bg-[var(--surface-solid)] border border-[var(--separator)] flex items-center justify-center text-[var(--accent)] shadow-xs">
          <Upload className="w-5 h-5" />
        </div>
        <div>
          <span className="text-[15px] font-semibold text-[var(--text)] block">
            Drop your process document here
          </span>
          <span className="text-[13px] text-[var(--text-secondary-color)] mt-1 block">
            or click to browse from Finder
          </span>
        </div>
        <span className="text-[12px] text-[var(--text-tertiary)]">
          Supports .docx, .xlsx, .pdf, .csv, .txt, .md, .vtt — or a .bpmn file from another tool
        </span>
      </div>

      {/* Process capture template card */}
      {onOpenTemplate && (
        <div
          id="empty-state-template-card"
          onClick={onOpenTemplate}
          className="w-full max-w-lg p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:bg-[var(--surface-solid)] hover:border-[var(--accent)] transition-all cursor-pointer flex items-center justify-between text-left group shadow-xs"
        >
          <div className="flex items-center gap-3.5">
            <div className="w-9 h-9 rounded-[8px] bg-[var(--accent-subtle)] text-[var(--accent)] flex items-center justify-center shrink-0">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[14px] font-semibold text-[var(--text)] group-hover:text-[var(--accent)] transition-colors">
                Process capture template
              </div>
              <div className="text-[12px] text-[var(--text-secondary-color)]">
                Download the blank Excel or Word form, with one filled-in example
              </div>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-[var(--text-tertiary)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all shrink-0" />
        </div>
      )}

    </div>
  );
};

