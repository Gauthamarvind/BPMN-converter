import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Toolbar } from './Toolbar';
import { ProfileMetadata } from '../../types';

/** The API returns the two scope-v2 targets; the order here is deliberately wrong. */
const PROFILES: ProfileMetadata[] = [
  {
    id: 'generic',
    name: 'generic',
    displayName: 'Generic BPMN 2.0 (Standard)',
    shortName: 'Generic',
    description: '',
    assumptions: [],
    targetVendor: '',
  },
  {
    id: 'celonis',
    name: 'celonis',
    displayName: 'Celonis Process Designer',
    shortName: 'Celonis',
    description: '',
    assumptions: [],
    targetVendor: '',
  },
];

function renderToolbar(overrides: Partial<React.ComponentProps<typeof Toolbar>> = {}) {
  const props = {
    appName: 'process2bpmn',
    profiles: PROFILES,
    selectedProfileId: 'celonis',
    onSelectProfile: vi.fn(),
    templates: [],
    selectedTemplateId: '',
    onSelectTemplate: vi.fn(),
    onOpenTemplateManager: vi.fn(),
    onOpenLaneMapping: vi.fn(),
    onOpenSettings: vi.fn(),
    activeModelLabel: 'mock',
    activeModelState: 'mock' as const,
    hasDiagram: false,
    exportBlocked: false,
    onExportBpmn: vi.fn(),
    onExportSvg: vi.fn(),
    onExportPng: vi.fn(),
    onExportZip: vi.fn(),
    ...overrides,
  };
  render(<Toolbar {...props} />);
  return props;
}

describe('Toolbar export targets', () => {
  it('shows exactly the two scope-v2 targets', () => {
    renderToolbar();
    expect(screen.getByText('Celonis')).toBeInTheDocument();
    expect(screen.getByText('Generic')).toBeInTheDocument();
    expect(screen.queryByText('Signavio')).not.toBeInTheDocument();
    expect(screen.queryByText('Camunda')).not.toBeInTheDocument();
    expect(screen.queryByText('ARIS')).not.toBeInTheDocument();
  });

  it('puts Celonis first even when the API lists it second', () => {
    const { container } = render(
      <Toolbar
        appName="process2bpmn"
        profiles={PROFILES}
        selectedProfileId="celonis"
        onSelectProfile={vi.fn()}
        templates={[]}
        selectedTemplateId=""
        onSelectTemplate={vi.fn()}
        onOpenTemplateManager={vi.fn()}
        onOpenLaneMapping={vi.fn()}
        onOpenSettings={vi.fn()}
        activeModelLabel="mock"
        activeModelState="mock"
        hasDiagram={false}
        exportBlocked={false}
        onExportBpmn={vi.fn()}
        onExportSvg={vi.fn()}
        onExportPng={vi.fn()}
        onExportZip={vi.fn()}
      />
    );
    const selector = container.querySelector('#toolbar-profile-selector');
    expect(selector).not.toBeNull();
    const labels = Array.from(selector!.querySelectorAll('button')).map(
      (b) => (b as HTMLButtonElement).textContent?.trim()
    );
    expect(labels[0]).toBe('Celonis');
    expect(labels[1]).toBe('Generic');
  });

  it('reports the chosen target back to the caller', async () => {
    const user = userEvent.setup();
    const props = renderToolbar();
    await user.click(screen.getByText('Generic'));
    expect(props.onSelectProfile).toHaveBeenCalledWith('generic');
  });

  it('offers the capture template but no Step Builder', async () => {
    const user = userEvent.setup();
    const onOpenTemplate = vi.fn();
    renderToolbar({ onOpenTemplate });
    expect(screen.queryByText(/Step Builder/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/samples/i)).not.toBeInTheDocument();
    await user.click(screen.getByTitle('Process capture template'));
    expect(onOpenTemplate).toHaveBeenCalled();
  });
});
