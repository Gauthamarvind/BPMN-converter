/**
 * File-type routing for uploads.
 *
 * A BPMN file goes to the deterministic import path (/api/import/bpmn); everything else goes
 * through extraction (/api/convert). Kept here rather than inline in App so the rule has one
 * definition and can be tested on its own.
 */

/** Extensions routed to the BPMN importer. */
export const BPMN_EXTENSIONS = ['.bpmn', '.bpmn2', '.xml'] as const;

/** Extensions the extraction pipeline accepts, for the dropzone `accept` attribute. */
export const DOCUMENT_EXTENSIONS = [
  '.txt',
  '.md',
  '.markdown',
  '.csv',
  '.docx',
  '.xlsx',
  '.pdf',
  '.json',
  '.srt',
  '.vtt',
] as const;

/** Everything a dropzone will take, BPMN files included. */
export const ACCEPTED_EXTENSIONS = [...DOCUMENT_EXTENSIONS, ...BPMN_EXTENSIONS].join(',');

export const isBpmnFile = (name: string): boolean =>
  BPMN_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext));
