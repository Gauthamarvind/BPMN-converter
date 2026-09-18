import React, { useRef, useEffect } from 'react';
import { FlowNode, SampleFile, TemplateRecord } from '../types';
import {
  FileText,
  Upload,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  Quote,
  Target,
  Download,
  FileSpreadsheet,
} from 'lucide-react';
import { InfoTooltip } from './InfoTooltip';
import { TemplateSelector } from './TemplateSelector';

interface SourceViewerProps {
  inputText: string;
  setInputText: (text: string) => void;
  samples: SampleFile[];
  onSelectSample: (sample: SampleFile) => void;
  onFileUpload: (file: File) => void;
  onConvert: () => void;
  loading: boolean;
  activeTab: 'input' | 'traceability';
  setActiveTab: (tab: 'input' | 'traceability') => void;
  normalizedText?: string;
  selectedNode?: FlowNode;
  elements?: FlowNode[];
  onSelectNodeById?: (id: string) => void;
  // Template mode props
  templates?: TemplateRecord[];
  selectedTemplateId?: string;
  onSelectTemplate?: (templateId: string) => void;
  onOpenTemplateManager?: () => void;
  onOpenLaneMapping?: () => void;
  hasActors?: boolean;
}

export const SourceViewer: React.FC<SourceViewerProps> = ({
  inputText,
  setInputText,
  samples,
  onSelectSample,
  onFileUpload,
  onConvert,
  loading,
  activeTab,
  setActiveTab,
  normalizedText,
  selectedNode,
  elements = [],
  onSelectNodeById,
  templates = [],
  selectedTemplateId = '',
  onSelectTemplate = () => {},
  onOpenTemplateManager = () => {},
  onOpenLaneMapping = () => {},
  hasActors = false,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to highlighted snippet when selectedNode changes
  useEffect(() => {
    if (activeTab === 'traceability' && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [selectedNode, activeTab]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileUpload(file);
    }
  };

  const displayText = normalizedText || inputText;
  const lines = displayText.split('\n');

  // Find line index matching source snippet
  const snippet = selectedNode?.source_snippet?.toLowerCase().trim();
  const highlightedLineIndex = snippet
    ? lines.findIndex(
        (l) =>
          l.toLowerCase().includes(snippet) ||
          (snippet.length > 20 && l.toLowerCase().includes(snippet.slice(0, 30)))
      )
    : -1;

  return (
    <div
      id="source-viewer-panel"
      className="w-full h-full flex flex-col bg-white border border-stone-200 rounded-xl overflow-hidden shadow-xs"
    >
      {/* Top Header & Mode Tabs */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-stone-50 border-b border-stone-200">
        <div className="flex items-center gap-1 bg-stone-200/70 p-0.5 rounded-lg text-xs font-medium">
          <button
            id="tab-source-input"
            onClick={() => setActiveTab('input')}
            className={`px-3 py-1 rounded-md transition-all flex items-center gap-1 ${
              activeTab === 'input'
                ? 'bg-white text-stone-900 shadow-xs font-semibold'
                : 'text-stone-600 hover:text-stone-900'
            }`}
          >
            <span>Source Input</span>
            <InfoTooltip
              title="Process Input"
              content="Provide unstructured text (SOP, interview notes) or structured files (.xlsx, .csv, .docx) to convert into BPMN 2.0."
            />
          </button>
          <button
            id="tab-source-traceability"
            onClick={() => setActiveTab('traceability')}
            className={`px-3 py-1 rounded-md transition-all flex items-center gap-1.5 ${
              activeTab === 'traceability'
                ? 'bg-white text-stone-900 shadow-xs font-semibold'
                : 'text-stone-600 hover:text-stone-900'
            }`}
          >
            <Target className="w-3.5 h-3.5 text-blue-600" />
            <span>Traceability</span>
            {elements.length > 0 && (
              <span className="ml-0.5 px-1.5 py-0.2 bg-blue-100 text-blue-700 rounded-full text-[10px] font-bold">
                {elements.length}
              </span>
            )}
            <InfoTooltip
              title="Evidence Traceability Matrix"
              content="Inspect exactly which line or paragraph of your source document produced each BPMN task or gateway, with confidence scores."
            />
          </button>
        </div>

        {activeTab === 'input' && (
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".txt,.md,.markdown,.csv,.docx,.xlsx,.srt,.vtt,.json"
              className="hidden"
            />
            <div className="flex items-center gap-1">
              <button
                id="upload-doc-btn"
                onClick={() => fileInputRef.current?.click()}
                className="px-2.5 py-1 text-xs font-medium text-stone-700 bg-white hover:bg-stone-100 border border-stone-200 rounded-md transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
              >
                <Upload className="w-3.5 h-3.5 text-stone-500" />
                <span>Upload Document</span>
              </button>
              <InfoTooltip
                title="Document Upload"
                content="Upload standard SOPs (.md, .txt), transcripts (.vtt), or structured tabular forms (.xlsx, .csv, .docx). Structured files are parsed deterministically."
              />
            </div>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {activeTab === 'input' ? (
        <div className="flex-1 flex flex-col p-3.5 overflow-hidden space-y-3">
          {/* SECTION 1: Sample Quick Loaders */}
          <div className="p-2.5 bg-stone-50/70 border border-stone-200/80 rounded-xl">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-stone-600 flex items-center gap-1">
                <BookOpen className="w-3.5 h-3.5 text-stone-400" />
                Sample Workflows
                <InfoTooltip
                  title="Real-World Process Templates"
                  content="Click any sample to instantly load multi-role SOP workflows (Order-to-Cash, Loan Approval, Incident Response) for testing."
                />
              </span>
              <span className="text-[10px] text-stone-400">or enter your process below</span>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              {samples.slice(0, 3).map((s) => (
                <button
                  key={s.name}
                  onClick={() => onSelectSample(s)}
                  className="text-left px-2 py-1.5 bg-white hover:bg-blue-50/60 hover:border-blue-200 border border-stone-200/80 rounded-lg transition-all group shadow-2xs"
                >
                  <p className="text-xs font-medium text-stone-800 group-hover:text-blue-700 truncate">
                    {s.title}
                  </p>
                  <p className="text-[9px] text-stone-400 uppercase tracking-wider">
                    {s.extension.replace('.', '')}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* SECTION 2: Reference Template Mode (Opt-in) */}
          <TemplateSelector
            templates={templates}
            selectedTemplateId={selectedTemplateId}
            onSelectTemplate={onSelectTemplate}
            onOpenManager={onOpenTemplateManager}
            onOpenLaneMapping={onOpenLaneMapping}
            hasActors={hasActors}
          />

          {/* SECTION 3: Process Text Input Area */}
          <div className="flex-1 flex flex-col min-h-0 border border-stone-200 rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500 transition-all bg-white">
            <div className="px-3 py-1.5 bg-stone-50/60 border-b border-stone-100 flex items-center justify-between text-[11px] text-stone-500">
              <span className="font-semibold text-stone-700 flex items-center gap-1">
                <FileText className="w-3.5 h-3.5 text-stone-400" />
                Process Description Text
              </span>
              <div className="flex items-center gap-2">
                <a
                  href="/api/templates/download-blank?type=xlsx&sample=true"
                  download
                  className="text-[10px] text-emerald-700 hover:text-emerald-900 hover:underline flex items-center gap-1 font-medium"
                  title="Download blank Excel process capture form"
                >
                  <FileSpreadsheet className="w-3 h-3" />
                  Blank Form (.xlsx)
                </a>
                <span className="text-stone-300">•</span>
                <InfoTooltip
                  title="Text Input Guidance"
                  content="Write in bullet points, numbered steps, or narrative prose. Mention departments or roles (e.g. 'Customer', 'Manager', 'ERP System') for swimlane detection."
                />
              </div>
            </div>
            <textarea
              id="process-text-input"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Paste standard operating procedure (SOP), interview transcript, bullet steps, or table here..."
              className="w-full flex-1 p-3 text-xs text-stone-800 bg-white resize-none outline-none font-mono leading-relaxed placeholder:text-stone-400"
            />
          </div>

          {/* SECTION 4: Bottom Action Bar */}
          <div className="pt-2 flex items-center justify-between border-t border-stone-200">
            <div className="text-[11px] text-stone-500">
              {inputText
                ? `${inputText.split(/\s+/).filter(Boolean).length} words • ${inputText.length} chars`
                : 'Ready for input'}
            </div>
            <div className="flex items-center gap-1.5">
              <button
                id="convert-btn"
                onClick={onConvert}
                disabled={loading || !inputText.trim()}
                className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-sm transition-all flex items-center gap-2 cursor-pointer"
              >
                {loading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Synthesizing BPMN 2.0...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 text-blue-200" />
                    <span>Generate BPMN 2.0</span>
                  </>
                )}
              </button>
              <InfoTooltip
                title="Conversion Execution"
                content="Extracts process flow, validates deterministically against BPMN 2.0 rules, computes Sugiyama planar layout, and conforms to selected template swimlanes."
              />
            </div>
          </div>
        </div>
      ) : (
        /* Traceability & Source Citation Inspection */
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Node metadata badge if selected */}
          {selectedNode ? (
            <div className="p-3 bg-blue-50/70 border-b border-blue-100 flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-blue-600 text-white rounded text-xs font-semibold">
                    {selectedNode.type}
                  </span>
                  <h4 className="text-sm font-bold text-stone-900 truncate">
                    {selectedNode.name || selectedNode.id}
                  </h4>
                </div>
                {selectedNode.confidence !== undefined && (
                  <div className="flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{Math.round(selectedNode.confidence * 100)}% Confidence</span>
                  </div>
                )}
              </div>

              {selectedNode.laneId && (
                <div className="text-xs text-stone-600">
                  <span className="font-semibold text-stone-500">Lane / Actor:</span>{' '}
                  <span className="bg-stone-200/80 px-1.5 py-0.5 rounded text-stone-800 font-mono text-[11px]">
                    {selectedNode.laneId}
                  </span>
                </div>
              )}

              {selectedNode.source_snippet && (
                <div className="mt-1 p-2 bg-white rounded border border-blue-200 text-xs text-stone-700 flex items-start gap-2 shadow-2xs">
                  <Quote className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-blue-900 block mb-0.5">
                      Source Evidence Citation:
                    </span>
                    <span className="italic">"{selectedNode.source_snippet}"</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-3 bg-stone-50 border-b border-stone-200 text-xs text-stone-500 flex items-center justify-between">
              <span>Click any node in the BPMN diagram to highlight its corresponding source line.</span>
              <span className="text-[11px] font-mono text-stone-400">Traceability Matrix</span>
            </div>
          )}

          {/* Line-by-Line Document Viewer */}
          <div className="flex-1 overflow-y-auto font-mono text-xs leading-relaxed p-2 select-text">
            {lines.map((line, idx) => {
              const isMatch =
                highlightedLineIndex === idx ||
                (snippet && line.toLowerCase().includes(snippet));
              return (
                <div
                  key={idx}
                  ref={isMatch ? highlightRef : undefined}
                  className={`flex items-start py-0.5 px-2 rounded transition-colors ${
                    isMatch
                      ? 'bg-amber-100 text-stone-900 font-medium border-l-3 border-amber-500 shadow-2xs'
                      : 'text-stone-700 hover:bg-stone-50'
                  }`}
                >
                  <span className="w-8 shrink-0 text-stone-400 select-none text-right pr-3 font-mono text-[11px]">
                    {idx + 1}
                  </span>
                  <span className="flex-1 break-words">
                    {line || <span className="opacity-0">empty</span>}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Node element pills list for quick jumping */}
          {elements.length > 0 && (
            <div className="p-2 bg-stone-50 border-t border-stone-200 max-h-36 overflow-y-auto">
              <div className="text-[11px] font-bold text-stone-500 uppercase tracking-wider mb-1 px-1">
                Extracted Process Steps ({elements.length})
              </div>
              <div className="flex flex-wrap gap-1">
                {elements.map((el) => {
                  const isSelected = selectedNode?.id === el.id;
                  return (
                    <button
                      key={el.id}
                      onClick={() => onSelectNodeById && onSelectNodeById(el.id)}
                      className={`px-2 py-1 rounded text-xs transition-all text-left flex items-center gap-1 ${
                        isSelected
                          ? 'bg-blue-600 text-white font-medium shadow-2xs'
                          : 'bg-white border border-stone-200 text-stone-700 hover:border-stone-300'
                      }`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      <span className="max-w-[130px] truncate">{el.name || el.id}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
