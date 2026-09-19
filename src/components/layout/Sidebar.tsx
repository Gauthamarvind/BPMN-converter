import React, { useRef, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Upload,
  FileText,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  AlertCircle,
} from 'lucide-react';
import { UiError } from '../../types';
import { Button } from '../ui/Button';
import { Textarea } from '../ui/Field';

export interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  inputText: string;
  onInputChange: (text: string) => void;
  fileName?: string;
  fileSize?: number;
  onFileUpload: (file: File) => void;
  onConvert: () => void;
  isLoading: boolean;
  error?: UiError | null;
  onOpenSettings?: () => void;
  isSheet?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggle,
  inputText,
  onInputChange,
  fileName,
  fileSize,
  onFileUpload,
  onConvert,
  isLoading,
  error,
  onOpenSettings,
  isSheet = false,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showErrorDetails, setShowErrorDetails] = useState(false);

  useEffect(() => {
    setShowErrorDetails(false);
  }, [error]);

  const errorCard = error ? (
    <div
      role="alert"
      className="p-3 rounded-[12px] bg-[var(--danger-subtle)] text-[13px] leading-snug space-y-1.5"
    >
      <div className="flex items-start gap-2 text-[var(--danger)]">
        <AlertCircle className="w-4 h-4 shrink-0 mt-px" />
        <span className="font-semibold">{error.title}</span>
      </div>
      <p className="text-[var(--text)] pl-6">{error.message}</p>
      <div className="flex items-center gap-3 pl-6 text-[12px]">
        {error.canOpenSettings && onOpenSettings && (
          <button
            type="button"
            onClick={onOpenSettings}
            className="font-medium text-[var(--accent)] hover:underline cursor-pointer"
          >
            Open Settings
          </button>
        )}
        {error.details && error.details !== error.message && (
          <button
            type="button"
            onClick={() => setShowErrorDetails((v) => !v)}
            className="text-[var(--text-secondary-color)] hover:text-[var(--text)] cursor-pointer"
          >
            {showErrorDetails ? 'Hide details' : 'Show details'}
          </button>
        )}
      </div>
      {showErrorDetails && error.details && (
        <pre className="pl-6 text-[12px] text-[var(--text-secondary-color)] whitespace-pre-wrap break-words font-mono select-text">
          {error.details}
        </pre>
      )}
    </div>
  ) : null;

  // Keyboard shortcut ⌘\ or Ctrl+\ to toggle sidebar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
        e.preventDefault();
        onToggle();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onToggle]);

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

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileUpload(file);
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileExtension = (name?: string) => {
    if (!name) return '';
    const parts = name.split('.');
    return parts.length > 1 ? parts.pop()?.toUpperCase() : '';
  };

  if (isSheet) {
    return (
      <AnimatePresence>
        {isOpen && (
          <div className="fixed inset-0 z-50 flex">
            {/* Scrim */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={onToggle}
              className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-40 cursor-pointer"
            />

            {/* Slide-over Sheet */}
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="relative z-50 w-[320px] max-w-[85vw] h-full bg-[var(--surface-solid)] border-r border-[var(--separator)] flex flex-col justify-between p-4 overflow-y-auto shadow-[var(--shadow-sheet)] select-none"
            >
              <div className="space-y-4">
                {/* Header: Title & Collapse Button */}
                <div className="flex items-center justify-between pb-1">
                  <span className="text-[15px] font-semibold text-[var(--text)]">
                    Process Input
                  </span>
                  <button
                    onClick={onToggle}
                    title="Close Sidebar"
                    className="w-7 h-7 rounded-[8px] flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                </div>

                {/* Drop Zone */}
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileInputChange}
                  accept=".txt,.md,.markdown,.csv,.docx,.xlsx,.pdf,.json,.srt,.vtt,.bpmn,.xml"
                  className="hidden"
                />
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`p-4 rounded-[12px] border border-dashed transition-all cursor-pointer text-center flex flex-col items-center justify-center gap-2 ${
                    isDragging
                      ? 'border-[var(--accent)] bg-[var(--accent-subtle)]'
                      : 'border-[var(--separator-strong)] bg-[var(--surface-subtle)] hover:bg-[var(--surface-solid)]'
                  }`}
                >
                  <div className="w-9 h-9 rounded-full bg-[var(--surface-solid)] flex items-center justify-center text-[var(--accent)] shadow-xs">
                    <Upload className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-[var(--text)]">
                      Drop file or click to browse
                    </p>
                    <p className="text-[13px] text-[var(--text-secondary-color)] mt-0.5">
                      .docx, .xlsx, .pdf, .csv, .txt, .md
                    </p>
                  </div>
                </div>

                {/* Detected File Info Caption */}
                {fileName && (
                  <div className="px-3 py-2 bg-[var(--surface-subtle)] rounded-[8px] flex items-center justify-between text-[12px]">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" />
                      <span className="truncate text-[var(--text)] font-medium text-[13px]">
                        {fileName}
                      </span>
                    </div>
                    <div className="shrink-0 text-[var(--text-secondary-color)] ml-2 text-[12px]">
                      {getFileExtension(fileName)} {fileSize ? `· ${formatFileSize(fileSize)}` : ''}
                    </div>
                  </div>
                )}

                {/* Inline Error */}
                {errorCard}

                {/* Raw Text Input Area */}
                <div>
                  <label className="text-[13px] font-medium text-[var(--text)] block mb-1.5">
                    Or paste process text
                  </label>

                  <Textarea
                    value={inputText}
                    onChange={(e) => onInputChange(e.target.value)}
                    placeholder="Paste steps, interview notes, or SOP..."
                    rows={8}
                  />
                </div>
              </div>

              {/* Primary Convert Button */}
              <div className="pt-4 border-t border-[var(--separator)]">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={onConvert}
                  isLoading={isLoading}
                  disabled={isLoading || (!inputText.trim() && !fileName)}
                  className="w-full"
                  icon={<Sparkles className="w-4 h-4" />}
                >
                  {isLoading ? 'Converting Process...' : 'Convert Process'}
                </Button>
              </div>
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
    );
  }

  return (
    <motion.aside
      initial={false}
      animate={{ width: isOpen ? 320 : 44 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="relative h-full bg-[var(--surface-solid)] border-r border-[var(--separator)] flex flex-col shrink-0 overflow-hidden z-20 select-none"
    >
      {/* Collapsed 44px Rail */}
      {!isOpen && (
        <div className="w-[44px] h-full flex flex-col items-center py-3 gap-3">
          <button
            onClick={onToggle}
            title="Expand Sidebar (⌘\)"
            className="w-8 h-8 rounded-[8px] flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
          <div className="w-5 h-px bg-[var(--separator)]" />
          <button
            onClick={() => fileInputRef.current?.click()}
            title="Upload File"
            className="w-8 h-8 rounded-[8px] flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
          >
            <Upload className="w-4 h-4" />
          </button>
          <button
            onClick={onToggle}
            title="Edit Input Text"
            className="w-8 h-8 rounded-[8px] flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
          >
            <FileText className="w-4 h-4" />
          </button>
          <div className="mt-auto">
            <button
              onClick={onConvert}
              disabled={isLoading || (!inputText.trim() && !fileName)}
              title="Convert Process"
              className="w-8 h-8 rounded-[8px] flex items-center justify-center bg-[var(--accent)] text-white disabled:opacity-50 transition-opacity cursor-pointer"
            >
              <Sparkles className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Expanded 320px Sidebar Content */}
      {isOpen && (
        <div className="w-[320px] h-full flex flex-col justify-between p-4 overflow-y-auto">
          <div className="space-y-4">
            {/* Header: Title & Collapse Button */}
            <div className="flex items-center justify-between pb-1">
              <span className="text-[13px] font-semibold text-[var(--text)]">
                Process Input
              </span>
              <button
                onClick={onToggle}
                title="Collapse Sidebar (⌘\)"
                className="w-7 h-7 rounded-[8px] flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>

            {/* Drop Zone */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileInputChange}
              accept=".txt,.md,.markdown,.csv,.docx,.xlsx,.pdf,.json,.srt,.vtt,.bpmn,.xml"
              className="hidden"
            />
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`p-4 rounded-[12px] border border-dashed transition-all cursor-pointer text-center flex flex-col items-center justify-center gap-2 ${
                isDragging
                  ? 'border-[var(--accent)] bg-[var(--accent-subtle)]'
                  : 'border-[var(--separator-strong)] bg-[var(--surface-subtle)] hover:bg-[var(--surface-solid)]'
              }`}
            >
              <div className="w-9 h-9 rounded-full bg-[var(--surface-solid)] flex items-center justify-center text-[var(--accent)] shadow-xs">
                <Upload className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[13px] font-medium text-[var(--text)]">
                  Drop file or click to browse
                </p>
                <p className="text-[13px] text-[var(--text-secondary-color)] mt-0.5">
                  .docx, .xlsx, .pdf, .csv, .txt, .md
                </p>
              </div>
            </div>

            {/* Detected File Info Caption */}
            {fileName && (
              <div className="px-3 py-2 bg-[var(--surface-subtle)] rounded-[8px] flex items-center justify-between text-[12px]">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" />
                  <span className="truncate text-[var(--text)] font-medium text-[13px]">
                    {fileName}
                  </span>
                </div>
                <div className="shrink-0 text-[var(--text-secondary-color)] ml-2 text-[12px]">
                  {getFileExtension(fileName)} {fileSize ? `· ${formatFileSize(fileSize)}` : ''}
                </div>
              </div>
            )}

            {/* Inline Error under Dropzone if any */}
            {errorCard}

            {/* Raw Text Input Area */}
            <div>
              <label className="text-[13px] font-medium text-[var(--text)] block mb-1.5">
                Or paste process text
              </label>

              <Textarea
                value={inputText}
                onChange={(e) => onInputChange(e.target.value)}
                placeholder="Paste steps, interview notes, or SOP..."
                rows={9}
              />
            </div>
          </div>

          {/* Primary Convert Button */}
          <div className="pt-4 border-t border-[var(--separator)]">
            <Button
              variant="primary"
              size="lg"
              onClick={onConvert}
              isLoading={isLoading}
              disabled={isLoading || (!inputText.trim() && !fileName)}
              className="w-full"
              icon={<Sparkles className="w-4 h-4" />}
            >
              {isLoading ? 'Converting Process...' : 'Convert Process'}
            </Button>
            <div className="text-center mt-2">
              <span className="text-[12px] text-[var(--text-tertiary)]">
                Shortcut: ⌘\ to toggle sidebar
              </span>
            </div>
          </div>
        </div>
      )}
    </motion.aside>
  );
};
