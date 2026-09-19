import { describe, expect, it } from 'vitest';

import { ACCEPTED_EXTENSIONS, isBpmnFile } from './files';

describe('upload routing', () => {
  it('sends BPMN files to the importer', () => {
    expect(isBpmnFile('camunda_export.bpmn')).toBe(true);
    expect(isBpmnFile('Signavio Export.BPMN')).toBe(true);
    expect(isBpmnFile('model.bpmn2')).toBe(true);
    expect(isBpmnFile('aris_export.xml')).toBe(true);
  });

  it('sends everything else through extraction', () => {
    expect(isBpmnFile('sop.docx')).toBe(false);
    expect(isBpmnFile('claim.xlsx')).toBe(false);
    expect(isBpmnFile('notes.txt')).toBe(false);
    expect(isBpmnFile('transcript.vtt')).toBe(false);
    // a name that merely contains the word
    expect(isBpmnFile('how_to_bpmn.pdf')).toBe(false);
  });

  it('accepts both document and BPMN extensions in the dropzone', () => {
    expect(ACCEPTED_EXTENSIONS).toContain('.docx');
    expect(ACCEPTED_EXTENSIONS).toContain('.bpmn');
    expect(ACCEPTED_EXTENSIONS).toContain('.xml');
  });
});
