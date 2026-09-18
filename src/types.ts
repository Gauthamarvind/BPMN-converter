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

export interface ProcessIR {
  id: string;
  name: string;
  elements: FlowNode[];
  flows: SequenceFlow[];
  pools: Pool[];
  open_questions?: string[];
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
  description: string;
  assumptions: string[];
  targetVendor: string;
}

export interface SampleFile {
  name: string;
  title: string;
  extension: string;
  content: string;
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
  bpmn_by_profile: Record<string, string>;
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

export interface StepBuilderRow {
  step_id: string;
  step: string;
  responsible: string;
  type: 'Task' | 'Decision' | 'End';
  if_yes?: string;
  if_no?: string;
  parallel_group?: string;
  next_step?: string;
  description?: string;
  system?: string;
  input_data?: string;
  output_data?: string;
  duration?: string;
}

export interface RowValidationErrorItem {
  row: number;
  column: string;
  message: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
  fix?: string;
}

export interface LLMSettings {
  provider: 'openai_compatible' | 'anthropic' | 'gemini' | 'mock';
  model: string;
  baseUrl: string;
  apiKey: string;
  temperature: number;
}
