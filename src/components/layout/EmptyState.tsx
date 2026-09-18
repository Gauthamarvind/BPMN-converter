import React, { useRef, useState } from 'react';
import { Upload, ArrowUpRight, Sparkles, BookOpen } from 'lucide-react';
import { SampleFile } from '../../types';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export interface EmptyStateProps {
  onFileUpload: (file: File) => void;
  samples: SampleFile[];
  onSelectSample: (sample: SampleFile) => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  onFileUpload,
  samples,
  onSelectSample,
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
    <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center select-none max-w-2xl mx-auto">
      {/* Title */}
      <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-[-0.01em]">
        Turn any process description into BPMN
      </h1>

      {/* Secondary Description */}
      <p className="text-[15px] text-[var(--text-secondary-color)] mt-2 max-w-lg leading-relaxed">
        Drop your SOP, Excel, Word, or PDF document to automatically generate
        standards-compliant BPMN 2.0 diagrams.
      </p>

      {/* Large Drop Zone */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileUpload(file);
        }}
        accept=".txt,.md,.markdown,.csv,.docx,.xlsx,.pdf,.json,.srt,.vtt"
        className="hidden"
      />

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`w-full max-w-lg mt-8 p-8 rounded-[16px] border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center gap-3 ${
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
          Supports .docx, .xlsx, .pdf, .csv, .txt, .md
        </span>
      </div>

      {/* Row of Sample Chips */}
      {samples.length > 0 && (
        <div className="mt-8 flex flex-col items-center gap-2.5">
          <span className="text-[12px] font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
            Or try a sample workflow
          </span>
          <div className="flex items-center gap-2 flex-wrap justify-center">
            {samples.map((sample) => (
              <Badge
                key={sample.name}
                variant="neutral"
                size="md"
                onClick={() => onSelectSample(sample)}
                className="cursor-pointer hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all"
              >
                <span>{sample.title || sample.name}</span>
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
