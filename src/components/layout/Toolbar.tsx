import React, { useState } from 'react';
import { Settings as SettingsIcon, Layers, Download, Check, GitMerge, ChevronDown, Table, FileSpreadsheet } from 'lucide-react';
import { ProfileMetadata, TemplateRecord } from '../../types';
import { Button } from '../ui/Button';
import { SegmentedControl, SegmentedOption } from '../ui/SegmentedControl';
import { Popover } from '../ui/Popover';

export interface ToolbarProps {
  appName?: string;
  profiles: ProfileMetadata[];
  selectedProfileId: string;
  onSelectProfile: (profileId: string) => void;
  templates: TemplateRecord[];
  selectedTemplateId: string;
  onSelectTemplate: (templateId: string) => void;
  onOpenTemplateManager: () => void;
  onOpenLaneMapping: () => void;
  onOpenSettings: () => void;
  onOpenStepBuilder?: () => void;
  onExportBpmn: () => void;
  onExportSvg: () => void;
  onExportPng: () => void;
  onExportZip: () => void;
  isExportingZip?: boolean;
  hasDiagram?: boolean;
  exportBlocked?: boolean;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  appName = 'process2bpmn',
  profiles,
  selectedProfileId,
  onSelectProfile,
  templates,
  selectedTemplateId,
  onSelectTemplate,
  onOpenTemplateManager,
  onOpenLaneMapping,
  onOpenSettings,
  onOpenStepBuilder,
  onExportBpmn,
  onExportSvg,
  onExportPng,
  onExportZip,
  isExportingZip,
  hasDiagram,
  exportBlocked,
}) => {
  const [isTemplateMenuOpen, setIsTemplateMenuOpen] = useState(false);
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false);

  // Profile options for SegmentedControl
  const profileOptions: SegmentedOption[] = profiles.map((p) => ({
    id: p.id,
    label: p.displayName || p.name,
  }));

  const activeTemplate = templates.find((t) => t.id === selectedTemplateId);

  return (
    <header className="h-[52px] w-full px-6 flex items-center justify-between bg-[var(--surface)] backdrop-blur-[20px] border-b border-[var(--separator)] select-none shrink-0 z-30">
      {/* Left: App Identity */}
      <div className="flex items-center gap-3">
        <span className="text-[15px] font-semibold text-[var(--text)] tracking-tight">
          {appName}
        </span>
      </div>

      {/* Center: Target Tool Segmented Control */}
      {profileOptions.length > 0 && (
        <div className="hidden md:flex items-center">
          <SegmentedControl
            id="toolbar-profile-selector"
            options={profileOptions}
            value={selectedProfileId}
            onChange={onSelectProfile}
          />
        </div>
      )}

      {/* Right: Template picker, Primary Export, Settings */}
      <div className="flex items-center gap-2">
        {/* Template Picker Popover */}
        <Popover
          id="template-picker-popover"
          isOpen={isTemplateMenuOpen}
          onClose={() => setIsTemplateMenuOpen(false)}
          trigger={
            <Button
              variant={activeTemplate ? 'secondary' : 'ghost'}
              size="md"
              icon={<Layers className="w-4 h-4 text-[var(--text-secondary-color)]" />}
              onClick={() => setIsTemplateMenuOpen(!isTemplateMenuOpen)}
              className="max-w-[180px]"
            >
              <span className="truncate">
                {activeTemplate ? activeTemplate.name : 'Templates'}
              </span>
              <ChevronDown className="w-3.5 h-3.5 opacity-60 shrink-0 ml-0.5" />
            </Button>
          }
        >
          <div className="w-64 p-1.5 space-y-1 text-left">
            <div className="px-2.5 py-1.5 text-[12px] font-semibold text-[var(--text-secondary-color)]">
              Reference Templates
            </div>
            <button
              onClick={() => {
                onSelectTemplate('');
                setIsTemplateMenuOpen(false);
              }}
              className={`w-full px-2.5 py-1.5 rounded-[8px] text-[13px] flex items-center justify-between text-left transition-colors cursor-pointer ${
                !selectedTemplateId
                  ? 'bg-[var(--accent-subtle)] text-[var(--accent)] font-medium'
                  : 'text-[var(--text)] hover:bg-[var(--surface-subtle)]'
              }`}
            >
              <span>None (Auto-layout)</span>
              {!selectedTemplateId && <Check className="w-4 h-4" />}
            </button>
            {templates.map((tpl) => (
              <button
                key={tpl.id}
                onClick={() => {
                  onSelectTemplate(tpl.id);
                  setIsTemplateMenuOpen(false);
                }}
                className={`w-full px-2.5 py-1.5 rounded-[8px] text-[13px] flex items-center justify-between text-left transition-colors cursor-pointer ${
                  selectedTemplateId === tpl.id
                    ? 'bg-[var(--accent-subtle)] text-[var(--accent)] font-medium'
                    : 'text-[var(--text)] hover:bg-[var(--surface-subtle)]'
                }`}
              >
                <div className="truncate pr-2">
                  <div className="truncate">{tpl.name}</div>
                  <div className="text-[12px] text-[var(--text-secondary-color)]">
                    {tpl.source_vendor.toUpperCase()}
                  </div>
                </div>
                {selectedTemplateId === tpl.id && <Check className="w-4 h-4 shrink-0" />}
              </button>
            ))}

            <div className="h-px bg-[var(--separator)] my-1" />

            <div className="px-2.5 py-1 text-[12px] font-semibold text-[var(--text-secondary-color)]">
              Process Capture Workbooks
            </div>
            <a
              href="/api/templates/download-blank?type=xlsx&sample=true"
              download="Process_Capture_Template.xlsx"
              onClick={() => setIsTemplateMenuOpen(false)}
              className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] text-[var(--text)] hover:bg-[var(--surface-subtle)] flex items-center gap-2 cursor-pointer no-underline"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-[var(--success)]" />
              <span>Download Excel Template</span>
            </a>
            <a
              href="/api/templates/download-blank?type=docx&sample=true"
              download="Process_Capture_Template.docx"
              onClick={() => setIsTemplateMenuOpen(false)}
              className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] text-[var(--text)] hover:bg-[var(--surface-subtle)] flex items-center gap-2 cursor-pointer no-underline"
            >
              <Table className="w-3.5 h-3.5 text-[var(--accent)]" />
              <span>Download Word Template</span>
            </a>

            <div className="h-px bg-[var(--separator)] my-1" />

            {activeTemplate && (
              <button
                onClick={() => {
                  setIsTemplateMenuOpen(false);
                  onOpenLaneMapping();
                }}
                className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] text-[var(--text)] hover:bg-[var(--surface-subtle)] flex items-center gap-2 cursor-pointer"
              >
                <GitMerge className="w-3.5 h-3.5 text-[var(--accent)]" />
                <span>Map Swimlanes</span>
              </button>
            )}

            <button
              onClick={() => {
                setIsTemplateMenuOpen(false);
                onOpenTemplateManager();
              }}
              className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] text-[var(--accent)] hover:bg-[var(--accent-subtle)] font-medium flex items-center gap-2 cursor-pointer"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Manage Templates...</span>
            </button>
          </div>
        </Popover>

        {/* Step Builder (No-Code Process Capture) */}
        {onOpenStepBuilder && (
          <Button
            id="step-builder-open-btn"
            variant="ghost"
            size="md"
            icon={<Table className="w-4 h-4 text-[var(--text-secondary-color)]" />}
            onClick={onOpenStepBuilder}
          >
            Step Builder
          </Button>
        )}

        {/* Primary Export Action */}
        <Popover
          id="export-popover"
          isOpen={isExportMenuOpen}
          onClose={() => setIsExportMenuOpen(false)}
          trigger={
            <Button
              variant="primary"
              size="lg"
              icon={<Download className="w-4 h-4" />}
              disabled={!hasDiagram || exportBlocked}
              onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
              title={exportBlocked ? 'Export blocked due to validation errors (see Issues tab)' : undefined}
            >
              Export
            </Button>
          }
        >
          <div className="w-56 p-1.5 space-y-1 text-left">
            <div className="px-2.5 py-1.5 text-[12px] font-semibold text-[var(--text-secondary-color)]">
              Export Diagram
            </div>
            <button
              onClick={() => {
                setIsExportMenuOpen(false);
                onExportBpmn();
              }}
              className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] text-[var(--text)] hover:bg-[var(--surface-subtle)] flex items-center justify-between cursor-pointer"
            >
              <span>BPMN 2.0 XML</span>
              <span className="text-[12px] text-[var(--text-tertiary)]">.bpmn</span>
            </button>
            <button
              onClick={() => {
                setIsExportMenuOpen(false);
                onExportSvg();
              }}
              className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] text-[var(--text)] hover:bg-[var(--surface-subtle)] flex items-center justify-between cursor-pointer"
            >
              <span>Vector Graphic</span>
              <span className="text-[12px] text-[var(--text-tertiary)]">.svg</span>
            </button>
            <button
              onClick={() => {
                setIsExportMenuOpen(false);
                onExportPng();
              }}
              className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] text-[var(--text)] hover:bg-[var(--surface-subtle)] flex items-center justify-between cursor-pointer"
            >
              <span>High-Res Image</span>
              <span className="text-[12px] text-[var(--text-tertiary)]">.png</span>
            </button>
            <div className="h-px bg-[var(--separator)] my-1" />
            <button
              onClick={() => {
                setIsExportMenuOpen(false);
                onExportZip();
              }}
              disabled={isExportingZip}
              className="w-full px-2.5 py-1.5 rounded-[8px] text-[13px] text-[var(--accent)] hover:bg-[var(--accent-subtle)] font-medium flex items-center justify-between cursor-pointer"
            >
              <span>Bulk Bundle (All Formats)</span>
              <span className="text-[12px] text-[var(--accent)]">.zip</span>
            </button>
          </div>
        </Popover>

        {/* Settings Button */}
        <Button
          variant="ghost"
          size="md"
          icon={<SettingsIcon className="w-4 h-4" />}
          onClick={onOpenSettings}
          title="LLM Settings"
          aria-label="Settings"
        >
          <span className="sr-only">Settings</span>
        </Button>
      </div>
    </header>
  );
};
