import React, { useState, useEffect, useRef } from 'react';
import {
  ProcessIR,
  FlowNode,
  ProfileMetadata,
  ConversionResponse,
  ImportInfo,
  LintResult,
  LLMSettings,
  TemplateRecord,
  BulkExportData,
  ValidationIssue,
  ServerConfig,
  UiError,
} from './types';
import { describeApiError, describeUnexpectedError } from './lib/errors';
import { isBpmnFile } from './lib/files';
import { BpmnViewerComponent, BpmnViewerHandle } from './components/BpmnViewer';
import { Toolbar } from './components/layout/Toolbar';
import { Sidebar } from './components/layout/Sidebar';
import { Inspector } from './components/layout/Inspector';
import { FloatingControls } from './components/layout/FloatingControls';
import { EmptyState } from './components/layout/EmptyState';
import { SettingsSheet } from './components/sheets/SettingsSheet';
import { TemplateManagerSheet } from './components/sheets/TemplateManagerSheet';
import { TemplateSheet } from './components/sheets/TemplateSheet';
import { LaneMappingSheet } from './components/sheets/LaneMappingSheet';
import { Toast, ToastMessage } from './components/ui/Toast';
import { RowValidationErrorItem } from './types';

/** Thrown after an API failure has already been shown to the user, so catch blocks don't show it twice. */
class HandledApiError extends Error {
  readonly ui: UiError;
  constructor(ui: UiError) {
    super(ui.message);
    this.ui = ui;
  }
}

const SETTINGS_STORAGE_KEY = 'process2bpmn.settings.v1';

/** Scope v2 default export target. The backend defaults to the same profile. */
const DEFAULT_PROFILE_ID = 'celonis';



function loadStoredSettings(): LLMSettings {
  const fallback: LLMSettings = { provider: '', model: '', baseUrl: '', apiKey: '', temperature: 0.1 };
  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return { ...fallback, ...parsed, apiKey: '' }; // the key is never persisted
  } catch {
    return fallback;
  }
}

export default function App() {
  const viewerRef = useRef<BpmnViewerHandle>(null);

  // Core Process Inputs
  const [inputText, setInputText] = useState<string>('');
  const [normalizedText, setNormalizedText] = useState<string>('');
  const [filename, setFilename] = useState<string>('process_input.txt');
  const [fileSize, setFileSize] = useState<number | undefined>(undefined);
  const [profiles, setProfiles] = useState<ProfileMetadata[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>(DEFAULT_PROFILE_ID);
  const [loading, setLoading] = useState<boolean>(false);
  const [sidebarError, setSidebarError] = useState<UiError | null>(null);
  const [serverConfig, setServerConfig] = useState<ServerConfig | null>(null);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Template Mode States
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [laneMap, setLaneMap] = useState<Record<string, string>>({});
  const [isTemplateManagerOpen, setIsTemplateManagerOpen] = useState<boolean>(false);
  const [isTemplateSheetOpen, setIsTemplateSheetOpen] = useState<boolean>(false);
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
  const [rowErrors, setRowErrors] = useState<RowValidationErrorItem[]>([]);
  const [conversionMeta, setConversionMeta] = useState<any>(null);
  const [bulkExport, setBulkExport] = useState<BulkExportData | undefined>(undefined);
  const [importInfo, setImportInfo] = useState<ImportInfo | undefined>(undefined);

  // LLM Engine Settings
  // Empty values mean "use the server's .env configuration". Only what the user
  // explicitly enters in Settings is sent with a request, so .env stays the source of truth.
  // Provider/model/base URL overrides survive a reload; the API key never does.
  const [settings, setSettings] = useState<LLMSettings>(loadStoredSettings);

  useEffect(() => {
    try {
      window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({ ...settings, apiKey: '' }));
    } catch {
      /* private mode or storage disabled: overrides simply don't persist */
    }
  }, [settings]);

  const fetchServerConfig = () => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data: ServerConfig) => setServerConfig(data))
      .catch((err) => console.error('Failed to load server config:', err));
  };

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

  // Initial mount: load config, profiles and templates. Nothing is preloaded onto the canvas.
  useEffect(() => {
    fetchServerConfig();

    fetch('/api/profiles')
      .then((res) => res.json())
      .then((data) => {
        if (data.profiles && data.profiles.length > 0) {
          setProfiles(data.profiles);
          // Fall back to the first target the server offers if the default is not among them.
          if (!data.profiles.some((p: ProfileMetadata) => p.id === DEFAULT_PROFILE_ID)) {
            setSelectedProfileId(data.profiles[0].id);
          }
        }
      })
      .catch((err) => console.error('Failed to load profiles:', err));

    fetchTemplates();
  }, []);

  /** Surfaces an API failure (sidebar card, toast, row errors) and throws a HandledApiError. */
  const handleFailedResponse = async (res: Response): Promise<never> => {
    const body = await res.json().catch(() => ({}));
    const ui = describeApiError(res.status, body);
    if (Array.isArray(body?.row_errors) && body.row_errors.length > 0) {
      setRowErrors(body.row_errors as RowValidationErrorItem[]);
      setIsInspectorOpen(true);
      setInspectorTab('issues');
    }
    setSidebarError(ui);
    setToast({
      id: String(Date.now()),
      type: 'error',
      title: ui.title,
      message: ui.message,
      action: ui.canOpenSettings ? { label: 'Open Settings', onClick: () => setIsSettingsOpen(true) } : undefined,
    });
    throw new HandledApiError(ui);
  };

  const applyConversionResult = (data: ConversionResponse) => {
    setBpmnXml(data.bpmn_xml);
    setProcessIr(data.ir);
    setExportBlocked(Boolean(data.export_blocked));
    setRowErrors([]);
    if (data.normalized_text) {
      setNormalizedText(data.normalized_text);
    }
    setLintResult(data.lint_result);
    setValidationIssues(data.validation_issues || []);
    setConversionMeta(data.metadata);
    setBulkExport(data.bulk_export);
    setImportInfo(data.import_info);
    if (data.template_info?.lane_map) {
      setLaneMap((prev) => ({ ...prev, ...data.template_info?.lane_map }));
    }
    if (data.ir.elements && data.ir.elements.length > 0) {
      setSelectedElementId(data.ir.elements[0].id);
    }
  };

  const showUnexpectedError = (err: unknown) => {
    if (err instanceof HandledApiError) return; // already shown
    console.error(err);
    setSidebarError(describeUnexpectedError(err));
  };

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
        provider: settings.provider || undefined,
        model: settings.model || undefined,
        base_url: settings.provider === 'openai_compatible' && settings.baseUrl ? settings.baseUrl : undefined,
        api_key: settings.apiKey || undefined,
      };

      const res = await fetch('/api/convert-json', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        await handleFailedResponse(res);
      }

      const data: ConversionResponse = await res.json();
      if (!data.success) {
        throw new Error(data.error || 'Conversion failed');
      }
      applyConversionResult(data);
    } catch (err) {
      showUnexpectedError(err);
    } finally {
      setLoading(false);
    }
  };

  /** Converts an uploaded file. Resolves to true on success so callers (Step Builder) can decide whether to close. */
  /**
   * Imports a BPMN file exported from another tool. Deterministic — no model call — and the
   * diagram keeps the coordinates the source file carried.
   */
  const importBpmnFile = async (file: File): Promise<boolean> => {
    setLoading(true);
    setSidebarError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (selectedProfileId) formData.append('profile', selectedProfileId);
      if (selectedTemplateId) formData.append('template_id', selectedTemplateId);

      const res = await fetch('/api/import/bpmn', { method: 'POST', body: formData });
      if (!res.ok) {
        await handleFailedResponse(res);
      }
      const data: ConversionResponse = await res.json();
      if (!data.success) {
        throw new Error(data.error || 'Import failed');
      }
      applyConversionResult(data);
      setInputText('');
      setNormalizedText('');

      const info = data.import_info;
      if (info) {
        const strippedCount = info.stripped_namespaces.length + info.stripped_extensions.length;
        const vendorLabel = info.source_vendor === 'generic' ? 'BPMN 2.0' : info.source_vendor;
        setToast({
          id: String(Date.now()),
          type: 'success',
          title: `Imported from ${vendorLabel}`,
          message:
            `${info.element_count} elements, ${info.flow_count} flows` +
            (strippedCount > 0 ? ` · ${strippedCount} vendor extension(s) stripped` : '') +
            (info.original_layout ? ' · original layout kept' : ' · auto-layout applied'),
        });
      }
      return true;
    } catch (err) {
      showUnexpectedError(err);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file: File): Promise<boolean> => {
    setFilename(file.name);
    setFileSize(file.size);

    if (isBpmnFile(file.name)) {
      return importBpmnFile(file);
    }

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
      if (settings.provider === 'openai_compatible' && settings.baseUrl) formData.append('base_url', settings.baseUrl);
      if (settings.apiKey) formData.append('api_key', settings.apiKey);

      const res = await fetch('/api/convert', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        await handleFailedResponse(res);
      }

      const data: ConversionResponse = await res.json();
      if (!data.success) {
        throw new Error(data.error || 'Conversion failed');
      }
      applyConversionResult(data);
      if (data.normalized_text) {
        setInputText(data.normalized_text);
      }
      return true;
    } catch (err) {
      showUnexpectedError(err);
      return false;
    } finally {
      setLoading(false);
    }
  };

  /**
   * Re-renders the current diagram for another target tool, template or lane mapping
   * from the IR we already have. No model call, so it is instant and free.
   */
  // Only the latest re-render may update the screen: switching profiles quickly fires
  // several /api/render calls and the responses can arrive out of order.
  const renderAbortRef = useRef<AbortController | null>(null);

  const rerenderFromIr = async (
    profile: string,
    templateId: string,
    currentLaneMap: Record<string, string>
  ) => {
    if (!processIr) return;
    renderAbortRef.current?.abort();
    const controller = new AbortController();
    renderAbortRef.current = controller;
    setLoading(true);
    setSidebarError(null);
    try {
      const res = await fetch('/api/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          ir: processIr,
          profile,
          template_id: templateId || undefined,
          lane_map: Object.keys(currentLaneMap).length > 0 ? currentLaneMap : undefined,
          filename,
        }),
      });
      if (controller.signal.aborted) return;
      if (!res.ok) {
        await handleFailedResponse(res);
      }
      const data: ConversionResponse = await res.json();
      if (controller.signal.aborted) return;
      applyConversionResult(data);
    } catch (err) {
      if ((err as { name?: string })?.name === 'AbortError') return;
      showUnexpectedError(err);
    } finally {
      if (renderAbortRef.current === controller) setLoading(false);
    }
  };

  /** Discards imported coordinates: /api/render always lays the diagram out from scratch. */
  const handleRelayout = () => {
    setImportInfo((prev) => (prev ? { ...prev, original_layout: false } : prev));
    rerenderFromIr(selectedProfileId, selectedTemplateId, laneMap);
  };

  const handleProfileChange = (newProfileId: string) => {
    setSelectedProfileId(newProfileId);
    rerenderFromIr(newProfileId, selectedTemplateId, laneMap);
  };

  const handleTemplateChange = (newTemplateId: string) => {
    setSelectedTemplateId(newTemplateId);
    rerenderFromIr(selectedProfileId, newTemplateId, laneMap);
  };

  const handleApplyLaneMapping = (newLaneMap: Record<string, string>) => {
    setLaneMap(newLaneMap);
    rerenderFromIr(selectedProfileId, selectedTemplateId, newLaneMap);
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

  // The badge counts things a person should look at: errors, warnings, lint findings,
  // template row errors and open questions. INFO entries are auto-repairs and stay in
  // the Issues tab under their own heading.
  const totalIssuesCount =
    validationIssues.filter((i) => i.severity !== 'INFO').length +
    rowErrors.length +
    (lintResult?.warnings?.length || 0) +
    (processIr?.openQuestions?.length || 0);

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
        onOpenTemplate={() => setIsTemplateSheetOpen(true)}
        onOpenLaneMapping={() => setIsLaneMappingOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        activeModelLabel={
          settings.provider
            ? `${settings.provider === 'mock' ? 'Rule engine' : settings.provider}${settings.model ? ' · ' + settings.model : ''}`
            : serverConfig
            ? `${serverConfig.active_provider} · ${serverConfig.active_model}`
            : 'Model: loading…'
        }
        activeModelState={
          settings.provider === 'mock'
            ? 'mock'
            : settings.provider || (serverConfig && serverConfig.api_key_set) || (serverConfig && serverConfig.active_provider === 'ollama')
            ? 'ready'
            : serverConfig
            ? 'missing-key'
            : 'unknown'
        }
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
          onConvert={() =>
            convertProcess(inputText, filename, selectedProfileId, selectedTemplateId, laneMap)
          }
          isLoading={loading}
          error={sidebarError}
          onOpenSettings={() => setIsSettingsOpen(true)}
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
                  processIr={processIr}
                  templateId={selectedTemplateId}
                  laneMap={laneMap}
                  isLoading={loading}
                  onExportError={(title, message) =>
                    setToast({ id: String(Date.now()), type: 'error', title, message })
                  }
                  onExportSuccess={(message) =>
                    setToast({ id: String(Date.now()), type: 'success', title: 'Export ready', message })
                  }
                />

                {/* Floating Controls */}
                <FloatingControls
                  elementCount={conversionMeta?.element_count || processIr?.elements?.length || 0}
                  flowCount={conversionMeta?.flow_count || processIr?.flows?.length || 0}
                  laneCount={conversionMeta?.lane_count || processIr?.pools?.reduce((acc, p) => acc + p.lanes.length, 0) || 1}
                  extractionMode={conversionMeta?.extraction?.mode}
                  issuesCount={totalIssuesCount}
                  canRelayout={Boolean(importInfo?.original_layout)}
                  onRelayout={handleRelayout}
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
                onOpenTemplate={() => setIsTemplateSheetOpen(true)}
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
          rowErrors={rowErrors}
          importInfo={importInfo}
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
      <TemplateSheet
        isOpen={isTemplateSheetOpen}
        onClose={() => setIsTemplateSheetOpen(false)}
        onOpenTemplateManager={() => setIsTemplateManagerOpen(true)}
      />

      <SettingsSheet
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        serverConfig={serverConfig}
        onSave={(next) => {
          setSettings(next);
          setSidebarError(null);
        }}
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
