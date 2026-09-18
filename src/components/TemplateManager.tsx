import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Layers,
  Upload,
  CheckCircle,
  AlertTriangle,
  FileCode,
  Trash2,
  Star,
  Download,
  Info,
  ExternalLink,
  RefreshCw,
  PlusCircle,
} from 'lucide-react';
import { TemplateRecord, TemplateValidationReport } from '../types';
import { InfoTooltip } from './InfoTooltip';

interface TemplateManagerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTemplate?: (templateId: string) => void;
  selectedTemplateId?: string;
}

export const TemplateManager: React.FC<TemplateManagerProps> = ({
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
  const [lastReport, setLastReport] = useState<TemplateValidationReport | null>(null);
  const [activeTab, setActiveTab] = useState<'library' | 'upload' | 'download'>('library');

  // Form states for upload
  const [uploadName, setUploadName] = useState<string>('');
  const [uploadDesc, setUploadDesc] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/templates');
      if (!res.ok) throw new Error('Failed to load templates');
      const data = await res.json();
      setTemplates(data.templates || []);
    } catch (err: any) {
      console.error(err);
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
      setLastReport(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      if (!uploadName) {
        setUploadName(file.name.replace(/\.(bpmn|xml)$/, '').replace(/_/g, ' '));
      }
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a .bpmn or .xml file to upload.');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('name', uploadName);
      formData.append('description', uploadDesc);

      const res = await fetch('/api/templates', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed: ${res.statusText}`);
      }

      const data = await res.json();
      setSuccessMsg(`Template "${data.template.name}" successfully registered and validated!`);
      setLastReport(data.report);
      setSelectedFile(null);
      setUploadName('');
      setUploadDesc('');
      loadTemplates();
      setActiveTab('library');
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to upload template.');
    } finally {
      setUploading(false);
    }
  };

  const handleSetDefault = async (templateId: string) => {
    try {
      const res = await fetch(`/api/templates/${templateId}/default`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to set default template');
      loadTemplates();
      setSuccessMsg('Default template updated.');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (templateId: string) => {
    if (!confirm('Are you sure you want to delete this reference template?')) return;
    try {
      const res = await fetch(`/api/templates/${templateId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete template');
      loadTemplates();
      setSuccessMsg('Template deleted.');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDownloadBlank = (type: 'xlsx' | 'docx') => {
    window.location.href = `/api/templates/download-blank?type=${type}&sample=true`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        id="template-manager-modal"
        className="w-full max-w-3xl bg-white rounded-2xl shadow-2xl border border-stone-200 overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-stone-200 flex items-center justify-between bg-stone-50/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center border border-purple-200 shadow-2xs">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-stone-900">BPMN Template Manager</h2>
                <span className="px-2 py-0.5 bg-purple-100/70 text-purple-800 rounded-full text-[10px] font-bold">
                  Opt-in
                </span>
                <InfoTooltip
                  title="Template Mode"
                  content="Upload and select BPMN 2.0 reference templates (from Signavio, Camunda, ARIS, Celonis) to ensure generated diagrams preserve standard corporate swimlanes, layouts, and skeleton gates."
                />
              </div>
              <p className="text-xs text-stone-500">
                Manage reference BPMN schemas, swimlanes, and blank structured capture forms.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-stone-400 hover:text-stone-700 hover:bg-stone-200 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Navigation Tabs */}
        <div className="px-6 pt-3 border-b border-stone-200 flex items-center gap-2 bg-stone-50/40 text-xs font-semibold">
          <button
            id="tab-template-library"
            onClick={() => setActiveTab('library')}
            className={`pb-2 px-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'library'
                ? 'border-purple-600 text-purple-700 font-bold'
                : 'border-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            <FileCode className="w-4 h-4" />
            Template Library ({templates.length})
            <InfoTooltip content="All registered reference templates available for diagram alignment." />
          </button>
          <button
            id="tab-template-upload"
            onClick={() => setActiveTab('upload')}
            className={`pb-2 px-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'upload'
                ? 'border-purple-600 text-purple-700 font-bold'
                : 'border-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            <PlusCircle className="w-4 h-4" />
            Upload New Template
            <InfoTooltip content="Register your company's existing .bpmn or .xml diagram as an active reference template." />
          </button>
          <button
            id="tab-template-download"
            onClick={() => setActiveTab('download')}
            className={`pb-2 px-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'download'
                ? 'border-purple-600 text-purple-700 font-bold'
                : 'border-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            <Download className="w-4 h-4" />
            Blank Capture Forms
            <InfoTooltip content="Download pre-configured Excel (.xlsx) and Word (.docx) process inventory templates for structured text-free input." />
          </button>
        </div>

        {/* Banner notices */}
        {error && (
          <div className="mx-6 mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-red-500 font-bold">&times;</button>
          </div>
        )}
        {successMsg && (
          <div className="mx-6 mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>{successMsg}</span>
            </div>
            <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 font-bold">&times;</button>
          </div>
        )}

        {/* Content Area */}
        <div className="p-6 overflow-y-auto flex-1">
          {/* TAB 1: Library */}
          {activeTab === 'library' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-stone-500">
                  Select a template to inspect details, set as default, or apply directly to your current workflow.
                </p>
                <button
                  onClick={loadTemplates}
                  className="text-xs text-stone-500 hover:text-stone-800 flex items-center gap-1 p-1 hover:bg-stone-100 rounded"
                  title="Refresh templates"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
              </div>

              {templates.length === 0 ? (
                <div className="py-12 text-center text-stone-400 text-xs">
                  No templates found. Click "Upload New Template" to add one.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {templates.map((tpl) => {
                    const isSelected = selectedTemplateId === tpl.id;
                    const vendorColor =
                      tpl.source_vendor === 'camunda'
                        ? 'bg-orange-50 text-orange-700 border-orange-200'
                        : tpl.source_vendor === 'signavio'
                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                        : tpl.source_vendor === 'celonis'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-purple-50 text-purple-700 border-purple-200';

                    return (
                      <div
                        key={tpl.id}
                        className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between ${
                          isSelected
                            ? 'bg-purple-50/50 border-purple-400 ring-2 ring-purple-500/20'
                            : 'bg-stone-50/50 hover:bg-stone-50 border-stone-200'
                        }`}
                      >
                        <div>
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <div>
                              <h4 className="text-sm font-bold text-stone-900 leading-tight">
                                {tpl.name}
                              </h4>
                              <p className="text-[11px] text-stone-500 mt-0.5 line-clamp-1">
                                {tpl.description || tpl.filename}
                              </p>
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold border uppercase tracking-wider ${vendorColor}`}
                              >
                                {tpl.source_vendor}
                              </span>
                              {tpl.is_default && (
                                <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-[10px] font-bold flex items-center gap-0.5">
                                  <Star className="w-2.5 h-2.5 fill-amber-500 text-amber-500" />
                                  Default
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Metrics / Schema features */}
                          <div className="grid grid-cols-3 gap-1.5 py-2 px-2.5 bg-white rounded-lg border border-stone-200/80 text-[11px] text-stone-600 mb-3">
                            <div className="flex flex-col">
                              <span className="text-[10px] text-stone-400 uppercase font-semibold">Pools</span>
                              <span className="font-bold text-stone-800">{tpl.pools_count ?? 1}</span>
                            </div>
                            <div className="flex flex-col">
                              <span className="text-[10px] text-stone-400 uppercase font-semibold">Lanes</span>
                              <span className="font-bold text-stone-800">{tpl.lanes_count ?? 0}</span>
                            </div>
                            <div className="flex flex-col">
                              <span className="text-[10px] text-stone-400 uppercase font-semibold">Skeleton</span>
                              <span className="font-bold text-stone-800">{tpl.skeleton_count ?? 0}</span>
                            </div>
                          </div>
                        </div>

                        {/* Bottom Actions */}
                        <div className="flex items-center justify-between pt-2 border-t border-stone-200/60 text-xs">
                          <div className="flex items-center gap-1">
                            {!tpl.is_default && (
                              <button
                                type="button"
                                onClick={() => handleSetDefault(tpl.id)}
                                className="px-2 py-1 text-[11px] font-medium text-stone-600 hover:text-amber-800 hover:bg-amber-50 rounded transition-colors"
                              >
                                Set as Default
                              </button>
                            )}
                            {tpl.id.startsWith('tpl_') && (
                              <button
                                type="button"
                                onClick={() => handleDelete(tpl.id)}
                                className="p-1 text-stone-400 hover:text-red-600 rounded hover:bg-red-50 transition-colors"
                                title="Delete custom template"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>

                          {onSelectTemplate && (
                            <button
                              type="button"
                              onClick={() => {
                                onSelectTemplate(tpl.id);
                                onClose();
                              }}
                              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                                isSelected
                                  ? 'bg-purple-600 text-white shadow-xs'
                                  : 'bg-white hover:bg-purple-50 text-purple-700 border border-purple-200'
                              }`}
                            >
                              {isSelected ? 'Active Template' : 'Use Template'}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Upload */}
          {activeTab === 'upload' && (
            <form onSubmit={handleUploadSubmit} className="space-y-4 max-w-xl mx-auto">
              <div className="bg-stone-50 p-4 border border-stone-200 rounded-xl space-y-3">
                <div className="flex items-center gap-1.5">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-stone-700">
                    Upload BPMN 2.0 XML File
                  </h3>
                  <InfoTooltip content="Supported formats: .bpmn and .xml. The file must contain valid BPMN 2.0 XML with definitions, collaboration pools, and diagram bounds." />
                </div>

                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-stone-300 hover:border-purple-500 rounded-xl p-6 text-center cursor-pointer transition-colors bg-white group"
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    accept=".bpmn,.xml"
                    className="hidden"
                  />
                  <Upload className="w-8 h-8 text-stone-400 group-hover:text-purple-600 mx-auto mb-2 transition-colors" />
                  {selectedFile ? (
                    <div>
                      <p className="text-sm font-semibold text-stone-900">{selectedFile.name}</p>
                      <p className="text-xs text-stone-400">{(selectedFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-sm font-semibold text-stone-700 group-hover:text-purple-700">
                        Click or drag BPMN reference file here
                      </p>
                      <p className="text-xs text-stone-400 mt-1">.bpmn or .xml up to 10 MB</p>
                    </div>
                  )}
                </div>

                <div className="space-y-3 pt-2">
                  <div>
                    <label className="block text-xs font-semibold text-stone-700 mb-1 flex items-center gap-1">
                      Template Display Name
                      <InfoTooltip content="Human-readable label displayed in the template selector dropdown." />
                    </label>
                    <input
                      type="text"
                      value={uploadName}
                      onChange={(e) => setUploadName(e.target.value)}
                      placeholder="e.g., Corporate Standard Approvals Template"
                      className="w-full px-3 py-2 text-xs bg-white border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-stone-700 mb-1 flex items-center gap-1">
                      Description & Notes (Optional)
                      <InfoTooltip content="Additional guidance on when to use this template or which department owns it." />
                    </label>
                    <textarea
                      value={uploadDesc}
                      onChange={(e) => setUploadDesc(e.target.value)}
                      placeholder="Describe target vendor, swimlane rules, or compliance standards..."
                      rows={2}
                      className="w-full px-3 py-2 text-xs bg-white border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                    />
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    type="submit"
                    disabled={uploading || !selectedFile}
                    className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                  >
                    {uploading ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Validating & Saving...
                      </>
                    ) : (
                      <>
                        <Upload className="w-3.5 h-3.5" />
                        Save Template
                      </>
                    )}
                  </button>
                </div>
              </div>

              {lastReport && (
                <div className="p-4 bg-purple-50 border border-purple-200 rounded-xl space-y-2 text-xs">
                  <div className="flex items-center gap-2 font-bold text-purple-900">
                    <CheckCircle className="w-4 h-4 text-purple-600" />
                    Validation Report: {lastReport.name}
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-stone-700">
                    <div>Pools: <span className="font-semibold">{lastReport.pools_found}</span></div>
                    <div>Lanes: <span className="font-semibold">{lastReport.lanes_found}</span></div>
                    <div>Fixed Skeletons: <span className="font-semibold">{lastReport.skeleton_nodes_found}</span></div>
                  </div>
                  {lastReport.warnings.length > 0 && (
                    <div className="text-amber-700 bg-amber-50 p-2 rounded border border-amber-200">
                      {lastReport.warnings.map((w, i) => (
                        <p key={i}>• {w}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </form>
          )}

          {/* TAB 3: Download blank forms */}
          {activeTab === 'download' && (
            <div className="space-y-4 max-w-xl mx-auto py-2">
              <div className="bg-stone-50 border border-stone-200 rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center border border-emerald-200">
                    <Download className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-stone-900">Structured Process Capture Forms</h3>
                    <p className="text-xs text-stone-500">
                      Eliminate ambiguity by letting stakeholders fill standardized tabular templates.
                    </p>
                  </div>
                </div>

                <p className="text-xs text-stone-600 leading-relaxed">
                  These templates define recognized columns (<code>Step #</code>, <code>Task Name</code>,{' '}
                  <code>Actor / Lane</code>, <code>Type</code>, <code>Next Steps</code>, <code>Condition</code>).
                  Files uploaded in this format bypass LLM text extraction and convert deterministically into ProcessIR.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                  <div className="p-3 bg-white border border-stone-200 rounded-lg flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-stone-900">Excel Worksheet (.xlsx)</span>
                        <InfoTooltip content="Standard spreadsheet format with pre-populated sample rows and column drop-down guides." />
                      </div>
                      <p className="text-[11px] text-stone-500">
                        Multi-column tabular format with example claim-processing workflow.
                      </p>
                    </div>
                    <button
                      type="button"
                      id="download-blank-xlsx-btn"
                      onClick={() => handleDownloadBlank('xlsx')}
                      className="mt-3 w-full px-3 py-2 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download Excel Template
                    </button>
                  </div>

                  <div className="p-3 bg-white border border-stone-200 rounded-lg flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-stone-900">Word Document (.docx)</span>
                        <InfoTooltip content="Standard Word document with an embedded structured process table and instruction notes." />
                      </div>
                      <p className="text-[11px] text-stone-500">
                        Formatted procedure document with embedded steps table.
                      </p>
                    </div>
                    <button
                      type="button"
                      id="download-blank-docx-btn"
                      onClick={() => handleDownloadBlank('docx')}
                      className="mt-3 w-full px-3 py-2 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download Word Template
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-stone-200 bg-stone-50/80 flex items-center justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-stone-700 hover:bg-stone-200/70 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
