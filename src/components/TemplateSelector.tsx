import React from 'react';
import { Layers, GitMerge, Sliders, Check, Download, FileSpreadsheet } from 'lucide-react';
import { TemplateRecord } from '../types';
import { InfoTooltip } from './InfoTooltip';

interface TemplateSelectorProps {
  templates: TemplateRecord[];
  selectedTemplateId: string;
  onSelectTemplate: (templateId: string) => void;
  onOpenManager: () => void;
  onOpenLaneMapping: () => void;
  hasActors?: boolean;
}

export const TemplateSelector: React.FC<TemplateSelectorProps> = ({
  templates,
  selectedTemplateId,
  onSelectTemplate,
  onOpenManager,
  onOpenLaneMapping,
  hasActors = false,
}) => {
  const activeTemplate = templates.find((t) => t.id === selectedTemplateId);

  return (
    <div className="w-full bg-stone-50 border border-stone-200/90 rounded-xl p-3 space-y-2.5 shadow-2xs">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Layers className="w-4 h-4 text-purple-600" />
          <span className="text-xs font-bold uppercase tracking-wider text-stone-700">
            Reference Template Mode
          </span>
          <span className="px-1.5 py-0.2 bg-stone-200/70 text-stone-600 rounded text-[9px] font-bold">
            Opt-in
          </span>
          <InfoTooltip
            title="Reference BPMN Template Mode"
            content="Aligns your output diagram with a corporate reference BPMN template. Preserves predefined swimlanes, vendor metadata (Signavio, Camunda, ARIS, Celonis), and fixed skeleton nodes. When None is selected, standard unconstrained layout is used."
          />
        </div>

        <button
          type="button"
          id="open-template-manager-btn"
          onClick={onOpenManager}
          className="text-xs text-purple-700 hover:text-purple-900 font-semibold hover:underline flex items-center gap-1"
        >
          Manage Templates
        </button>
      </div>

      {/* Main Select Row */}
      <div className="flex items-center gap-2">
        <div className="flex-1 relative">
          <select
            id="template-select-dropdown"
            value={selectedTemplateId}
            onChange={(e) => onSelectTemplate(e.target.value)}
            className="w-full pl-2.5 pr-8 py-1.5 text-xs bg-white border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 font-medium text-stone-800"
          >
            <option value="">None (Standard Auto-Layout)</option>
            {templates.map((tpl) => (
              <option key={tpl.id} value={tpl.id}>
                {tpl.name} ({tpl.source_vendor.toUpperCase()})
                {tpl.is_default ? ' ★' : ''}
              </option>
            ))}
          </select>
        </div>

        {activeTemplate && (
          <button
            type="button"
            id="open-lane-mapping-btn"
            onClick={onOpenLaneMapping}
            title="Configure actor-to-swimlane mappings"
            className="px-2.5 py-1.5 text-xs font-medium text-stone-700 bg-white hover:bg-stone-100 border border-stone-200 rounded-lg transition-colors flex items-center gap-1 shrink-0 shadow-2xs cursor-pointer"
          >
            <GitMerge className="w-3.5 h-3.5 text-purple-600" />
            <span>Map Lanes</span>
            <InfoTooltip
              title="Swimlane Alignment"
              content="Verify and customize how roles or actors detected in your workflow are mapped to the swimlanes in this template."
            />
          </button>
        )}
      </div>

      {/* Template Details / Badges if active */}
      {activeTemplate && (
        <div className="flex items-center justify-between text-[11px] bg-white px-2.5 py-1.5 rounded-lg border border-purple-100 text-stone-600">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-purple-900 uppercase text-[10px]">
              {activeTemplate.source_vendor}
            </span>
            <span className="text-stone-300">•</span>
            <span>{activeTemplate.lanes_count ?? 0} swimlanes</span>
            <span className="text-stone-300">•</span>
            <span>{activeTemplate.skeleton_count ?? 0} skeleton gates</span>
          </div>
          <span className="text-[10px] text-emerald-700 font-medium flex items-center gap-1">
            <Check className="w-3 h-3 text-emerald-600" /> Conforming active
          </span>
        </div>
      )}
    </div>
  );
};
