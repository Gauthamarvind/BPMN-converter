import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import App from './App';

/**
 * A BPMN file must go to /api/import/bpmn and everything else to /api/convert. Getting this
 * wrong sends a foreign BPMN file through the language model, which is both wrong and slow.
 */

const HEALTH = {
  status: 'healthy',
  service: 'Process2BPMN',
  active_provider: 'mock',
  active_model: 'rule-engine',
  api_key_set: false,
};

const PROFILES = {
  profiles: [
    { id: 'celonis', name: 'celonis', displayName: 'Celonis Process Designer', shortName: 'Celonis', description: '', assumptions: [], targetVendor: '' },
    { id: 'generic', name: 'generic', displayName: 'Generic BPMN 2.0', shortName: 'Generic', description: '', assumptions: [], targetVendor: '' },
  ],
};

const CONVERSION = {
  success: true,
  export_blocked: false,
  bpmn_xml: '<?xml version="1.0"?><bpmn:definitions/>',
  ir: { id: 'Process_1', name: 'Imported', pools: [], elements: [], flows: [] },
  validation_issues: [],
  lint_result: { profile_name: 'celonis', display_name: 'Celonis', is_valid: true, assumptions: [], warnings: [] },
  metadata: {
    filename: 'x',
    process_name: 'Imported',
    element_count: 8,
    flow_count: 8,
    pool_count: 1,
    lane_count: 3,
    extraction: { mode: 'bpmn-import', tokens_used: 0 },
  },
  normalized_text: '',
};

function mockFetch() {
  const calls: string[] = [];
  const fetchMock = vi.fn(async (url: string) => {
    calls.push(url);
    const body =
      url.startsWith('/api/health') ? HEALTH :
      url.startsWith('/api/profiles') ? PROFILES :
      url.startsWith('/api/templates') ? { templates: [] } :
      CONVERSION;
    return { ok: true, status: 200, json: async () => body } as unknown as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
  return calls;
}

function uploadInput(): HTMLInputElement {
  const inputs = Array.from(document.querySelectorAll('input[type="file"]')) as HTMLInputElement[];
  expect(inputs.length).toBeGreaterThan(0);
  return inputs[0];
}

describe('upload routing in App', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it('nothing is preloaded onto the canvas', async () => {
    const calls = mockFetch();
    render(<App />);
    await waitFor(() => expect(calls.some((c) => c.startsWith('/api/profiles'))).toBe(true));
    expect(calls.some((c) => c.startsWith('/api/samples'))).toBe(false);
    expect(screen.getByText(/Turn any process description into BPMN/i)).toBeInTheDocument();
  });

  it('sends a .bpmn upload to the import endpoint', async () => {
    const user = userEvent.setup();
    const calls = mockFetch();
    render(<App />);
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));

    const file = new File(['<bpmn:definitions/>'], 'camunda_export.bpmn', { type: 'application/xml' });
    await user.upload(uploadInput(), file);

    await waitFor(() => expect(calls).toContain('/api/import/bpmn'));
    expect(calls).not.toContain('/api/convert');
  });

  it('sends a document upload to the conversion endpoint', async () => {
    const user = userEvent.setup();
    const calls = mockFetch();
    render(<App />);
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));

    const file = new File(['1. Do the thing'], 'sop.txt', { type: 'text/plain' });
    await user.upload(uploadInput(), file);

    await waitFor(() => expect(calls).toContain('/api/convert'));
    expect(calls).not.toContain('/api/import/bpmn');
  });
});
