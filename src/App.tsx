import React, { useState, useEffect } from 'react';
import {
  ProcessIR,
  FlowNode,
  ProfileMetadata,
  SampleFile,
  ConversionResponse,
  LintResult,
  LLMSettings,
  TemplateRecord,
  BulkExportData,
} from './types';
import { BpmnViewerComponent } from './components/BpmnViewer';
import { SourceViewer } from './components/SourceViewer';
import { ProfileSelector } from './components/ProfileSelector';
import { AmbiguityDrawer } from './components/AmbiguityDrawer';
import { SettingsModal } from './components/SettingsModal';
import { TemplateManager } from './components/TemplateManager';
import { LaneMappingModal } from './components/LaneMappingModal';
import { InfoTooltip } from './components/InfoTooltip';
import {
  Layers,
  Sparkles,
  Settings as SettingsIcon,
  GitCommit,
  CheckCircle,
  HelpCircle,
  Activity,
  AlertCircle,
  GitMerge,
} from 'lucide-react';

export default function App() {
  const [inputText, setInputText] = useState<string>('');
  const [normalizedText, setNormalizedText] = useState<string>('');
  const [filename, setFilename] = useState<string>('sample_sop.md');
  const [profiles, setProfiles] = useState<ProfileMetadata[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>('signavio');
  const [samples, setSamples] = useState<SampleFile[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Template Mode States
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [laneMap, setLaneMap] = useState<Record<string, string>>({});
  const [isTemplateManagerOpen, setIsTemplateManagerOpen] = useState<boolean>(false);
  const [isLaneMappingOpen, setIsLaneMappingOpen] = useState<boolean>(false);

  const [activeTab, setActiveTab] = useState<'input' | 'traceability'>('input');
  const [bpmnXml, setBpmnXml] = useState<string>('');
  const [processIr, setProcessIr] = useState<ProcessIR | null>(null);
  const [selectedElementId, setSelectedElementId] = useState<string | undefined>(undefined);
  const [lintResult, setLintResult] = useState<LintResult | undefined>(undefined);
  const [conversionMeta, setConversionMeta] = useState<any>(null);
  const [bulkExport, setBulkExport] = useState<BulkExportData | undefined>(undefined);

  const [isAmbiguityOpen, setIsAmbiguityOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  const [settings, setSettings] = useState<LLMSettings>({
    provider: 'openai_compatible',
    model: 'llama3',
    baseUrl: 'http://localhost:11434/v1',
    apiKey: '',
    temperature: 0.1,
  });

  // Load templates list
  const fetchTemplates = () => {
    fetch('/api/templates')
      .then((res) => res.json())
      .then((data) => {
        if (data.templates) {
          setTemplates(data.templates);
        }
      })
      .catch((err) => console.error('Failed to load templates:', err));
  };

  // Load profiles, samples, and templates on initial mount
  useEffect(() => {
    fetch('/api/profiles')
      .then((res) => res.json())
      .then((data) => {
        if (data.profiles && data.profiles.length > 0) {
          setProfiles(data.profiles);
        }
      })
      .catch((err) => console.error('Failed to load profiles:', err));

    fetchTemplates();

    fetch('/api/samples')
      .then((res) => res.json())
      .then((data) => {
        if (data.samples && data.samples.length > 0) {
          setSamples(data.samples);
          // Auto-load sample SOP
          const defaultSample =
            data.samples.find((s: SampleFile) => s.name.includes('sop')) || data.samples[0];
          if (defaultSample) {
            setInputText(defaultSample.content);
            setFilename(defaultSample.name);
            // Trigger automatic initial conversion (without template for golden standard)
            convertProcess(defaultSample.content, defaultSample.name, 'signavio', '', {}, false);
          }
        }
      })
      .catch((err) => console.error('Failed to load samples:', err));
  }, []);

  const convertProcess = async (
    textToConvert: string,
    fname: string = 'process_input.txt',
    profile: string = selectedProfileId,
    templateId: string = selectedTemplateId,
    currentLaneMap: Record<string, string> = laneMap,
    forceMock: boolean = settings.provider === 'mock'
  ) => {
    if (!textToConvert.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const payload = {
        text: textToConvert,
        filename: fname,
        profile: profile,
        template_id: templateId || undefined,
        lane_map: Object.keys(currentLaneMap).length > 0 ? currentLaneMap : undefined,
        mock: forceMock || settings.provider === 'mock',
        provider: settings.provider,
        model: settings.model,
        base_url: settings.baseUrl,
        api_key: settings.apiKey,
      };

      const res = await fetch('/api/convert-json', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.error || `Conversion failed: ${res.statusText}`);
      }

      const data: ConversionResponse = await res.json();
      if (!data.success) {
        throw new Error(data.error || 'Conversion failed');
      }

      setBpmnXml(data.bpmn_xml);
      setProcessIr(data.ir);
      setNormalizedText(data.normalized_text);
      setLintResult(data.lint_result);
      setConversionMeta(data.metadata);
      setBulkExport(data.bulk_export);

      // If backend returned template info with auto lane map, save it
      if (data.template_info?.lane_map) {
        setLaneMap((prev) => ({
          ...prev,
          ...data.template_info?.lane_map,
        }));
      }

      // Default select first element if available
      if (data.ir.elements && data.ir.elements.length > 0) {
        setSelectedElementId(data.ir.elements[0].id);
      }
    } catch (err: any) {
      console.error('Conversion error:', err);
      setError(err.message || 'An error occurred during process conversion.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSample = (sample: SampleFile) => {
    setInputText(sample.content);
    setFilename(sample.name);
    convertProcess(sample.content, sample.name, selectedProfileId, selectedTemplateId, laneMap);
  };

  const handleFileUpload = async (file: File) => {
    setFilename(file.name);
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (selectedProfileId) formData.append('profile', selectedProfileId);
      if (selectedTemplateId) formData.append('template_id', selectedTemplateId);
      if (laneMap && Object.keys(laneMap).length > 0) {
        formData.append('lane_map', JSON.stringify(laneMap));
      }
      formData.append('mock', String(settings.provider === 'mock'));
      if (settings.provider) formData.append('provider', settings.provider);
      if (settings.model) formData.append('model', settings.model);
      if (settings.baseUrl) formData.append('base_url', settings.baseUrl);
      if (settings.apiKey) formData.append('api_key', settings.apiKey);

      const res = await fetch('/api/convert', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.error || `Conversion failed: ${res.statusText}`);
      }

      const data: ConversionResponse = await res.json();
      if (!data.success) {
        throw new Error(data.error || 'Conversion failed');
      }

      setBpmnXml(data.bpmn_xml);
      setProcessIr(data.ir);
      setNormalizedText(data.normalized_text);
      if (data.normalized_text) {
        setInputText(data.normalized_text);
      }
      setLintResult(data.lint_result);
      setConversionMeta(data.metadata);
      setBulkExport(data.bulk_export);

      if (data.template_info?.lane_map) {
        setLaneMap((prev) => ({
          ...prev,
          ...data.template_info?.lane_map,
        }));
      }

      if (data.ir.elements && data.ir.elements.length > 0) {
        setSelectedElementId(data.ir.elements[0].id);
      }
    } catch (err: any) {
      console.error('File upload conversion error:', err);
      setError(err.message || 'An error occurred during file upload and conversion.');
    } finally {
      setLoading(false);
    }
  };

  const handleProfileChange = async (newProfileId: string) => {
    setSelectedProfileId(newProfileId);
    if (processIr) {
      try {
        const res = await fetch('/api/lint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ir: processIr, profile: newProfileId }),
        });
        if (res.ok) {
          const lintData = await res.json();
          setLintResult(lintData);
        }
      } catch (e) {
        console.error('Failed to lint:', e);
      }
      convertProcess(inputText, filename, newProfileId, selectedTemplateId, laneMap);
    }
  };

  const handleTemplateChange = (newTemplateId: string) => {
    setSelectedTemplateId(newTemplateId);
    // If user changed template, trigger re-conversion with new template bindings
    convertProcess(inputText, filename, selectedProfileId, newTemplateId, laneMap);
  };

  const handleApplyLaneMapping = (newLaneMap: Record<string, string>) => {
    setLaneMap(newLaneMap);
    // Re-run conversion with updated lane mappings
    convertProcess(inputText, filename, selectedProfileId, selectedTemplateId, newLaneMap);
  };

  const handleElementSelectedInDiagram = (elementId: string) => {
    setSelectedElementId(elementId);
    setActiveTab('traceability');
  };

  const selectedNode: FlowNode | undefined = processIr?.elements?.find(
    (el) => el.id === selectedElementId
  );

  const activeTemplate = templates.find((t) => t.id === selectedTemplateId);

  // Safely derive unique actors from IR elements and pools without unsafe spreads
  const detectedActors: string[] = React.useMemo(() => {
    const actorSet = new Set<string>();
    if (processIr?.pools && Array.isArray(processIr.pools)) {
      for (const pool of processIr.pools) {
        if (pool && Array.isArray(pool.lanes)) {
          for (const lane of pool.lanes) {
            if (lane?.name) actorSet.add(lane.name);
          }
        }
      }
    }
    if (processIr?.elements && Array.isArray(processIr.elements)) {
      for (const el of processIr.elements) {
        if (el?.laneId) actorSet.add(el.laneId);
      }
    }
    if (laneMap && typeof laneMap === 'object') {
      for (const key of Object.keys(laneMap)) {
        if (key) actorSet.add(key);
      }
    }
    return Array.from(actorSet).filter(Boolean);
  }, [processIr, laneMap]);

  return (
    <div className="flex flex-col h-screen w-screen bg-stone-100 text-stone-900 overflow-hidden font-sans antialiased">
      {/* Top Application Bar */}
      <header className="h-14 bg-white border-b border-stone-200 px-4 flex items-center justify-between shrink-0 shadow-2xs z-20">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-2xs">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-sm tracking-tight text-stone-900">Text2BPMN</h1>
                <span className="px-1.5 py-0.2 bg-stone-100 text-stone-600 rounded text-[10px] font-mono font-medium border border-stone-200">
                  BPMN 2.0
                </span>
                <InfoTooltip
                  title="Text2BPMN Pipeline"
                  content="Converts unstructured or structured business process descriptions into compliant, standards-based BPMN 2.0 XML with deterministic Sugiyama layout."
                />
              </div>
              <p className="text-[11px] text-stone-500 leading-none">
                Vendor-Agnostic Process Description to BPMNDI 2.0 Pipeline
              </p>
            </div>
          </div>
        </div>

        {/* Center: Metadata / Metrics stats if available */}
        {conversionMeta && (
          <div className="hidden lg:flex items-center gap-4 text-xs text-stone-600 bg-stone-50 px-3 py-1 rounded-lg border border-stone-200/80">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-stone-800">{conversionMeta.element_count}</span>
              <span className="text-stone-400">elements</span>
            </div>
            <span className="text-stone-300">•</span>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-stone-800">{conversionMeta.flow_count}</span>
              <span className="text-stone-400">flows</span>
            </div>
            <span className="text-stone-300">•</span>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-stone-800">
                {conversionMeta.lane_count || 1}
              </span>
              <span className="text-stone-400">swimlanes</span>
            </div>

            {activeTemplate && (
              <>
                <span className="text-stone-300">•</span>
                <div className="flex items-center gap-1 text-purple-700 font-medium">
                  <Layers className="w-3 h-3" />
                  <span>{activeTemplate.name}</span>
                  <InfoTooltip
                    title="Active Reference Template"
                    content={`Diagram adheres to ${activeTemplate.name} (${activeTemplate.source_vendor.toUpperCase()}) definitions and swimlane bounds.`}
                  />
                </div>
              </>
            )}

            <span className="text-stone-300">•</span>
            <div className="flex items-center gap-1 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span className="text-stone-500">
                {conversionMeta.extraction?.mode || 'extracted'}
              </span>
            </div>
          </div>
        )}

        {/* Right: Controls & Actions */}
        <div className="flex items-center gap-2">
          <ProfileSelector
            profiles={profiles}
            selectedProfileId={selectedProfileId}
            onSelectProfile={handleProfileChange}
            lintResult={lintResult}
          />

          <AmbiguityDrawer
            openQuestions={processIr?.open_questions || []}
            assumptions={lintResult?.assumptions || processIr?.assumptions || []}
            validationIssues={[]}
            isOpen={isAmbiguityOpen}
            onToggle={() => setIsAmbiguityOpen(!isAmbiguityOpen)}
          />

          <div className="flex items-center gap-1">
            <button
              id="open-settings-btn"
              onClick={() => setIsSettingsOpen(true)}
              title="Configure LLM Provider & Settings"
              className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg border border-stone-200 transition-colors cursor-pointer"
            >
              <SettingsIcon className="w-4 h-4" />
            </button>
            <InfoTooltip
              title="LLM Settings"
              content="Configure connection details for local (Ollama/LM Studio), OpenAI-compatible, Anthropic, or Gemini providers."
            />
          </div>
        </div>
      </header>

      {/* Error notification banner if any */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-xs text-red-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="font-bold text-red-500 hover:text-red-800"
          >
            &times;
          </button>
        </div>
      )}

      {/* Main Dual-Pane Layout */}
      <main className="flex-1 flex overflow-hidden p-3 gap-3">
        {/* Left Pane: Source Document Input & Traceability (42% width) */}
        <div className="w-[42%] min-w-[390px] max-w-[590px] h-full flex flex-col">
          <SourceViewer
            inputText={inputText}
            setInputText={setInputText}
            samples={samples}
            onSelectSample={handleSelectSample}
            onFileUpload={handleFileUpload}
            onConvert={() =>
              convertProcess(inputText, filename, selectedProfileId, selectedTemplateId, laneMap)
            }
            loading={loading}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            normalizedText={normalizedText}
            selectedNode={selectedNode}
            elements={processIr?.elements || []}
            onSelectNodeById={(id) => setSelectedElementId(id)}
            // Template integration
            templates={templates}
            selectedTemplateId={selectedTemplateId}
            onSelectTemplate={handleTemplateChange}
            onOpenTemplateManager={() => setIsTemplateManagerOpen(true)}
            onOpenLaneMapping={() => setIsLaneMappingOpen(true)}
            hasActors={detectedActors.length > 0}
          />
        </div>

        {/* Right Pane: Interactive BPMN 2.0 Canvas (58% width) */}
        <div className="flex-1 h-full flex flex-col min-w-0">
          <BpmnViewerComponent
            xml={bpmnXml}
            selectedElementId={selectedElementId}
            onSelectElement={handleElementSelectedInDiagram}
            processName={processIr?.name || filename || 'Process'}
            bulkExport={bulkExport}
          />
        </div>
      </main>

      {/* LLM Provider Configuration Modal */}
      <SettingsModal
        settings={settings}
        onSave={(newSet) => setSettings(newSet)}
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      {/* BPMN Reference Template Manager Modal */}
      <TemplateManager
        isOpen={isTemplateManagerOpen}
        onClose={() => {
          setIsTemplateManagerOpen(false);
          fetchTemplates();
        }}
        onSelectTemplate={(tplId) => handleTemplateChange(tplId)}
        selectedTemplateId={selectedTemplateId}
      />

      {/* Swimlane Role Mapping Modal */}
      {activeTemplate && (
        <LaneMappingModal
          isOpen={isLaneMappingOpen}
          onClose={() => setIsLaneMappingOpen(false)}
          templateId={activeTemplate.id}
          templateName={activeTemplate.name}
          actors={detectedActors}
          currentMapping={laneMap}
          onApplyMapping={handleApplyLaneMapping}
        />
      )}
    </div>
  );
}
