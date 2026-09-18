import React, {
  useEffect,
  useRef,
  useState,
  useImperativeHandle,
  forwardRef,
} from 'react';
// @ts-ignore
import BpmnViewer from 'bpmn-js/dist/bpmn-navigated-viewer.production.min.js';
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-js.css';
import { saveAs } from 'file-saver';
import JSZip from 'jszip';
import { BulkExportData } from '../types';
import { Skeleton } from './ui/Skeleton';

export interface BpmnViewerHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  fitViewport: () => void;
  resetZoom: () => void;
  exportBpmn: () => void;
  exportSvg: () => Promise<void>;
  exportPng: () => Promise<void>;
  exportZip: () => Promise<void>;
}

export interface BpmnViewerProps {
  xml: string;
  selectedElementId?: string;
  onSelectElement?: (id: string) => void;
  processName?: string;
  bulkExport?: BulkExportData;
  isLoading?: boolean;
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

export const BpmnViewerComponent = forwardRef<BpmnViewerHandle, BpmnViewerProps>(
  (
    {
      xml,
      selectedElementId,
      onSelectElement,
      processName = 'process',
      bulkExport,
      isLoading,
    },
    ref
  ) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const viewerRef = useRef<any>(null);

    // Imperative methods exposed to Toolbar and Floating Controls
    useImperativeHandle(ref, () => ({
      zoomIn: () => {
        if (!viewerRef.current) return;
        const canvas = viewerRef.current.get('canvas');
        canvas.zoom(canvas.zoom() * 1.2);
      },
      zoomOut: () => {
        if (!viewerRef.current) return;
        const canvas = viewerRef.current.get('canvas');
        canvas.zoom(canvas.zoom() * 0.8);
      },
      fitViewport: () => {
        if (!viewerRef.current) return;
        const canvas = viewerRef.current.get('canvas');
        canvas.zoom('fit-viewport');
      },
      resetZoom: () => {
        if (!viewerRef.current) return;
        const canvas = viewerRef.current.get('canvas');
        canvas.zoom(1.0);
      },
      exportBpmn: () => {
        if (!xml) return;
        const blob = new Blob([xml], { type: 'application/xml;charset=utf-8' });
        const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
        saveAs(blob, `${safeName}.bpmn`);
      },
      exportSvg: async () => {
        if (!viewerRef.current) return;
        try {
          const { svg } = await viewerRef.current.saveSVG();
          const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
          const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
          saveAs(blob, `${safeName}.svg`);
        } catch (err) {
          console.error('Failed to export SVG:', err);
        }
      },
      exportPng: async () => {
        if (!viewerRef.current) return;
        try {
          const { svg } = await viewerRef.current.saveSVG();
          const pngBlob = await svgToPngBlob(svg, 2.5);
          const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
          saveAs(pngBlob, `${safeName}.png`);
        } catch (err) {
          console.error('Failed to export PNG:', err);
        }
      },
      exportZip: async () => {
        if (!viewerRef.current || !xml) return;
        try {
          const safeName = processName.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
          const zip = new JSZip();

          const { svg } = await viewerRef.current.saveSVG();
          zip.file(`${safeName}.svg`, svg);

          try {
            const pngBlob = await svgToPngBlob(svg, 2.5);
            zip.file(`${safeName}.png`, pngBlob);
          } catch (err) {
            console.warn('PNG rasterization inside ZIP failed:', err);
          }

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

          for (const [prof, profXml] of Object.entries(profileXmlMap)) {
            zip.file(`${safeName}_${prof}.bpmn`, profXml);
          }

          const manifest = {
            processName: processName,
            exportedAt: new Date().toISOString(),
            profiles: Object.keys(profileXmlMap),
            formats: ['.bpmn', '.svg', '.png'],
            generator: 'Text2BPMN Pipeline 2.0',
          };
          zip.file('manifest.json', JSON.stringify(manifest, null, 2));

          const zipBlob = await zip.generateAsync({
            type: 'blob',
            compression: 'DEFLATE',
            compressionOptions: { level: 6 },
          });

          saveAs(zipBlob, `${safeName}_all_formats.zip`);
        } catch (err) {
          console.error('Failed to generate bulk export bundle:', err);
        }
      },
    }));

    // Initialize bpmn-js
    useEffect(() => {
      if (!containerRef.current) return;

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

    // Render XML on changes
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

        elementRegistry.forEach((elem: any) => {
          canvas.removeMarker(elem.id, 'highlight-node');
        });

        if (selectedElementId && elementRegistry.get(selectedElementId)) {
          canvas.addMarker(selectedElementId, 'highlight-node');
        }
      } catch (e) {
        // Element not in current view
      }
    }, [selectedElementId, xml]);

    return (
      <div
        id="bpmn-canvas-container"
        className="relative w-full h-full bg-[var(--surface-solid)] overflow-hidden flex items-center justify-center"
      >
        {isLoading && (
          <div className="absolute inset-0 z-30 bg-[var(--surface-solid)]/80 backdrop-blur-[4px] flex flex-col items-center justify-center p-8 space-y-4">
            <Skeleton width="60%" height="40px" rounded="rounded-[12px]" />
            <Skeleton width="80%" height="240px" rounded="rounded-[16px]" />
            <div className="flex items-center gap-2 text-[13px] text-[var(--text-secondary-color)]">
              <span className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
              <span>Generating BPMN diagram layout...</span>
            </div>
          </div>
        )}

        <div
          id="bpmn-canvas-target"
          ref={containerRef}
          className="w-full h-full cursor-grab active:cursor-grabbing p-4"
        />
      </div>
    );
  }
);

BpmnViewerComponent.displayName = 'BpmnViewerComponent';
