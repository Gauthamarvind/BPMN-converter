import React, { useState, useEffect } from 'react';
import {
  FileSpreadsheet,
  FileText,
  Download,
  BookOpen,
  Sparkles,
  Layers,
  ArrowRight,
  Check,
  FileCode,
  Table,
  CheckCircle,
} from 'lucide-react';
import { SampleFile } from '../../types';
import { Sheet } from '../ui/Sheet';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

export interface TemplatesAndSamplesSheetProps {
  isOpen: boolean;
  onClose: () => void;
  samples: SampleFile[];
  onSelectSample: (sample: SampleFile) => void;
  onOpenStepBuilder?: () => void;
  onOpenTemplateManager?: () => void;
  currentFilename?: string;
}

export const TemplatesAndSamplesSheet: React.FC<TemplatesAndSamplesSheetProps> = ({
  isOpen,
  onClose,
  samples,
  onSelectSample,
  onOpenStepBuilder,
  onOpenTemplateManager,
  currentFilename,
}) => {
  const [activeTab, setActiveTab] = useState<'all' | 'templates' | 'samples'>('all');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const handleDownloadFile = (url: string, filename: string) => {
    setDownloadingId(filename);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => setDownloadingId(null), 1000);
  };

  const handleSelectAndClose = (sample: SampleFile) => {
    onSelectSample(sample);
    onClose();
  };

  const getFormatBadgeVariant = (ext?: string): 'neutral' | 'accent' | 'danger' | 'success' => {
    const e = ext?.toLowerCase() || '';
    if (e.includes('xlsx') || e.includes('excel')) return 'accent';
    if (e.includes('docx') || e.includes('word')) return 'accent';
    if (e.includes('pdf')) return 'danger';
    if (e.includes('csv')) return 'success';
    return 'neutral';
  };

  return (
    <Sheet
      id="templates-and-samples-sheet"
      isOpen={isOpen}
      onClose={onClose}
      title="Templates & Sample Workflows"
      subtitle="Download standardized process capture forms, try sample workflows, or launch the interactive Step Builder."
    >
      <div className="space-y-8 text-left">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 border-b border-[var(--separator)] pb-2">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-[8px] text-[13px] font-medium transition-colors cursor-pointer ${
              activeTab === 'all'
                ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
                : 'text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)]'
            }`}
          >
            All Resources
          </button>
          <button
            onClick={() => setActiveTab('templates')}
            className={`px-3 py-1.5 rounded-[8px] text-[13px] font-medium transition-colors cursor-pointer ${
              activeTab === 'templates'
                ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
                : 'text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)]'
            }`}
          >
            Capture Templates
          </button>
          <button
            onClick={() => setActiveTab('samples')}
            className={`px-3 py-1.5 rounded-[8px] text-[13px] font-medium transition-colors cursor-pointer ${
              activeTab === 'samples'
                ? 'bg-[var(--accent-subtle)] text-[var(--accent)]'
                : 'text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)]'
            }`}
          >
            Sample Processes ({samples.length})
          </button>
        </div>

        {/* SECTION 1: DOWNLOADABLE CAPTURE TEMPLATES */}
        {(activeTab === 'all' || activeTab === 'templates') && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-[15px] font-semibold text-[var(--text)] flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-[var(--accent)]" />
                  Process Capture Templates
                </h3>
                <p className="text-[12px] text-[var(--text-secondary-color)] mt-0.5">
                  Standardized workbooks and documents for step-by-step process interviews.
                </p>
              </div>

              {onOpenStepBuilder && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Table className="w-3.5 h-3.5" />}
                  onClick={() => {
                    onClose();
                    onOpenStepBuilder();
                  }}
                >
                  Open in Step Builder
                </Button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Blank Excel Form */}
              <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] transition-all flex flex-col justify-between gap-3">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[14px] font-medium text-[var(--text)] flex items-center gap-1.5">
                      <FileSpreadsheet className="w-4 h-4 text-[var(--success)]" />
                      Excel Template
                    </span>
                    <Badge variant="accent" size="sm">
                      .XLSX (Blank)
                    </Badge>
                  </div>
                  <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                    Ready-to-use tabular form with Role dropdowns, decision targets, and metadata columns.
                  </p>
                </div>
                <div className="flex items-center gap-2 pt-1 border-t border-[var(--separator)]">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-[12px]"
                    icon={<Download className="w-3.5 h-3.5" />}
                    onClick={() =>
                      handleDownloadFile(
                        '/api/templates/download-blank?type=xlsx&sample=false',
                        'Process_Capture_Template.xlsx'
                      )
                    }
                  >
                    Download Blank (.xlsx)
                  </Button>
                </div>
              </div>

              {/* Filled Excel Example */}
              <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] transition-all flex flex-col justify-between gap-3">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[14px] font-medium text-[var(--text)] flex items-center gap-1.5">
                      <FileSpreadsheet className="w-4 h-4 text-[var(--accent)]" />
                      Leave Request Example
                    </span>
                    <Badge variant="neutral" size="sm">
                      .XLSX (Filled)
                    </Badge>
                  </div>
                  <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                    Reference leave request process showing gateways, swimlanes, and parallel groups.
                  </p>
                </div>
                <div className="flex items-center gap-2 pt-1 border-t border-[var(--separator)]">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-[12px]"
                    icon={<Download className="w-3.5 h-3.5" />}
                    onClick={() =>
                      handleDownloadFile(
                        '/api/templates/download-blank?type=xlsx&sample=true',
                        'Process_Capture_Template_Example.xlsx'
                      )
                    }
                  >
                    Download Example (.xlsx)
                  </Button>
                </div>
              </div>

              {/* Blank Word Document */}
              <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] transition-all flex flex-col justify-between gap-3">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[14px] font-medium text-[var(--text)] flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-[var(--accent)]" />
                      Word Document Form
                    </span>
                    <Badge variant="accent" size="sm">
                      .DOCX (Blank)
                    </Badge>
                  </div>
                  <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                    SOP document template with formatted headings and a structured process step table.
                  </p>
                </div>
                <div className="flex items-center gap-2 pt-1 border-t border-[var(--separator)]">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-[12px]"
                    icon={<Download className="w-3.5 h-3.5" />}
                    onClick={() =>
                      handleDownloadFile(
                        '/api/templates/download-blank?type=docx&sample=false',
                        'Process_Capture_Template.docx'
                      )
                    }
                  >
                    Download Blank (.docx)
                  </Button>
                </div>
              </div>

              {/* Filled Word Example */}
              <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] transition-all flex flex-col justify-between gap-3">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[14px] font-medium text-[var(--text)] flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-[var(--text-secondary-color)]" />
                      Word Example SOP
                    </span>
                    <Badge variant="neutral" size="sm">
                      .DOCX (Filled)
                    </Badge>
                  </div>
                  <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                    Pre-filled SOP document with step table and responsible role definitions.
                  </p>
                </div>
                <div className="flex items-center gap-2 pt-1 border-t border-[var(--separator)]">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-[12px]"
                    icon={<Download className="w-3.5 h-3.5" />}
                    onClick={() =>
                      handleDownloadFile(
                        '/api/templates/download-blank?type=docx&sample=true',
                        'Process_Capture_Template_Example.docx'
                      )
                    }
                  >
                    Download Example (.docx)
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SECTION 2: READY-TO-CONVERT SAMPLES */}
        {(activeTab === 'all' || activeTab === 'samples') && (
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-[15px] font-semibold text-[var(--text)] flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[var(--accent)]" />
                  Ready-to-Convert Sample Processes
                </h3>
                <p className="text-[12px] text-[var(--text-secondary-color)] mt-0.5">
                  Click any sample to load it into the engine and generate a BPMN diagram.
                </p>
              </div>
            </div>

            <div className="space-y-2.5">
              {samples.map((sample) => {
                const isCurrent = currentFilename === sample.name;
                return (
                  <div
                    key={sample.name}
                    id={`sample-card-${sample.name}`}
                    className={`p-3.5 rounded-[12px] border transition-all flex items-start justify-between gap-4 ${
                      isCurrent
                        ? 'border-[var(--accent)] bg-[var(--accent-subtle)]'
                        : 'border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] hover:bg-[var(--surface-solid)]'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[14px] font-medium text-[var(--text)]">
                          {sample.title || sample.name}
                        </span>
                        <Badge
                          variant={getFormatBadgeVariant(sample.type || sample.extension)}
                          size="sm"
                        >
                          {(sample.type || sample.extension).toUpperCase()}
                        </Badge>
                        <span className="text-[12px] font-mono text-[var(--text-tertiary)]">
                          {sample.name}
                        </span>
                        {isCurrent && (
                          <Badge variant="accent" size="sm" icon={<Check className="w-3 h-3" />}>
                            Active
                          </Badge>
                        )}
                      </div>
                      <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                        {sample.description || `Sample process workflow document.`}
                      </p>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0 self-center">
                      {sample.download_url && (
                        <button
                          onClick={() =>
                            handleDownloadFile(sample.download_url!, sample.name)
                          }
                          title="Download sample source file"
                          className="p-1.5 rounded-[8px] text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                      )}
                      <Button
                        variant={isCurrent ? 'secondary' : 'primary'}
                        size="sm"
                        icon={<Sparkles className="w-3.5 h-3.5" />}
                        onClick={() => handleSelectAndClose(sample)}
                      >
                        {isCurrent ? 'Reload' : 'Load & Convert'}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Reference Templates Quick Link */}
        {onOpenTemplateManager && (
          <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Layers className="w-4 h-4 text-[var(--accent)]" />
              <div>
                <div className="text-[13px] font-medium text-[var(--text)]">
                  Enterprise Vendor Reference Templates
                </div>
                <div className="text-[12px] text-[var(--text-secondary-color)]">
                  Manage custom BPMN XML templates for Signavio, Camunda, Celonis, and ARIS.
                </div>
              </div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              icon={<ArrowRight className="w-3.5 h-3.5" />}
              onClick={() => {
                onClose();
                onOpenTemplateManager();
              }}
            >
              Manage
            </Button>
          </div>
        )}
      </div>
    </Sheet>
  );
};
