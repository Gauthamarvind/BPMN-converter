import React, { useEffect, useRef, useState } from 'react';
// @ts-ignore
import BpmnViewer from 'bpmn-js/dist/bpmn-navigated-viewer.production.min.js';
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-js.css';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Download,
  Copy,
  Check,
  Package,
  FileCode,
  Loader2,
} from 'lucide-react';
import { saveAs } from 'file-saver';
import JSZip from 'jszip';
import { BulkExportData } from '../types';
import { InfoTooltip } from './InfoTooltip';

interface BpmnViewerProps {
  xml: string;
  selectedElementId?: string;
  onSelectElement?: (id: string) => void;
  processName?: string;
  bulkExport?: BulkExportData;
}

/**
 * Converts an SVG string into a high-resolution PNG blob using an off-screen HTML5 Canvas.
 */
async function svgToPngBlob(svgString: string, scale: number = 2): Promise<Blob> {
  return new Promise((resolve, reject) => {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(svgString, 'image/svg+xml');
      const svgElem = doc.documentElement;

      let width = 1200;
      let height = 800;
      const viewBox = svgElem.getAttribute('viewBox');
      if (viewBox) {
        const parts = viewBox.split(/[\s,]+/).map(parseFloat);
        if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
          width = parts[2];
          height = parts[3];
        }
      } else {
        const wAttr = parseFloat(svgElem.getAttribute('width') || '1200');
        const hAttr = parseFloat(svgElem.getAttribute('height') || '800');
        if (wAttr > 0) width = wAttr;
        if (hAttr > 0) height = hAttr;
      }

      const canvas = document.createElement('canvas');
      canvas.width = Math.max(Math.round(width * scale), 600);
      canvas.height = Math.max(Math.round(height * scale), 400);
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Canvas 2D rendering context not available'));
        return;
      }

      // Crisp background for presentation export
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const img = new Image();

      img.onload = () => {
        try {
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          URL.revokeObjectURL(url);
          canvas.toBlob((b) => {
            if (b) resolve(b);
            else reject(new Error('Canvas toBlob conversion failed'));
          }, 'image/png');
        } catch (err) {
          URL.revokeObjectURL(url);
          reject(err);
        }
      };

      img.onerror = (err) => {
        URL.revokeObjectURL(url);
        reject(err);
      };

      img.src = url;
    } catch (e) {
      reject(e);
    }
  });
}

export const BpmnViewerComponent: React.FC<BpmnViewerProps> = ({
  xml,
  selectedElementId,
  onSelectElement,
  processName = 'process',
  bulkExport,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [copied, setCopied] = useState(false);
  const [exportingSvg, setExportingSvg] = useState(false);
  const [exportingPng, setExportingPng] = useState(false);
  const [exportingBulk, setExportingBulk] = useState(false);

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
    setExportingSvg(true);
    try {
      const { svg } = await viewerRef.current.saveSVG();
      const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
      const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
      saveAs(blob, `${safeName}.svg`);
    } catch (err) {
      console.error('Failed to export SVG:', err);
    } finally {
      setExportingSvg(false);
    }
  };

  const handleExportPng = async () => {
    if (!viewerRef.current) return;
    setExportingPng(true);
    try {
      const { svg } = await viewerRef.current.saveSVG();
      const pngBlob = await svgToPngBlob(svg, 2.5);
      const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
      saveAs(pngBlob, `${safeName}.png`);
    } catch (err) {
      console.error('Failed to export PNG:', err);
    } finally {
      setExportingPng(false);
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

  /**
   * Bulk export all formats at once (.bpmn across all profiles, .svg, .png, manifest) into a ZIP
   */
  const handleBulkExport = async () => {
    if (!viewerRef.current || !xml) return;
    setExportingBulk(true);

    try {
      const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
      const zip = new JSZip();

      // 1. Render SVG from canvas
      const { svg } = await viewerRef.current.saveSVG();
      zip.file(`${safeName}.svg`, svg);

      // 2. Render high-res PNG image from SVG
      try {
        const pngBlob = await svgToPngBlob(svg, 2.5);
        zip.file(`${safeName}.png`, pngBlob);
      } catch (err) {
        console.warn('PNG rasterization inside ZIP failed, proceeding with SVG:', err);
      }

      // 3. Add all profile BPMN XML files
      const profileXmlMap: Record<string, string> =
        bulkExport?.bpmn_by_profile && Object.keys(bulkExport.bpmn_by_profile).length > 0
          ? bulkExport.bpmn_by_profile
          : {
              generic: xml,
              camunda: xml,
              signavio: xml,
              celonis: xml,
              aris: xml,
            };

      const profileDescriptions: Record<string, string> = {
        camunda: 'Camunda 8 / Zeebe execution semantics (zeebe:taskDefinition)',
        signavio: 'SAP Signavio enterprise compliance & glossary annotations',
        celonis: 'Celonis Execution Management & Process Mining schema',
        aris: 'Software AG ARIS enterprise repository export',
        generic: 'Standard OMG BPMN 2.0 Analytic schema',
      };

      for (const [prof, profXml] of Object.entries(profileXmlMap)) {
        zip.file(`${safeName}_${prof}.bpmn`, profXml);
      }

      // 4. Manifest / README documentation
      const manifest = {
        processName: processName,
        exportedAt: new Date().toISOString(),
        profiles: Object.keys(profileXmlMap),
        formats: ['.bpmn', '.svg', '.png'],
        generator: 'Text2BPMN Pipeline 2.0',
      };
      zip.file('manifest.json', JSON.stringify(manifest, null, 2));

      let readmeContent = `Text2BPMN Export Bundle
==================================================
Process Name : ${processName}
Export Date  : ${new Date().toUTCString()}
Generator    : Text2BPMN 2.0 (Sugiyama Manhattan Layout)

This package contains complete BPMN 2.0 models tailored for all enterprise platforms,
along with high-resolution visual diagram assets.

Included Files:
--------------------------------------------------
`;

      for (const prof of Object.keys(profileXmlMap)) {
        const desc = profileDescriptions[prof] || `${prof.toUpperCase()} profile`;
        readmeContent += `* ${safeName}_${prof}.bpmn\n  Target: ${desc}\n\n`;
      }

      readmeContent += `* ${safeName}.svg\n  Target: Scalable Vector Graphics (lossless resolution)\n\n`;
      readmeContent += `* ${safeName}.png\n  Target: High-resolution PNG raster preview\n\n`;
      readmeContent += `* manifest.json\n  Target: Machine-readable deployment metadata\n\n`;

      zip.file('README.txt', readmeContent);

      // 5. Generate and trigger download of ZIP archive
      const zipBlob = await zip.generateAsync({
        type: 'blob',
        compression: 'DEFLATE',
        compressionOptions: { level: 6 },
      });

      saveAs(zipBlob, `${safeName}_all_formats.zip`);
    } catch (err) {
      console.error('Failed to generate bulk export bundle:', err);
    } finally {
      setExportingBulk(false);
    }
  };

  return (
    <div
      id="bpmn-viewer-panel"
      className="relative w-full h-full flex flex-col bg-stone-50 overflow-hidden border border-stone-200 rounded-xl"
    >
      {/* Viewer Floating Controls */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-1.5 bg-white/95 backdrop-blur-sm px-2 py-1.5 rounded-lg border border-stone-200/80 shadow-sm">
        <button
          id="zoom-in-btn"
          onClick={handleZoomIn}
          title="Zoom In"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors cursor-pointer"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          id="zoom-out-btn"
          onClick={handleZoomOut}
          title="Zoom Out"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors cursor-pointer"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <div className="w-px h-4 bg-stone-200 mx-0.5" />
        <button
          id="fit-viewport-btn"
          onClick={handleFitViewport}
          title="Fit to Viewport"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors cursor-pointer"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          id="reset-zoom-btn"
          onClick={handleResetZoom}
          title="Reset Zoom (100%)"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors cursor-pointer"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        <div className="w-px h-4 bg-stone-200 mx-0.5" />
        <button
          id="copy-xml-btn"
          onClick={handleCopyXml}
          title="Copy BPMN XML"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors flex items-center gap-1 cursor-pointer"
        >
          {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
        </button>

        {/* Single Format Exports: SVG & PNG */}
        <button
          id="download-svg-btn"
          onClick={handleExportSvg}
          disabled={exportingSvg}
          title="Export Vector SVG"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors text-xs font-medium cursor-pointer"
        >
          {exportingSvg ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'SVG'}
        </button>

        <button
          id="download-png-btn"
          onClick={handleExportPng}
          disabled={exportingPng}
          title="Export High-Res PNG"
          className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-md transition-colors text-xs font-medium cursor-pointer"
        >
          {exportingPng ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'PNG'}
        </button>

        {/* Active Profile BPMN Download */}
        <button
          id="download-bpmn-btn"
          onClick={handleDownloadBpmn}
          title="Download active profile .bpmn XML"
          className="px-2 py-1 text-xs font-medium text-stone-700 bg-stone-100 hover:bg-stone-200 border border-stone-300/80 rounded-md transition-colors flex items-center gap-1 shadow-2xs cursor-pointer"
        >
          <Download className="w-3.5 h-3.5" />
          .BPMN
        </button>

        <div className="w-px h-4 bg-stone-200 mx-0.5" />

        {/* Bulk Export All Formats (.zip) */}
        <div className="flex items-center gap-1">
          <button
            id="bulk-export-all-btn"
            onClick={handleBulkExport}
            disabled={exportingBulk || !xml}
            title="Bulk Export: All profiles (.bpmn), SVG, and PNG in one ZIP"
            className="px-2.5 py-1 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 rounded-md transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            {exportingBulk ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Exporting...</span>
              </>
            ) : (
              <>
                <Package className="w-3.5 h-3.5" />
                <span>Export All (.ZIP)</span>
              </>
            )}
          </button>
          <InfoTooltip
            title="Bulk Export Package"
            content="Downloads all supported profile formats (.bpmn for Camunda, Signavio, Celonis, ARIS, Generic) plus high-resolution SVG and PNG diagrams in a single compressed ZIP archive."
          />
        </div>
      </div>

      {/* BPMN Canvas Container */}
      <div
        id="bpmn-canvas-target"
        ref={containerRef}
        className="w-full h-full cursor-grab active:cursor-grabbing"
      />

      {/* Watermark / status info */}
      <div className="absolute bottom-3 left-3 z-10 text-[11px] text-stone-400 pointer-events-none bg-white/70 px-2 py-0.5 rounded border border-stone-200/50">
        Text2BPMN Analytic Diagram • Sugiyama Manhattan Layout
      </div>
    </div>
  );
};
