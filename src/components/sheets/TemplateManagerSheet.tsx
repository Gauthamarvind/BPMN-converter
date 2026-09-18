import React, { useState, useEffect, useRef } from 'react';
import {
  Upload,
  Trash2,
  Star,
  Download,
  ChevronDown,
  ChevronRight,
  FileCode,
  CheckCircle,
  AlertCircle,
  FileSpreadsheet,
  FileText,
} from 'lucide-react';
import { TemplateRecord, TemplateValidationReport } from '../../types';
import { Sheet } from '../ui/Sheet';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Input } from '../ui/Field';

export interface TemplateManagerSheetProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTemplate?: (templateId: string) => void;
  selectedTemplateId?: string;
}

export const TemplateManagerSheet: React.FC<TemplateManagerSheetProps> = ({
  isOpen,
  onClose,
  onSelectTemplate,
  selectedTemplateId,
}) => {
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [expandedTemplateId, setExpandedTemplateId] = useState<string | null>(null);

  // File upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [templateName, setTemplateName] = useState<string>('');
  const [templateDesc, setTemplateDesc] = useState<string>('');

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/templates');
      if (!res.ok) throw new Error('Failed to load templates');
      const data = await res.json();
      setTemplates(data.templates || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch templates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadTemplates();
      setError(null);
      setSuccessMsg(null);
      setSelectedFile(null);
      setTemplateName('');
      setTemplateDesc('');
    }
  }, [isOpen]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      if (!templateName) {
        setTemplateName(file.name.replace(/\.(bpmn|xml)$/, '').replace(/_/g, ' '));
      }
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a .bpmn or .xml diagram file.');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('name', templateName);
      formData.append('description', templateDesc);

      const res = await fetch('/api/templates', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Template registration failed');
      }

      const data = await res.json();
      setSuccessMsg(`Template "${data.template.name}" added successfully.`);
      setSelectedFile(null);
      setTemplateName('');
      setTemplateDesc('');
      loadTemplates();
    } catch (err: any) {
      setError(err.message || 'Failed to upload template.');
    } finally {
      setUploading(false);
    }
  };

  const handleSetDefault = async (templateId: string) => {
    try {
      const res = await fetch(`/api/templates/${templateId}/default`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to update default template');
      loadTemplates();
      setSuccessMsg('Default template updated.');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (templateId: string) => {
    if (!confirm('Are you sure you want to delete this template?')) return;
    try {
      const res = await fetch(`/api/templates/${templateId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete template');
      loadTemplates();
      setSuccessMsg('Template deleted.');
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <Sheet
      id="template-manager-sheet"
      isOpen={isOpen}
      onClose={onClose}
      title="BPMN Template Manager"
      subtitle="Corporate swimlane layouts, vendor profiles, and reference templates."
    >
      <div className="space-y-6 text-left">
        {/* Banner Messages */}
        {error && (
          <div className="p-3 bg-[var(--danger-subtle)] text-[var(--danger)] text-[12px] rounded-[8px] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="font-semibold cursor-pointer">
              &times;
            </button>
          </div>
        )}

        {successMsg && (
          <div className="p-3 bg-[var(--success-subtle)] text-[var(--success)] text-[12px] rounded-[8px] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
            <button onClick={() => setSuccessMsg(null)} className="font-semibold cursor-pointer">
              &times;
            </button>
          </div>
        )}

        {/* 1. Add Template Drop Zone */}
        <div className="space-y-3">
          <span className="text-[13px] font-semibold text-[var(--text)]">
            Add Reference Template
          </span>

          <form onSubmit={handleUpload} className="space-y-3">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".bpmn,.xml"
              className="hidden"
            />

            <div
              onClick={() => fileInputRef.current?.click()}
              className="p-4 rounded-[12px] border border-dashed border-[var(--separator-strong)] bg-[var(--surface-subtle)] hover:bg-[var(--surface-solid)] transition-colors cursor-pointer text-center flex flex-col items-center justify-center gap-1.5"
            >
              <Upload className="w-5 h-5 text-[var(--accent)]" />
              <span className="text-[13px] font-medium text-[var(--text)]">
                {selectedFile ? selectedFile.name : 'Choose or drop .bpmn / .xml diagram'}
              </span>
              <span className="text-[12px] text-[var(--text-secondary-color)]">
                Extracts swimlane geometry and vendor metadata
              </span>
            </div>

            {selectedFile && (
              <div className="space-y-2.5 pt-1">
                <Input
                  label="Template Name"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="e.g. Corporate Procurement Schema"
                  required
                />
                <Input
                  label="Description (Optional)"
                  value={templateDesc}
                  onChange={(e) => setTemplateDesc(e.target.value)}
                  placeholder="e.g. Standard 3-tier approval process with Finance lane"
                />
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  isLoading={uploading}
                  className="w-full"
                >
                  Register Template
                </Button>
              </div>
            )}
          </form>
        </div>

        {/* 2. Registered Template List */}
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between">
            <span className="text-[13px] font-semibold text-[var(--text)]">
              Registered Templates ({templates.length})
            </span>
            <span className="text-[12px] text-[var(--text-secondary-color)]">
              Select or configure defaults
            </span>
          </div>

          <div className="space-y-2">
            {templates.map((tpl) => {
              const isSelected = selectedTemplateId === tpl.id;
              const isExpanded = expandedTemplateId === tpl.id;

              return (
                <div
                  key={tpl.id}
                  className={`p-3.5 rounded-[12px] transition-all ${
                    isSelected
                      ? 'border border-[var(--accent)] bg-[var(--surface-solid)]'
                      : 'bg-[var(--surface-subtle)]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[13px] font-semibold text-[var(--text)]">
                          {tpl.name}
                        </span>
                        <Badge variant="neutral" size="sm">
                          {tpl.source_vendor.toUpperCase()}
                        </Badge>
                        {tpl.is_default && (
                          <Badge variant="accent" size="sm">
                            Default
                          </Badge>
                        )}
                      </div>

                      <div className="text-[12px] text-[var(--text-secondary-color)] mt-1 flex items-center gap-2">
                        <span>{tpl.lanes_count ?? 0} lanes</span>
                        <span>•</span>
                        <span>{tpl.skeleton_count ?? 0} gates</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleSetDefault(tpl.id)}
                        title={tpl.is_default ? 'Default template' : 'Set as default'}
                        className={`w-7 h-7 rounded-[8px] flex items-center justify-center transition-colors cursor-pointer ${
                          tpl.is_default
                            ? 'text-[var(--accent)]'
                            : 'text-[var(--text-tertiary)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)]'
                        }`}
                      >
                        <Star className="w-3.5 h-3.5 fill-current" />
                      </button>

                      <button
                        onClick={() => handleDelete(tpl.id)}
                        title="Delete template"
                        className="w-7 h-7 rounded-[8px] flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--danger)] hover:bg-[var(--danger-subtle)] transition-colors cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() =>
                          setExpandedTemplateId(isExpanded ? null : tpl.id)
                        }
                        title="Show technical specification"
                        className="w-7 h-7 rounded-[8px] flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--text)] transition-colors cursor-pointer"
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Progressive Disclosure: Template internals */}
                  {isExpanded && (
                    <div className="mt-3 pt-3 border-t border-[var(--separator)] text-[12px] space-y-2 text-[var(--text-secondary-color)]">
                      <div>
                        <span className="font-medium text-[var(--text)]">Filename:</span>{' '}
                        <span className="font-mono">{tpl.filename}</span>
                      </div>
                      {tpl.description && (
                        <div>
                          <span className="font-medium text-[var(--text)]">Description:</span>{' '}
                          {tpl.description}
                        </div>
                      )}
                      <div>
                        <span className="font-medium text-[var(--text)]">Derived profile:</span>{' '}
                        {tpl.derived_profile || 'generic'}
                      </div>
                      <div className="pt-1">
                        <a
                          href={`/api/templates/${tpl.id}/download`}
                          className="text-[var(--accent)] hover:underline inline-flex items-center gap-1 font-medium"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Download reference .bpmn</span>
                        </a>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Sheet>
  );
};
