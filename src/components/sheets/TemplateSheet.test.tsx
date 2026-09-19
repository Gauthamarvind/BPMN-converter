import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { TemplateSheet } from './TemplateSheet';

describe('TemplateSheet', () => {
  it('offers the blank form and a single filled example, in both formats', () => {
    render(<TemplateSheet isOpen onClose={vi.fn()} />);
    expect(screen.getByText('Download blank (.xlsx)')).toBeInTheDocument();
    expect(screen.getByText('Download blank (.docx)')).toBeInTheDocument();
    expect(screen.getByText('Download example (.xlsx)')).toBeInTheDocument();
    expect(screen.getByText('Download example (.docx)')).toBeInTheDocument();
  });

  it('does not offer sample workflows or the Step Builder', () => {
    render(<TemplateSheet isOpen onClose={vi.fn()} />);
    expect(screen.queryByText(/sample process/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Step Builder/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Load & Convert/i)).not.toBeInTheDocument();
  });

  it('downloads from the blank-template route rather than a removed samples route', async () => {
    const user = userEvent.setup();
    const clicked: string[] = [];
    const realCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = realCreate(tag);
      if (tag === 'a') {
        el.click = () => clicked.push((el as HTMLAnchorElement).href);
      }
      return el;
    });

    render(<TemplateSheet isOpen onClose={vi.fn()} />);
    await user.click(screen.getByText('Download blank (.xlsx)'));

    expect(clicked).toHaveLength(1);
    expect(clicked[0]).toContain('/api/templates/download-blank');
    expect(clicked[0]).toContain('sample=false');
    expect(clicked[0]).not.toContain('/api/samples');
  });

  it('hands off to the reference-template manager', async () => {
    const user = userEvent.setup();
    const onOpenTemplateManager = vi.fn();
    const onClose = vi.fn();
    render(
      <TemplateSheet isOpen onClose={onClose} onOpenTemplateManager={onOpenTemplateManager} />
    );
    await user.click(screen.getByText('Manage'));
    expect(onClose).toHaveBeenCalled();
    expect(onOpenTemplateManager).toHaveBeenCalled();
  });
});
