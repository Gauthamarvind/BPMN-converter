import React, { useState } from 'react';
import {
  Plus,
  Trash2,
  Download,
  Play,
  GripVertical,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  AlertCircle,
  CheckCircle,
  FileSpreadsheet,
  Sliders,
} from 'lucide-react';
import { StepBuilderRow, RowValidationErrorItem } from '../../types';
import { Sheet } from '../ui/Sheet';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Input } from '../ui/Field';

export interface StepBuilderSheetProps {
  isOpen: boolean;
  onClose: () => void;
  onConvertToDiagram: (file: File, processName: string) => Promise<void>;
}

const DEFAULT_ROLES = [
  'Employee',
  'Manager',
  'HR',
  'Finance',
  'System',
  'Department Head',
  'Approver',
  'Unassigned',
];

const INITIAL_SAMPLE_STEPS: StepBuilderRow[] = [
  {
    step_id: '1',
    step: 'Submit Leave Request',
    responsible: 'Employee',
    type: 'Task',
    next_step: '2',
    description: 'Employee selects leave dates and submits request in portal',
    system: 'HR Portal',
    duration: '10m',
  },
  {
    step_id: '2',
    step: 'Check Leave Balance',
    responsible: 'HR',
    type: 'Decision',
    if_yes: '3',
    if_no: '8',
    description: 'HR verifies employee has sufficient accrued PTO balance',
    system: 'HRIS',
    duration: '30m',
  },
  {
    step_id: '3',
    step: 'Manager Approval',
    responsible: 'Manager',
    type: 'Decision',
    if_yes: '4',
    if_no: '1',
    description: 'Manager reviews workload coverage and approves or sends back',
    system: 'Email / HR Portal',
    duration: '1d',
  },
  {
    step_id: '4',
    step: 'Record in Payroll',
    responsible: 'Finance',
    type: 'Task',
    parallel_group: 'G1',
    next_step: '6',
    description: 'Payroll adjusts upcoming cycle for approved time-off',
    system: 'Payroll System',
    duration: '1h',
  },
  {
    step_id: '5',
    step: 'Update HR Calendar',
    responsible: 'HR',
    type: 'Task',
    parallel_group: 'G1',
    next_step: '6',
    description: 'HR team publishes employee out-of-office schedule',
    system: 'Shared Calendar',
    duration: '15m',
  },
  {
    step_id: '6',
    step: 'Send Confirmation Email',
    responsible: 'System',
    type: 'Task',
    next_step: '7',
    description: 'Automated service delivers confirmation to employee & manager',
    system: 'Mail Service',
    duration: 'Instant',
  },
  {
    step_id: '7',
    step: 'Archival & Close',
    responsible: 'System',
    type: 'Task',
    next_step: 'END',
    description: 'Request record is marked completed and archived in database',
    system: 'Document Archive',
    duration: 'Instant',
  },
  {
    step_id: '8',
    step: 'Notify Rejection & Close',
    responsible: 'HR',
    type: 'End',
    next_step: 'END',
    description: 'HR informs employee of insufficient balance and terminates request',
    system: 'HRIS',
    duration: '15m',
  },
];

export const StepBuilderSheet: React.FC<StepBuilderSheetProps> = ({
  isOpen,
  onClose,
  onConvertToDiagram,
}) => {
  const [processName, setProcessName] = useState<string>('Employee Leave Request');
  const [roles, setRoles] = useState<string[]>(DEFAULT_ROLES);
  const [newRoleInput, setNewRoleInput] = useState<string>('');
  const [steps, setSteps] = useState<StepBuilderRow[]>(INITIAL_SAMPLE_STEPS);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [validationErrors, setValidationErrors] = useState<RowValidationErrorItem[]>([]);
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);

  const handleAddRow = () => {
    const nextId = String(
      steps.length > 0
        ? Math.max(...steps.map((s) => parseInt(s.step_id, 10) || 0)) + 1
        : 1
    );
    setSteps([
      ...steps,
      {
        step_id: nextId,
        step: '',
        responsible: roles[0] || 'Unassigned',
        type: 'Task',
        if_yes: '',
        if_no: '',
        parallel_group: '',
        next_step: '',
      },
    ]);
  };

  const handleDeleteRow = (index: number) => {
    const updated = steps.filter((_, idx) => idx !== index);
    setSteps(updated);
  };

  const handleUpdateField = (index: number, field: keyof StepBuilderRow, value: any) => {
    const updated = [...steps];
    const item = { ...updated[index], [field]: value };

    // If type changed from Decision to Task/End, clear if_yes and if_no
    if (field === 'type' && value !== 'Decision') {
      item.if_yes = '';
      item.if_no = '';
    }
    updated[index] = item;
    setSteps(updated);
  };

  const handleMoveRow = (index: number, direction: 'up' | 'down') => {
    if (
      (direction === 'up' && index === 0) ||
      (direction === 'down' && index === steps.length - 1)
    ) {
      return;
    }
    const targetIdx = direction === 'up' ? index - 1 : index + 1;
    const updated = [...steps];
    const temp = updated[index];
    updated[index] = updated[targetIdx];
    updated[targetIdx] = temp;
    setSteps(updated);
  };

  const handleAddCustomRole = () => {
    const trimmed = newRoleInput.trim();
    if (trimmed && !roles.includes(trimmed)) {
      setRoles([...roles, trimmed]);
      setNewRoleInput('');
    }
  };

  const handleExportXlsx = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/templates/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          process_name: processName,
          steps: steps,
          roles: roles,
        }),
      });
      if (!res.ok) throw new Error('Failed to generate Excel workbook');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${processName.replace(/[^a-zA-Z0-9_-]/g, '_') || 'Process'}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Export error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateDiagram = async () => {
    setLoading(true);
    setValidationErrors([]);
    try {
      const buildRes = await fetch('/api/templates/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          process_name: processName,
          steps: steps,
          roles: roles,
        }),
      });

      if (!buildRes.ok) {
        throw new Error('Failed to generate workbook payload');
      }

      const blob = await buildRes.blob();
      const fname = `${processName.replace(/[^a-zA-Z0-9_-]/g, '_') || 'Process'}.xlsx`;
      const file = new File([blob], fname, {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });

      await onConvertToDiagram(file, processName);
      onClose();
    } catch (err: any) {
      if (err.row_errors) {
        setValidationErrors(err.row_errors);
      } else {
        alert(err.message || 'Diagram generation failed.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSample = () => {
    setProcessName('Employee Leave Request');
    setSteps(INITIAL_SAMPLE_STEPS);
    setValidationErrors([]);
  };

  return (
    <Sheet
      id="step-builder-sheet"
      isOpen={isOpen}
      onClose={onClose}
      title="Step Builder (No-Code Process Capture)"
      width="w-full sm:max-w-4xl"
    >
      <div className="flex flex-col h-full space-y-4">
        {/* Top Controls Bar */}
        <div className="p-4 bg-[var(--surface-subtle)] rounded-[8px] space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex-1 min-w-[240px]">
              <label className="text-[12px] font-semibold text-[var(--text-secondary-color)] uppercase tracking-wider block mb-1">
                Process Name
              </label>
              <input
                type="text"
                id="step-builder-process-name"
                value={processName}
                onChange={(e) => setProcessName(e.target.value)}
                placeholder="e.g. Employee Leave Request"
                className="w-full px-3 py-1.5 bg-[var(--surface)] border border-[var(--border)] rounded-[6px] text-[13px] font-medium text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
              />
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon={<RotateCcw className="w-3.5 h-3.5" />}
                onClick={handleLoadSample}
              >
                Load Example
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Sliders className="w-3.5 h-3.5" />}
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                {showAdvanced ? 'Hide Advanced' : 'Advanced Columns'}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<FileSpreadsheet className="w-3.5 h-3.5" />}
                onClick={handleExportXlsx}
                isLoading={loading}
              >
                Export .xlsx
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={<Play className="w-3.5 h-3.5" />}
                onClick={handleGenerateDiagram}
                isLoading={loading}
              >
                Generate Diagram
              </Button>
            </div>
          </div>

          {/* Roles Management inline */}
          <div className="pt-2 border-t border-[var(--separator)] flex items-center justify-between text-[12px] gap-2">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-semibold text-[var(--text-secondary-color)]">Roles:</span>
              {roles.map((r, i) => (
                <Badge key={i} variant="neutral" size="sm">
                  {r}
                </Badge>
              ))}
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <input
                type="text"
                placeholder="New role name..."
                value={newRoleInput}
                onChange={(e) => setNewRoleInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddCustomRole()}
                className="px-2 py-1 bg-[var(--surface)] border border-[var(--border)] rounded-[4px] text-[12px] text-[var(--text)] w-32 focus:outline-none focus:border-[var(--accent)]"
              />
              <Button variant="secondary" size="sm" onClick={handleAddCustomRole}>
                + Add Role
              </Button>
            </div>
          </div>
        </div>

        {/* Validation Errors banner */}
        {validationErrors.length > 0 && (
          <div className="p-3 bg-[var(--danger-subtle)] border border-[var(--danger)]/30 rounded-[8px] space-y-1.5">
            <div className="flex items-center gap-2 text-[var(--danger)] font-semibold text-[13px]">
              <AlertCircle className="w-4 h-4" />
              <span>Validation Errors ({validationErrors.length})</span>
            </div>
            <div className="space-y-1 text-[12px] text-[var(--text)]">
              {validationErrors.map((err, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <Badge variant="danger" size="sm">
                    Row {err.row}
                  </Badge>
                  <span>{err.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Steps Table */}
        <div className="flex-1 overflow-x-auto overflow-y-auto border border-[var(--border)] rounded-[8px] bg-[var(--surface)]">
          <table className="w-full text-left border-collapse text-[12px]">
            <thead className="bg-[var(--surface-subtle)] text-[var(--text-secondary-color)] font-semibold sticky top-0 z-10 border-b border-[var(--border)]">
              <tr>
                <th className="py-2 px-2 w-10 text-center">#</th>
                <th className="py-2 px-2 w-16">Step ID</th>
                <th className="py-2 px-3 min-w-[180px]">Step Description</th>
                <th className="py-2 px-2 w-32">Responsible</th>
                <th className="py-2 px-2 w-28">Type</th>
                <th className="py-2 px-2 w-24">If Yes →</th>
                <th className="py-2 px-2 w-24">If No →</th>
                <th className="py-2 px-2 w-24">Parallel Grp</th>
                <th className="py-2 px-2 w-24">Next Step</th>
                {showAdvanced && (
                  <>
                    <th className="py-2 px-2 min-w-[160px]">Description</th>
                    <th className="py-2 px-2 w-28">System/Tool</th>
                    <th className="py-2 px-2 w-20">Duration</th>
                  </>
                )}
                <th className="py-2 px-2 w-20 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {steps.map((row, idx) => {
                const isDecision = row.type === 'Decision';
                return (
                  <tr
                    key={idx}
                    draggable
                    onDragStart={() => setDraggedIdx(idx)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => {
                      if (draggedIdx !== null && draggedIdx !== idx) {
                        const updated = [...steps];
                        const [moved] = updated.splice(draggedIdx, 1);
                        updated.splice(idx, 0, moved);
                        setSteps(updated);
                        setDraggedIdx(null);
                      }
                    }}
                    className={`hover:bg-[var(--surface-subtle)]/50 transition-colors ${
                      isDecision ? 'bg-[var(--accent-subtle)]/20' : ''
                    }`}
                  >
                    {/* Drag & Row index */}
                    <td className="py-2 px-2 text-center text-[var(--text-tertiary)] cursor-grab">
                      <div className="flex items-center justify-center gap-0.5">
                        <GripVertical className="w-3.5 h-3.5 opacity-40" />
                        <span>{idx + 1}</span>
                      </div>
                    </td>

                    {/* Step ID */}
                    <td className="py-2 px-2">
                      <input
                        type="text"
                        value={row.step_id}
                        onChange={(e) => handleUpdateField(idx, 'step_id', e.target.value)}
                        className="w-full px-1.5 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] text-center font-mono text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
                      />
                    </td>

                    {/* Step Name */}
                    <td className="py-2 px-2">
                      <input
                        type="text"
                        value={row.step}
                        onChange={(e) => handleUpdateField(idx, 'step', e.target.value)}
                        placeholder="e.g. Verify application details"
                        className="w-full px-2 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
                      />
                    </td>

                    {/* Responsible dropdown */}
                    <td className="py-2 px-2">
                      <select
                        value={row.responsible}
                        onChange={(e) => handleUpdateField(idx, 'responsible', e.target.value)}
                        className="w-full px-1.5 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
                      >
                        {roles.map((r, rIdx) => (
                          <option key={rIdx} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </td>

                    {/* Type dropdown */}
                    <td className="py-2 px-2">
                      <select
                        value={row.type}
                        onChange={(e) =>
                          handleUpdateField(idx, 'type', e.target.value as 'Task' | 'Decision' | 'End')
                        }
                        className={`w-full px-1.5 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] font-medium focus:outline-none focus:border-[var(--accent)] ${
                          isDecision ? 'text-[var(--accent)]' : 'text-[var(--text)]'
                        }`}
                      >
                        <option value="Task">Task</option>
                        <option value="Decision">Decision</option>
                        <option value="End">End</option>
                      </select>
                    </td>

                    {/* If Yes */}
                    <td className="py-2 px-2">
                      <input
                        type="text"
                        value={row.if_yes || ''}
                        disabled={!isDecision}
                        onChange={(e) => handleUpdateField(idx, 'if_yes', e.target.value)}
                        placeholder={isDecision ? 'Step ID' : '—'}
                        className={`w-full px-1.5 py-1 border rounded text-[12px] text-center font-mono focus:outline-none ${
                          isDecision
                            ? 'bg-[var(--surface)] border-[var(--accent)] text-[var(--accent)] font-semibold'
                            : 'bg-[var(--surface-subtle)] border-transparent text-[var(--text-tertiary)] cursor-not-allowed opacity-50'
                        }`}
                      />
                    </td>

                    {/* If No */}
                    <td className="py-2 px-2">
                      <input
                        type="text"
                        value={row.if_no || ''}
                        disabled={!isDecision}
                        onChange={(e) => handleUpdateField(idx, 'if_no', e.target.value)}
                        placeholder={isDecision ? 'Step ID' : '—'}
                        className={`w-full px-1.5 py-1 border rounded text-[12px] text-center font-mono focus:outline-none ${
                          isDecision
                            ? 'bg-[var(--surface)] border-[var(--accent)] text-[var(--accent)] font-semibold'
                            : 'bg-[var(--surface-subtle)] border-transparent text-[var(--text-tertiary)] cursor-not-allowed opacity-50'
                        }`}
                      />
                    </td>

                    {/* Parallel Group */}
                    <td className="py-2 px-2">
                      <input
                        type="text"
                        value={row.parallel_group || ''}
                        onChange={(e) => handleUpdateField(idx, 'parallel_group', e.target.value)}
                        placeholder="e.g. G1"
                        className="w-full px-1.5 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] text-center font-mono text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
                      />
                    </td>

                    {/* Next Step */}
                    <td className="py-2 px-2">
                      <input
                        type="text"
                        value={row.next_step || ''}
                        onChange={(e) => handleUpdateField(idx, 'next_step', e.target.value)}
                        placeholder="e.g. 2 / END"
                        className="w-full px-1.5 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] text-center font-mono text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
                      />
                    </td>

                    {/* Advanced Columns */}
                    {showAdvanced && (
                      <>
                        <td className="py-2 px-2">
                          <input
                            type="text"
                            value={row.description || ''}
                            onChange={(e) => handleUpdateField(idx, 'description', e.target.value)}
                            placeholder="Optional notes"
                            className="w-full px-1.5 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] text-[var(--text)]"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="text"
                            value={row.system || ''}
                            onChange={(e) => handleUpdateField(idx, 'system', e.target.value)}
                            placeholder="e.g. SAP"
                            className="w-full px-1.5 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] text-[var(--text)]"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="text"
                            value={row.duration || ''}
                            onChange={(e) => handleUpdateField(idx, 'duration', e.target.value)}
                            placeholder="e.g. 1h"
                            className="w-full px-1.5 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[12px] text-center text-[var(--text)]"
                          />
                        </td>
                      </>
                    )}

                    {/* Actions */}
                    <td className="py-2 px-2 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => handleMoveRow(idx, 'up')}
                          disabled={idx === 0}
                          title="Move up"
                          className="p-1 hover:bg-[var(--surface-subtle)] rounded text-[var(--text-secondary-color)] disabled:opacity-30 cursor-pointer"
                        >
                          <ChevronUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleMoveRow(idx, 'down')}
                          disabled={idx === steps.length - 1}
                          title="Move down"
                          className="p-1 hover:bg-[var(--surface-subtle)] rounded text-[var(--text-secondary-color)] disabled:opacity-30 cursor-pointer"
                        >
                          <ChevronDown className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteRow(idx)}
                          title="Delete step"
                          className="p-1 hover:bg-[var(--danger-subtle)] hover:text-[var(--danger)] rounded text-[var(--text-tertiary)] cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Bottom Bar: Add Step & Summary */}
        <div className="flex items-center justify-between pt-1">
          <Button
            variant="secondary"
            size="sm"
            icon={<Plus className="w-4 h-4" />}
            onClick={handleAddRow}
          >
            Add Step
          </Button>

          <span className="text-[12px] text-[var(--text-secondary-color)] font-medium">
            Total Steps: {steps.length} | Roles: {roles.length}
          </span>
        </div>
      </div>
    </Sheet>
  );
};
