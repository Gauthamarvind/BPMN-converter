import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { FloatingControls } from './FloatingControls';

const base = {
  elementCount: 8,
  flowCount: 8,
  laneCount: 3,
  onOpenIssues: vi.fn(),
  onZoomIn: vi.fn(),
  onZoomOut: vi.fn(),
  onFitViewport: vi.fn(),
  onResetZoom: vi.fn(),
};

describe('FloatingControls', () => {
  it('summarises the diagram', () => {
    render(<FloatingControls {...base} />);
    expect(screen.getByText(/8 Elements · 8 Flows · 3 Lanes/)).toBeInTheDocument();
  });

  it('offers Re-layout only for an imported diagram that kept its coordinates', () => {
    const { rerender } = render(<FloatingControls {...base} />);
    expect(screen.queryByText('Re-layout')).not.toBeInTheDocument();

    rerender(<FloatingControls {...base} canRelayout onRelayout={vi.fn()} />);
    expect(screen.getByText('Re-layout')).toBeInTheDocument();
  });

  it('asks for a fresh layout when clicked', async () => {
    const user = userEvent.setup();
    const onRelayout = vi.fn();
    render(<FloatingControls {...base} canRelayout onRelayout={onRelayout} />);
    await user.click(screen.getByText('Re-layout'));
    expect(onRelayout).toHaveBeenCalledTimes(1);
  });

  it('surfaces the issue count', async () => {
    const user = userEvent.setup();
    const onOpenIssues = vi.fn();
    render(<FloatingControls {...base} issuesCount={2} onOpenIssues={onOpenIssues} />);
    await user.click(screen.getByText('2 Issues'));
    expect(onOpenIssues).toHaveBeenCalled();
  });
});
