import React, { useEffect, useRef, useState } from 'react';
// @ts-ignore
import BpmnViewer from 'bpmn-js/dist/bpmn-navigated-viewer.production.min.js';
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-js.css';
import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Download, Copy, Check } from 'lucide-react';
import { saveAs } from 'file-saver';

interface BpmnViewerProps {
  xml: string;
  selectedElementId?: string;
  onSelectElement?: (id: string) => void;
  processName?: string;
}

export const BpmnViewerComponent: React.FC<BpmnViewerProps> = ({
  xml,
  selectedElementId,
  onSelectElement,
  processName = 'process',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    // Destroy existing instance
    if (viewerRef.current) {
      viewerRef.current.destroy();
      viewerRef.current = null;
    }

    const viewer = new BpmnViewer({
      container: containerRef.current,
    });

    viewerRef.current = viewer;

    const eventBus = viewer.get('eventBus');
    eventBus.on('element.click', (event: any) => {
      const element = event.element;
      if (element && element.id && onSelectElement) {
        onSelectElement(element.id);
      }
    });

    return () => {
      if (viewerRef.current) {
        viewerRef.current.destroy();
        viewerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!viewerRef.current || !xml) return;

    viewerRef.current
      .importXML(xml)
      .then(() => {
        const canvas = viewerRef.current.get('canvas');
        canvas.zoom('fit-viewport');
      })
      .catch((err: any) => {
        console.error('Error rendering BPMN XML:', err);
      });
  }, [xml]);

  // Handle selected element highlight
  useEffect(() => {
    if (!viewerRef.current || !xml) return;
    try {
      const canvas = viewerRef.current.get('canvas');
      const elementRegistry = viewerRef.current.get('elementRegistry');

      // Clear previous markers
      elementRegistry.forEach((elem: any) => {
        canvas.removeMarker(elem.id, 'highlight-node');
      });

      if (selectedElementId && elementRegistry.get(selectedElementId)) {
        canvas.addMarker(selectedElementId, 'highlight-node');
      }
    } catch (e) {
      // Ignore if element is not rendered
    }
  }, [selectedElementId, xml]);

  const handleZoomIn = () => {
    if (!viewerRef.current) return;
    const canvas = viewerRef.current.get('canvas');
    canvas.zoom(canvas.zoom() * 1.2);
  };

  const handleZoomOut = () => {
    if (!viewerRef.current) return;
    const canvas = viewerRef.current.get('canvas');
    canvas.zoom(canvas.zoom() * 0.8);
  };

  const handleFitViewport = () => {
    if (!viewerRef.current) return;
    const canvas = viewerRef.current.get('canvas');
    canvas.zoom('fit-viewport');
  };

  const handleResetZoom = () => {
    if (!viewerRef.current) return;
    const canvas = viewerRef.current.get('canvas');
    canvas.zoom(1.0);
  };

  const handleExportSvg = async () => {
    if (!viewerRef.current) return;
    setExporting(true);
    try {
      const { svg } = await viewerRef.current.saveSVG();
      const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
      const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
      saveAs(blob, `${safeName}.svg`);
    } catch (err) {
      console.error('Failed to export SVG:', err);
    } finally {
      setExporting(false);
    }
  };

  const handleDownloadBpmn = () => {
    if (!xml) return;
    const blob = new Blob([xml], { type: 'application/xml;charset=utf-8' });
    const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
    saveAs(blob, `${safeName}.bpmn`);
  };

  const handleCopyXml = () => {
    if (!xml) return;
    navigator.clipboard.writeText(xml).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div id="bpmn-viewer-panel" className="relative w-full h-full flex flex-col bg-stone-50 overflow-hidden border border-stone-200 rounded-xl">
      {/* Viewer Floating Controls */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-1.5 bg-white/95 backdrop-blur-sm px-2 py-1.5 rounded-lg border border-stone-200/80 shadow-sm">
        <button
          id="zoom-in-btn"
          onClick={handleZoomIn}
          title="Zoom In"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          id="zoom-out-btn"
          onClick={handleZoomOut}
          title="Zoom Out"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <div className="w-px h-4 bg-stone-200 mx-0.5" />
        <button
          id="fit-viewport-btn"
          onClick={handleFitViewport}
          title="Fit to Viewport"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          id="reset-zoom-btn"
          onClick={handleResetZoom}
          title="Reset Zoom (100%)"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        <div className="w-px h-4 bg-stone-200 mx-0.5" />
        <button
          id="copy-xml-btn"
          onClick={handleCopyXml}
          title="Copy BPMN XML"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors flex items-center gap-1"
        >
          {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
        </button>
        <button
          id="download-svg-btn"
          onClick={handleExportSvg}
          disabled={exporting}
          title="Export Vector SVG"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors text-xs font-medium"
        >
          SVG
        </button>
        <button
          id="download-bpmn-btn"
          onClick={handleDownloadBpmn}
          title="Download .bpmn file"
          className="px-2 py-1 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors flex items-center gap-1 shadow-sm"
        >
          <Download className="w-3.5 h-3.5" />
          .BPMN
        </button>
      </div>

      {/* BPMN Canvas Container */}
      <div
        id="bpmn-canvas-target"
        ref={containerRef}
        className="w-full h-full cursor-grab active:cursor-grabbing"
      />

      {/* Watermark / status info */}
      <div className="absolute bottom-3 left-3 z-10 text-[11px] text-stone-400 pointer-events-none bg-white/70 px-2 py-0.5 rounded border border-stone-200/50">
        BPMN 2.0 Analytic Diagram • Sugiyama Manhattan Layout
      </div>
    </div>
  );
};
