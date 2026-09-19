export interface FlowNode {
  id: string;
  type: string;
  name: string;
  laneId?: string;
  sourceRef?: string;
  targetRef?: string;
  conditionExpression?: string;
  documentation?: string;
  source_snippet?: string;
  confidence?: number;
}

export interface SequenceFlow {
  id: string;
  name?: string;
  sourceId: string;
  targetId: string;
  condition?: string;
  isDefault?: boolean;
}

export interface Lane {
  id: string;
  name: string;
  elementIds: string[];
}

export interface Pool {
  id: string;
  name: string;
  lanes: Lane[];
}

export interface OpenQuestion {
  topic: string;
  question: string;
  suggestedAssumption?: string;
}

export interface ProcessIR {
  id: string;
  name: string;
  elements: FlowNode[];
  flows: SequenceFlow[];
  pools: Pool[];
  /** Ambiguities the extractor or validator could not resolve (server key: openQuestions). */
  openQuestions?: OpenQuestion[];
  assumptions?: string[];
  templateBindings?: {
    templateId: string;
    laneMap: Record<string, string>;
  };
}

export interface ValidationIssue {
  severity: 'ERROR' | 'WARNING' | 'INFO';
  message: string;
  element_id?: string;
  auto_fixed?: boolean;
  details?: Record<string, any>;
}

export interface ProfileWarning {
  code: string;
  message: string;
  severity: 'WARNING' | 'INFO';
  element_id?: string;
}

export interface LintResult {
  profile_name: string;
  display_name: string;
  is_valid: boolean;
  assumptions: string[];
  warnings: ProfileWarning[];
}

export interface ProfileMetadata {
  id: string;
  name: string;
  displayName: string;
  /** Short label for the toolbar (e.g. "Celonis"); falls back to displayName. */
  shortName?: string;
  description: string;
  assumptions: string[];
  targetVendor: string;
}

export interface TemplateRecord {
  id: string;
  name: string;
  type: 'bpmn' | 'document';
  source_vendor: string;
  upload_date: string;
  filename: string;
  is_default: boolean;
  derived_profile?: string;
  description: string;
  pools_count?: number;
  lanes_count?: number;
  skeleton_count?: number;
  owner_id?: string;
  is_builtin?: boolean;
}

export interface AvailableLane {
  id: string;
  name: string;
  pool_name: string;
}

export interface LaneMappingItem {
  actor: string;
  lane_id?: string;
  confidence?: number;
  matched_name?: string;
}

export interface TemplateValidationReport {
  template_id: string;
  name: string;
  is_valid: boolean;
  pools_found: number;
  lanes_found: number;
  skeleton_nodes_found: number;
  warnings: string[];
  errors: string[];
}

export interface BulkExportData {
  process_name: string;
  supported_profiles: string[];
  available_formats: string[];
}

export interface ConversionResponse {
  success: boolean;
  export_blocked?: boolean;
  bpmn_xml: string;
  ir: ProcessIR;
  validation_issues: ValidationIssue[];
  lint_result: LintResult;
  template_info?: {
    template_id: string;
    name: string;
    source_vendor: string;
    lane_map: Record<string, string>;
  };
  bulk_export?: BulkExportData;
  metadata: {
    filename: string;
    process_name: string;
    element_count: number;
    flow_count: number;
    pool_count: number;
    lane_count: number;
    extraction: {
      mode: string;
      tokens_used: number;
    };
  };
  normalized_text: string;
  error?: string;
}

export interface RowValidationErrorItem {
  row: number;
  column: string;
  message: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
  fix?: string;
}

export interface LLMSettings {
  /** Empty string = use the server's .env configuration. */
  provider: '' | 'openai_compatible' | 'anthropic' | 'gemini' | 'mock';
  model: string;
  baseUrl: string;
  apiKey: string;
  temperature: number;
}

/** What the server loaded from .env (GET /api/health). The key itself is never sent. */
export interface ServerConfig {
  auth_mode?: 'none' | 'proxy' | 'token';
  /** false = the deployment ignores per-request provider/model/base_url/api_key (server key is used). */
  client_llm_overrides?: boolean;
  active_provider: string;
  active_model: string;
  base_url: string;
  api_key_set: boolean;
  api_key_hint?: string;
  context_tokens?: number;
  single_pool?: boolean;
  version?: string;
}

/** Result of POST /api/llm/ping. */
export interface LLMPingResult {
  ok: boolean;
  provider?: string;
  model?: string;
  latency_ms?: number;
  kind?: string;
  error?: string;
  note?: string;
}

/** A user-facing error: a short title, one plain sentence, and the raw detail on demand. */
export interface UiError {
  title: string;
  message: string;
  details?: string;
  kind?: string;
  canOpenSettings?: boolean;
}
