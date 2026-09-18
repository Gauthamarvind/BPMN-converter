import React, { useRef, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  X,
  FileText,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  Layers,
  ArrowRight,
  Info,
  ExternalLink,
} from 'lucide-react';
import { FlowNode, ValidationIssue, LintResult, ProcessIR } from '../../types';
import { SegmentedControl } from '../ui/SegmentedControl';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export interface InspectorProps {
  isOpen: boolean;
  onClose: () => void;
  activeTab: 'details' | 'source' | 'issues';
  onTabChange: (tab: 'details' | 'source' | 'issues') => void;
  selectedElement?: FlowNode;
  processIr?: ProcessIR | null;
  validationIssues?: ValidationIssue[];
  lintResult?: LintResult;
  sourceText: string;
  onSelectElementById?: (id: string) => void;
}

export const Inspector: React.FC<InspectorProps> = ({
  isOpen,
  onClose,
  activeTab,
  onTabChange,
  selectedElement,
  processIr,
  validationIssues = [],
  lintResult,
  sourceText,
  onSelectElementById,
}) => {
  const highlightRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to highlighted source snippet in Source tab
  useEffect(() => {
    if (activeTab === 'source' && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [selectedElement, activeTab]);

  if (!isOpen) return null;

  const totalIssuesCount =
    validationIssues.length +
    (lintResult?.warnings?.length || 0) +
    (processIr?.open_questions?.length || 0);

  // Find lane name for selected element
  const getElementLane = (elem?: FlowNode) => {
    if (!elem || !processIr) return 'Default Pool';
    for (const pool of processIr.pools) {
      for (const lane of pool.lanes) {
        if (lane.elementIds.includes(elem.id) || lane.id === elem.laneId) {
          return `${pool.name ? pool.name + ' → ' : ''}${lane.name}`;
        }
      }
    }
    return elem.laneId || 'Default Process';
  };

  // Split source text into lines and find match
  const lines = sourceText.split('\n');
  const snippet = selectedElement?.source_snippet?.toLowerCase().trim();
  const highlightedLineIndex = snippet
    ? lines.findIndex(
        (l) =>
          l.toLowerCase().includes(snippet) ||
          (snippet.length > 20 && l.toLowerCase().includes(snippet.slice(0, 30)))
      )
    : -1;

  return (
    <motion.aside
      initial={{ x: 360, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 360, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="w-[360px] h-full bg-[var(--surface-solid)] border-l border-[var(--separator)] flex flex-col shrink-0 overflow-hidden z-20 select-none shadow-[var(--shadow-popover)]"
    >
      {/* Header with Segmented Tabs and Close */}
      <div className="p-3 border-b border-[var(--separator)] flex items-center justify-between gap-2 shrink-0 bg-[var(--surface)] backdrop-blur-[20px]">
        <SegmentedControl
          id="inspector-tabs"
          size="sm"
          value={activeTab}
          onChange={(tab) => onTabChange(tab as any)}
          options={[
            { id: 'details', label: 'Details' },
            { id: 'source', label: 'Source' },
            {
              id: 'issues',
              label: 'Issues',
              badge: totalIssuesCount > 0 ? totalIssuesCount : undefined,
            },
          ]}
        />
        <button
          onClick={onClose}
          title="Close Inspector (Esc)"
          className="w-7 h-7 rounded-[8px] flex items-center justify-center text-[var(--text-secondary-color)] hover:text-[var(--text)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tab 1: Details */}
      {activeTab === 'details' && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4 text-left">
          {selectedElement ? (
            <div className="space-y-4">
              {/* Element Header */}
              <div>
                <span className="text-[12px] font-semibold text-[var(--accent)] uppercase tracking-wider">
                  {selectedElement.type.replace(/^bpmn:/, '')}
                </span>
                <h3 className="text-[15px] font-semibold text-[var(--text)] mt-0.5 leading-snug">
                  {selectedElement.name || selectedElement.id}
                </h3>
                <span className="text-[12px] text-[var(--text-tertiary)] font-mono block mt-0.5">
                  ID: {selectedElement.id}
                </span>
              </div>

              {/* Lane / Participant */}
              <div className="p-3 bg-[var(--surface-subtle)] rounded-[8px] space-y-1">
                <span className="text-[12px] font-medium text-[var(--text-secondary-color)]">
                  Swimlane / Role
                </span>
                <p className="text-[13px] font-medium text-[var(--text)]">
                  {getElementLane(selectedElement)}
                </p>
              </div>

              {/* Documentation / Description */}
              {selectedElement.documentation && (
                <div className="space-y-1">
                  <span className="text-[12px] font-medium text-[var(--text-secondary-color)]">
                    Documentation
                  </span>
                  <div className="p-3 bg-[var(--surface-subtle)] rounded-[8px] text-[13px] text-[var(--text)] leading-relaxed">
                    {selectedElement.documentation}
                  </div>
                </div>
              )}

              {/* Condition / Expression if Gateway/Flow */}
              {selectedElement.conditionExpression && (
                <div className="space-y-1">
                  <span className="text-[12px] font-medium text-[var(--text-secondary-color)]">
                    Branch Condition
                  </span>
                  <div className="p-2.5 bg-[var(--surface-subtle)] rounded-[8px] text-[12px] font-mono text-[var(--text)]">
                    {selectedElement.conditionExpression}
                  </div>
                </div>
              )}

              {/* Linked Source Snippet */}
              {selectedElement.source_snippet && (
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] font-medium text-[var(--text-secondary-color)]">
                      Matched Source Sentence
                    </span>
                    <button
                      onClick={() => onTabChange('source')}
                      className="text-[12px] text-[var(--accent)] hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      <span>View in text</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="p-3 border-l-2 border-[var(--accent)] bg-[var(--accent-subtle)] rounded-r-[8px] text-[13px] text-[var(--text)] leading-relaxed italic">
                    "{selectedElement.source_snippet}"
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-[var(--text-secondary-color)]">
              <Layers className="w-8 h-8 opacity-40 mb-2" />
              <p className="text-[13px] font-medium text-[var(--text)]">
                No element selected
              </p>
              <p className="text-[12px] text-[var(--text-secondary-color)] mt-1">
                Click any task, gateway, or flow on the canvas to inspect its parameters.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Source (Traceability) */}
      {activeTab === 'source' && (
        <div className="flex-1 overflow-y-auto p-4 space-y-3 text-left">
          <div className="flex items-center justify-between pb-2 border-b border-[var(--separator)]">
            <span className="text-[12px] font-semibold text-[var(--text-secondary-color)]">
              Source Document Transcript
            </span>
            {selectedElement?.source_snippet && (
              <Badge variant="accent" size="sm">
                Sentence linked
              </Badge>
            )}
          </div>

          <div className="space-y-1 font-sans text-[13px] leading-relaxed select-text">
            {lines.map((line, idx) => {
              const isHighlighted = idx === highlightedLineIndex;
              return (
                <div
                  key={idx}
                  ref={isHighlighted ? highlightRef : null}
                  className={`p-1.5 rounded-[6px] transition-colors ${
                    isHighlighted
                      ? 'bg-[var(--accent-subtle)] text-[var(--accent)] font-medium border-l-2 border-[var(--accent)]'
                      : 'text-[var(--text)] hover:bg-[var(--surface-subtle)]'
                  }`}
                >
                  <span className="text-[12px] text-[var(--text-tertiary)] mr-2 select-none font-mono">
                    {idx + 1}
                  </span>
                  <span>{line || ' '}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 3: Issues (Validation, Linting, Questions) */}
      {activeTab === 'issues' && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4 text-left">
          {totalIssuesCount === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-[var(--text-secondary-color)]">
              <CheckCircle className="w-8 h-8 text-[var(--success)] mb-2" />
              <p className="text-[13px] font-medium text-[var(--text)]">
                All checks passed
              </p>
              <p className="text-[12px] text-[var(--text-secondary-color)] mt-1">
                Process graph is fully connected and valid BPMN 2.0.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Validation & Lint Findings */}
              {validationIssues.length > 0 && (
                <div className="space-y-2">
                  <span className="text-[12px] font-semibold text-[var(--text-secondary-color)] uppercase tracking-wider">
                    Graph Validation ({validationIssues.length})
                  </span>
                  {validationIssues.map((issue, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-[var(--surface-subtle)] rounded-[8px] border border-[var(--separator)] space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <Badge
                          variant={
                            issue.severity === 'ERROR'
                              ? 'danger'
                              : issue.severity === 'WARNING'
                              ? 'neutral'
                              : 'accent'
                          }
                          size="sm"
                        >
                          {issue.severity}
                        </Badge>
                        {issue.auto_fixed && (
                          <span className="text-[12px] text-[var(--success)] font-medium">
                            Auto-repaired
                          </span>
                        )}
                      </div>
                      <p className="text-[13px] text-[var(--text)] leading-snug">
                        {issue.message}
                      </p>
                      {issue.element_id && onSelectElementById && (
                        <button
                          onClick={() => onSelectElementById(issue.element_id!)}
                          className="text-[12px] text-[var(--accent)] hover:underline flex items-center gap-1 cursor-pointer font-medium pt-1"
                        >
                          <span>Highlight element</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Profile Lint Warnings */}
              {lintResult?.warnings && lintResult.warnings.length > 0 && (
                <div className="space-y-2">
                  <span className="text-[12px] font-semibold text-[var(--text-secondary-color)] uppercase tracking-wider">
                    {lintResult.display_name} Lint Findings ({lintResult.warnings.length})
                  </span>
                  {lintResult.warnings.map((w, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-[var(--surface-subtle)] rounded-[8px] border border-[var(--separator)] space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <Badge variant="neutral" size="sm">
                          {w.code}
                        </Badge>
                      </div>
                      <p className="text-[13px] text-[var(--text)] leading-snug">
                        {w.message}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Open Ambiguity Questions */}
              {processIr?.open_questions && processIr.open_questions.length > 0 && (
                <div className="space-y-2">
                  <span className="text-[12px] font-semibold text-[var(--text-secondary-color)] uppercase tracking-wider">
                    Open Questions ({processIr.open_questions.length})
                  </span>
                  {processIr.open_questions.map((q, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-[var(--surface-subtle)] rounded-[8px] border border-[var(--separator)] space-y-1"
                    >
                      <div className="flex items-center gap-1.5 text-[var(--accent)]">
                        <HelpCircle className="w-3.5 h-3.5" />
                        <span className="text-[12px] font-medium">Question for Process Owner</span>
                      </div>
                      <p className="text-[13px] text-[var(--text)] leading-snug">
                        {q}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </motion.aside>
  );
};
