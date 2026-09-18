import React, { useState, useEffect, useRef } from 'react';
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
  ValidationIssue,
} from './types';
import { BpmnViewerComponent, BpmnViewerHandle } from './components/BpmnViewer';
import { Toolbar } from './components/layout/Toolbar';
import { Sidebar } from './components/layout/Sidebar';
import { Inspector } from './components/layout/Inspector';
import { FloatingControls } from './components/layout/FloatingControls';
import { EmptyState } from './components/layout/EmptyState';
import { SettingsSheet } from './components/sheets/SettingsSheet';
import { TemplateManagerSheet } from './components/sheets/TemplateManagerSheet';
import { LaneMappingSheet } from './components/sheets/LaneMappingSheet';
import { Toast, ToastMessage } from './components/ui/Toast';

export default function App() {
  const viewerRef = useRef<BpmnViewerHandle>(null);

  // Core Process Inputs
  const [inputText, setInputText] = useState<string>('');
  const [normalizedText, setNormalizedText] = useState<string>('');
  const [filename, setFilename] = useState<string>('sample_sop.md');
  const [fileSize, setFileSize] = useState<number | undefined>(undefined);
  const [profiles, setProfiles] = useState<ProfileMetadata[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>('signavio');
  const [samples, setSamples] = useState<SampleFile[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [sidebarError, setSidebarError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Template Mode States
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [laneMap, setLaneMap] = useState<Record<string, string>>({});
  const [isTemplateManagerOpen, setIsTemplateManagerOpen] = useState<boolean>(false);
  const [isLaneMappingOpen, setIsLaneMappingOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  // Layout View States
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [isInspectorOpen, setIsInspectorOpen] = useState<boolean>(false);
  const [inspectorTab, setInspectorTab] = useState<'details' | 'source' | 'issues'>('details');

  // Responsive Breakpoints: inspector bottom sheet < 1100px, sidebar sheet < 800px
  const [windowWidth, setWindowWidth] = useState<number>(() =>
    typeof window !== 'undefined' ? window.innerWidth : 1200
  );

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const isBelow1100 = windowWidth < 1100;
  const isBelow800 = windowWidth < 800;

  // Process Output States
  const [bpmnXml, setBpmnXml] = useState<string>('');
  const [processIr, setProcessIr] = useState<ProcessIR | null>(null);
  const [exportBlocked, setExportBlocked] = useState<boolean>(false);
  const [selectedElementId, setSelectedElementId] = useState<string | undefined>(undefined);
  const [lintResult, setLintResult] = useState<LintResult | undefined>(undefined);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [conversionMeta, setConversionMeta] = useState<any>(null);
  const [bulkExport, setBulkExport] = useState<BulkExportData | undefined>(undefined);

  // LLM Engine Settings
  const [settings, setSettings] = useState<LLMSettings>({
    provider: 'openai_compatible',
    model: 'llama3',
    baseUrl: 'http://localhost:11434/v1',
    apiKey: '',
    temperature: 0.1,
  });

  // Fetch templates list
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

  // Initial mount: load profiles, templates, samples
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
          const defaultSample =
            data.samples.find((s: SampleFile) => s.name.includes('sop')) || data.samples[0];
          if (defaultSample) {
            setInputText(defaultSample.content);
            setFilename(defaultSample.name);
            setFileSize(new Blob([defaultSample.content]).size);
            // Auto-load default diagram
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
    setSidebarError(null);

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
        const errMsg = errData.detail || errData.error || `Conversion failed (${res.status})`;
        const kind = errData.kind || (res.status === 502 ? 'LLMError' : res.status === 401 ? 'LLMAuthenticationError' : 'Error');
        const prov = errData.provider || settings.provider || 'Provider';
        const mdl = errData.model || settings.model || 'Model';

        if (res.status === 502 || res.status === 401 || res.status === 400 || errMsg.toLowerCase().includes('llm')) {
          setToast({
            id: String(Date.now()),
            type: 'error',
            title: `[${kind}] ${prov} / ${mdl}`,
            message: errMsg,
            action: {
              label: 'Open Settings',
              onClick: () => setIsSettingsOpen(true),
            },
          });
        }
        throw new Error(errMsg);
      }

      const data: ConversionResponse = await res.json();
      if (!data.success) {
        throw new Error(data.error || 'Conversion failed');
      }

      setBpmnXml(data.bpmn_xml);
      setProcessIr(data.ir);
      setExportBlocked(Boolean(data.export_blocked));
      setNormalizedText(data.normalized_text);
      setLintResult(data.lint_result);
      setValidationIssues(data.validation_issues || []);
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
      console.error('Conversion error:', err);
      setSidebarError(err.message || 'An error occurred during process conversion.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSample = (sample: SampleFile) => {
    setInputText(sample.content);
    setFilename(sample.name);
    setFileSize(new Blob([sample.content]).size);
    convertProcess(sample.content, sample.name, selectedProfileId, selectedTemplateId, laneMap);
  };

  const handleFileUpload = async (file: File) => {
    setFilename(file.name);
    setFileSize(file.size);
    setLoading(true);
    setSidebarError(null);

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
        const errMsg = errData.detail || errData.error || `Upload failed (${res.status})`;
        const kind = errData.kind || (res.status === 502 ? 'LLMError' : res.status === 401 ? 'LLMAuthenticationError' : 'Error');
        const prov = errData.provider || settings.provider || 'Provider';
        const mdl = errData.model || settings.model || 'Model';

        if (res.status === 502 || res.status === 401 || res.status === 400 || errMsg.toLowerCase().includes('llm')) {
          setToast({
            id: String(Date.now()),
            type: 'error',
            title: `[${kind}] ${prov} / ${mdl}`,
            message: errMsg,
            action: {
              label: 'Open Settings',
              onClick: () => setIsSettingsOpen(true),
            },
          });
        }
        throw new Error(errMsg);
      }

      const data: ConversionResponse = await res.json();
      if (!data.success) {
        throw new Error(data.error || 'Conversion failed');
      }

      setBpmnXml(data.bpmn_xml);
      setProcessIr(data.ir);
      setExportBlocked(Boolean(data.export_blocked));
      setNormalizedText(data.normalized_text);
      if (data.normalized_text) {
        setInputText(data.normalized_text);
      }
      setLintResult(data.lint_result);
      setValidationIssues(data.validation_issues || []);
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
      console.error('File upload error:', err);
      setSidebarError(err.message || 'Failed to parse and convert file.');
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
    convertProcess(inputText, filename, selectedProfileId, newTemplateId, laneMap);
  };

  const handleApplyLaneMapping = (newLaneMap: Record<string, string>) => {
    setLaneMap(newLaneMap);
    convertProcess(inputText, filename, selectedProfileId, selectedTemplateId, newLaneMap);
  };

  const handleElementSelectedInDiagram = (elementId: string) => {
    setSelectedElementId(elementId);
    setIsInspectorOpen(true);
    setInspectorTab('details');
  };

  const selectedNode: FlowNode | undefined = processIr?.elements?.find(
    (el) => el.id === selectedElementId
  );

  const activeTemplate = templates.find((t) => t.id === selectedTemplateId);

  // Derive detected actors for lane mapping
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

  const totalIssuesCount =
    validationIssues.length +
    (lintResult?.warnings?.length || 0) +
    (processIr?.open_questions?.length || 0);

  return (
    <div className="flex flex-col h-screen w-screen bg-[var(--bg)] text-[var(--text)] overflow-hidden font-sans select-none">
      {/* 1. Translucent Top Toolbar (52px) */}
      <Toolbar
        appName="process2bpmn"
        profiles={profiles}
        selectedProfileId={selectedProfileId}
        onSelectProfile={handleProfileChange}
        templates={templates}
        selectedTemplateId={selectedTemplateId}
        onSelectTemplate={handleTemplateChange}
        onOpenTemplateManager={() => setIsTemplateManagerOpen(true)}
        onOpenLaneMapping={() => setIsLaneMappingOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        hasDiagram={Boolean(bpmnXml)}
        exportBlocked={exportBlocked}
        onExportBpmn={() => viewerRef.current?.exportBpmn()}
        onExportSvg={() => viewerRef.current?.exportSvg()}
        onExportPng={() => viewerRef.current?.exportPng()}
        onExportZip={() => viewerRef.current?.exportZip()}
      />

      {/* 2. Main Stage: Left Sidebar + Full Canvas + Right Inspector */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Sidebar (320px -> 44px on desktop, left sheet on <800px) */}
        <Sidebar
          isOpen={isSidebarOpen}
          onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
          inputText={inputText}
          onInputChange={setInputText}
          fileName={filename}
          fileSize={fileSize}
          onFileUpload={handleFileUpload}
          samples={samples}
          onSelectSample={handleSelectSample}
          onConvert={() =>
            convertProcess(inputText, filename, selectedProfileId, selectedTemplateId, laneMap)
          }
          isLoading={loading}
          error={sidebarError}
          isSheet={isBelow800}
        />

        {/* Center: BPMN Canvas (Fills Remaining Space with 16px Inset, No Card Border) */}
        <main className="flex-1 h-full relative overflow-hidden flex flex-col p-4">
          <div className="relative w-full h-full rounded-[16px] overflow-hidden bg-[var(--surface-solid)]">
            {bpmnXml ? (
              <>
                <BpmnViewerComponent
                  ref={viewerRef}
                  xml={bpmnXml}
                  selectedElementId={selectedElementId}
                  onSelectElement={handleElementSelectedInDiagram}
                  processName={processIr?.name || filename || 'process'}
                  bulkExport={bulkExport}
                  isLoading={loading}
                />

                {/* Floating Controls */}
                <FloatingControls
                  elementCount={conversionMeta?.element_count || processIr?.elements?.length || 0}
                  flowCount={conversionMeta?.flow_count || processIr?.flows?.length || 0}
                  laneCount={conversionMeta?.lane_count || processIr?.pools?.reduce((acc, p) => acc + p.lanes.length, 0) || 1}
                  extractionMode={conversionMeta?.extraction?.mode}
                  issuesCount={totalIssuesCount}
                  onOpenIssues={() => {
                    setIsInspectorOpen(true);
                    setInspectorTab('issues');
                  }}
                  onZoomIn={() => viewerRef.current?.zoomIn()}
                  onZoomOut={() => viewerRef.current?.zoomOut()}
                  onFitViewport={() => viewerRef.current?.fitViewport()}
                  onResetZoom={() => viewerRef.current?.resetZoom()}
                />
              </>
            ) : (
              <EmptyState
                onFileUpload={handleFileUpload}
                samples={samples}
                onSelectSample={handleSelectSample}
              />
            )}
          </div>
        </main>

        {/* Right Inspector (360px on desktop, bottom sheet on <1100px) */}
        <Inspector
          isOpen={isInspectorOpen}
          onClose={() => setIsInspectorOpen(false)}
          activeTab={inspectorTab}
          onTabChange={setInspectorTab}
          selectedElement={selectedNode}
          processIr={processIr}
          validationIssues={validationIssues}
          lintResult={lintResult}
          exportBlocked={exportBlocked}
          sourceText={normalizedText || inputText}
          isBottomSheet={isBelow1100}
          onSelectElementById={(id) => {
            setSelectedElementId(id);
            setInspectorTab('details');
          }}
        />
      </div>

      {/* 3. Slide-over Sheets */}
      <SettingsSheet
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onSave={setSettings}
      />

      <TemplateManagerSheet
        isOpen={isTemplateManagerOpen}
        onClose={() => {
          setIsTemplateManagerOpen(false);
          fetchTemplates();
        }}
        onSelectTemplate={handleTemplateChange}
        selectedTemplateId={selectedTemplateId}
      />

      {activeTemplate && (
        <LaneMappingSheet
          isOpen={isLaneMappingOpen}
          onClose={() => setIsLaneMappingOpen(false)}
          templateId={activeTemplate.id}
          templateName={activeTemplate.name}
          actors={detectedActors}
          currentMapping={laneMap}
          onApplyMapping={handleApplyLaneMapping}
        />
      )}

      {/* 4. Global Toast for Transient Errors */}
      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
