import { UiError } from '../types';

interface ApiErrorBody {
  error?: string;
  detail?: string;
  message?: string;
  kind?: string;
  provider?: string;
  model?: string;
  errors?: string[];
  row_errors?: unknown[];
}

/**
 * Turns an HTTP failure from the API into something a person can act on.
 * The raw server message is kept as `details` and shown only when asked for.
 */
export function describeApiError(status: number, body: ApiErrorBody | null | undefined): UiError {
  const raw = (body && (body.error || body.detail || body.message)) || `Request failed (${status})`;
  const kind = (body && body.kind) || '';
  const where =
    body && (body.provider || body.model)
      ? ` (${[body.provider, body.model].filter(Boolean).join(' · ')})`
      : '';

  switch (kind) {
    case 'LLMConnectionError':
      return {
        kind,
        details: raw,
        canOpenSettings: true,
        title: 'Can’t reach the model endpoint',
        message: `Nothing answered at the configured address${where}. Check the provider and base URL in Settings, or that your local model server is running.`,
      };
    case 'LLMAuthenticationError':
      return {
        kind,
        details: raw,
        canOpenSettings: true,
        title: 'The API key was rejected',
        message: `The provider refused the key${where}. Paste a valid key in Settings, or fix LLM_API_KEY in .env and restart.`,
      };
    case 'LLMRateLimitError':
      return {
        kind,
        details: raw,
        canOpenSettings: true,
        title: 'The model is rate-limited right now',
        message: `The provider returned a quota or rate-limit error${where}. Wait a moment and try again, or switch models.`,
      };
    case 'LLMValidationError':
      return {
        kind,
        details: raw,
        canOpenSettings: true,
        title: 'The model didn’t return a usable process',
        message:
          'Three attempts produced JSON that doesn’t match the process schema. A larger model usually fixes this; adding structure to the text (numbered steps, named roles) helps too.',
      };
    case 'LLMConfigurationError':
      return { kind, details: raw, canOpenSettings: true, title: 'The model provider isn’t configured', message: raw };
    case 'IngestionError':
      return { kind, details: raw, title: 'Couldn’t read this file', message: raw };
    case 'RowValidationError':
      return {
        kind,
        details: raw,
        title: 'The template has rows that need fixing',
        message: 'Open the Issues tab to see each row and what to change. Conversion continues once the errors are resolved.',
      };
    case 'BpmnSchemaError':
      return {
        kind,
        details: raw,
        title: 'The generated diagram failed BPMN schema validation',
        message: 'This is a bug in the exporter rather than in your input. Please report it with the file you converted.',
      };
    default:
      if (status === 413) {
        return { kind, details: raw, title: 'File is too large', message: 'The limit is 20 MB. Split the document or paste the relevant section as text.' };
      }
      if (status === 415) {
        return { kind, details: raw, title: 'Unsupported file type', message: raw };
      }
      if (status === 502) {
        return { kind, details: raw, canOpenSettings: true, title: 'The model request failed', message: raw };
      }
      return { kind, details: raw, title: 'Conversion failed', message: raw };
  }
}

export function describeUnexpectedError(err: unknown): UiError {
  const message = err instanceof Error ? err.message : String(err);
  return { title: 'Something went wrong', message, details: message };
}
