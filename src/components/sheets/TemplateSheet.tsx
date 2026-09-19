import React, { useState } from 'react';
import {
  FileSpreadsheet,
  FileText,
  Download,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { Sheet } from '../ui/Sheet';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

export interface TemplateSheetProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenTemplateManager?: () => void;
}

/**
 * Scope v2: one Template page. A blank capture form (Excel and Word) plus a single filled-in
 * example process. Sample workflows and the in-browser Step Builder were removed.
 */
export const TemplateSheet: React.FC<TemplateSheetProps> = ({
  isOpen,
  onClose,
  onOpenTemplateManager,
}) => {
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

  return (
    <Sheet
      id="template-sheet"
      isOpen={isOpen}
      onClose={onClose}
      title="Process capture template"
      subtitle="Fill in the form, drop it back on the canvas, and it is converted by rules — no model call."
    >
      <div className="space-y-8 text-left">
        {/* Blank forms */}
        <div className="space-y-4">
          <div>
            <h3 className="text-[15px] font-semibold text-[var(--text)] flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-[var(--accent)]" />
              Blank form
            </h3>
            <p className="text-[12px] text-[var(--text-secondary-color)] mt-0.5">
              One row per step: Step ID, Step, Responsible, Type, decision targets and Next Step.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] transition-all flex flex-col justify-between gap-3">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[14px] font-medium text-[var(--text)] flex items-center gap-1.5">
                    <FileSpreadsheet className="w-4 h-4 text-[var(--success)]" />
                    Excel form
                  </span>
                  <Badge variant="accent" size="sm">
                    .XLSX
                  </Badge>
                </div>
                <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                  Tabular form with Role and Type dropdowns, decision targets and metadata columns.
                </p>
              </div>
              <div className="flex items-center gap-2 pt-1 border-t border-[var(--separator)]">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-[12px]"
                  icon={<Download className="w-3.5 h-3.5" />}
                  disabled={downloadingId === 'Process_Capture_Template.xlsx'}
                  onClick={() =>
                    handleDownloadFile(
                      '/api/templates/download-blank?type=xlsx&sample=false',
                      'Process_Capture_Template.xlsx'
                    )
                  }
                >
                  Download blank (.xlsx)
                </Button>
              </div>
            </div>

            <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] transition-all flex flex-col justify-between gap-3">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[14px] font-medium text-[var(--text)] flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-[var(--accent)]" />
                    Word form
                  </span>
                  <Badge variant="accent" size="sm">
                    .DOCX
                  </Badge>
                </div>
                <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                  SOP document with formatted headings and the same step table as the workbook.
                </p>
              </div>
              <div className="flex items-center gap-2 pt-1 border-t border-[var(--separator)]">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-[12px]"
                  icon={<Download className="w-3.5 h-3.5" />}
                  disabled={downloadingId === 'Process_Capture_Template.docx'}
                  onClick={() =>
                    handleDownloadFile(
                      '/api/templates/download-blank?type=docx&sample=false',
                      'Process_Capture_Template.docx'
                    )
                  }
                >
                  Download blank (.docx)
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Single filled example */}
        <div className="space-y-4 pt-2">
          <div>
            <h3 className="text-[15px] font-semibold text-[var(--text)] flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-[var(--accent)]" />
              Filled-in example
            </h3>
            <p className="text-[12px] text-[var(--text-secondary-color)] mt-0.5">
              An employee leave request, showing a decision, swimlanes and a parallel group.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] transition-all flex flex-col justify-between gap-3">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[14px] font-medium text-[var(--text)] flex items-center gap-1.5">
                    <FileSpreadsheet className="w-4 h-4 text-[var(--success)]" />
                    Leave request (Excel)
                  </span>
                  <Badge variant="neutral" size="sm">
                    .XLSX
                  </Badge>
                </div>
                <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                  Open it to see how decisions, roles and parallel steps are written down.
                </p>
              </div>
              <div className="flex items-center gap-2 pt-1 border-t border-[var(--separator)]">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-[12px]"
                  icon={<Download className="w-3.5 h-3.5" />}
                  disabled={downloadingId === 'Process_Capture_Template_Example.xlsx'}
                  onClick={() =>
                    handleDownloadFile(
                      '/api/templates/download-blank?type=xlsx&sample=true',
                      'Process_Capture_Template_Example.xlsx'
                    )
                  }
                >
                  Download example (.xlsx)
                </Button>
              </div>
            </div>

            <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] hover:border-[var(--accent)] transition-all flex flex-col justify-between gap-3">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[14px] font-medium text-[var(--text)] flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-[var(--text-secondary-color)]" />
                    Leave request (Word)
                  </span>
                  <Badge variant="neutral" size="sm">
                    .DOCX
                  </Badge>
                </div>
                <p className="text-[12px] text-[var(--text-secondary-color)] mt-1.5 leading-relaxed">
                  The same example as an SOP document, if your team captures processes in Word.
                </p>
              </div>
              <div className="flex items-center gap-2 pt-1 border-t border-[var(--separator)]">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-[12px]"
                  icon={<Download className="w-3.5 h-3.5" />}
                  disabled={downloadingId === 'Process_Capture_Template_Example.docx'}
                  onClick={() =>
                    handleDownloadFile(
                      '/api/templates/download-blank?type=docx&sample=true',
                      'Process_Capture_Template_Example.docx'
                    )
                  }
                >
                  Download example (.docx)
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Reference BPMN templates */}
        {onOpenTemplateManager && (
          <div className="p-4 rounded-[12px] border border-[var(--separator)] bg-[var(--surface-subtle)] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Layers className="w-4 h-4 text-[var(--accent)]" />
              <div>
                <div className="text-[13px] font-medium text-[var(--text)]">
                  Reference BPMN templates
                </div>
                <div className="text-[12px] text-[var(--text-secondary-color)]">
                  Upload a reference diagram to reuse its pools, lanes and namespaces.
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
