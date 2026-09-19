import React from 'react';
import { ZoomIn, ZoomOut, Maximize2, RotateCcw, AlertCircle, Info, Wand2 } from 'lucide-react';
import { Badge } from '../ui/Badge';

export interface FloatingControlsProps {
  elementCount?: number;
  flowCount?: number;
  laneCount?: number;
  extractionMode?: string;
  issuesCount?: number;
  /** Set when the diagram kept the coordinates of an imported file, so re-layout is offered. */
  canRelayout?: boolean;
  onRelayout?: () => void;
  onOpenIssues: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitViewport: () => void;
  onResetZoom: () => void;
}

export const FloatingControls: React.FC<FloatingControlsProps> = ({
  elementCount = 0,
  flowCount = 0,
  laneCount = 0,
  extractionMode,
  issuesCount = 0,
  canRelayout = false,
  onRelayout,
  onOpenIssues,
  onZoomIn,
  onZoomOut,
  onFitViewport,
  onResetZoom,
}) => {
  return (
    <>
      {/* Bottom-Left Status Pill */}
      <div className="absolute bottom-4 left-4 z-20 flex items-center gap-2 bg-[var(--surface)] backdrop-blur-[20px] px-3 py-1.5 rounded-full border border-[var(--separator)] shadow-[var(--shadow-hairline)] select-none">
        <span className="text-[12px] font-medium text-[var(--text)]">
          {elementCount} Elements · {flowCount} Flows · {laneCount} Lanes
        </span>

        {extractionMode && (
          <span className="text-[12px] text-[var(--text-secondary-color)] hidden sm:inline">
            · {extractionMode}
          </span>
        )}

        {canRelayout && onRelayout && (
          <button
            id="relayout-btn"
            onClick={onRelayout}
            title="Replace the imported coordinates with a clean automatic layout"
            className="ml-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--accent-subtle)] text-[var(--accent)] text-[12px] font-medium hover:opacity-80 transition-opacity cursor-pointer"
          >
            <Wand2 className="w-3 h-3" />
            <span>Re-layout</span>
          </button>
        )}

        {issuesCount > 0 && (
          <button
            onClick={onOpenIssues}
            className="ml-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--danger-subtle)] text-[var(--danger)] text-[12px] font-medium hover:opacity-80 transition-opacity cursor-pointer"
          >
            <AlertCircle className="w-3 h-3" />
            <span>{issuesCount} {issuesCount === 1 ? 'Issue' : 'Issues'}</span>
          </button>
        )}
      </div>

      {/* Bottom-Right Zoom Controls Pill */}
      <div className="absolute bottom-4 right-4 z-20 flex items-center bg-[var(--surface)] backdrop-blur-[20px] p-1 rounded-full border border-[var(--separator)] shadow-[var(--shadow-hairline)] select-none">
        <button
          onClick={onZoomOut}
          title="Zoom Out"
          className="w-7 h-7 rounded-full flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={onResetZoom}
          title="Reset Zoom (100%)"
          className="px-2 h-7 rounded-full text-[12px] font-medium text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
        >
          100%
        </button>
        <button
          onClick={onZoomIn}
          title="Zoom In"
          className="w-7 h-7 rounded-full flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>
        <div className="w-px h-3.5 bg-[var(--separator)] mx-0.5" />
        <button
          onClick={onFitViewport}
          title="Fit Diagram to Viewport"
          className="px-2.5 h-7 rounded-full text-[12px] font-medium text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors cursor-pointer"
        >
          Fit
        </button>
      </div>
    </>
  );
};
