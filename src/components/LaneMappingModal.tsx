import React, { useState, useEffect } from 'react';
import { X, GitMerge, Check, AlertCircle, ArrowRight, RefreshCw } from 'lucide-react';
import { AvailableLane, LaneMappingItem } from '../types';
import { InfoTooltip } from './InfoTooltip';

interface LaneMappingModalProps {
  isOpen: boolean;
  onClose: () => void;
  templateId: string;
  templateName: string;
  actors: string[];
  currentMapping: Record<string, string>;
  onApplyMapping: (mapping: Record<string, string>) => void;
}

export const LaneMappingModal: React.FC<LaneMappingModalProps> = ({
  isOpen,
  onClose,
  templateId,
  templateName,
  actors,
  currentMapping,
  onApplyMapping,
}) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [availableLanes, setAvailableLanes] = useState<AvailableLane[]>([]);
  const [mappingState, setMappingState] = useState<Record<string, string>>({});
  const [autoConfidence, setAutoConfidence] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!isOpen || !templateId) return;

    setLoading(true);
    setError(null);

    fetch('/api/templates/map-lanes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_id: templateId,
        actors: actors.length > 0 ? actors : ['Initiator', 'Approver', 'System'],
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to map lanes: ${res.statusText}`);
        return res.json();
      })
      .then((data) => {
        setAvailableLanes(data.available_lanes || []);

        const initial: Record<string, string> = { ...currentMapping };
        const conf: Record<string, number> = {};

        if (data.mappings) {
          data.mappings.forEach((m: LaneMappingItem) => {
            if (!initial[m.actor] && m.lane_id) {
              initial[m.actor] = m.lane_id;
            }
            if (m.confidence !== undefined) {
              conf[m.actor] = m.confidence;
            }
          });
        }
        setMappingState(initial);
        setAutoConfidence(conf);
      })
      .catch((err) => {
        console.error('Error mapping lanes:', err);
        setError(err.message || 'Failed to calculate lane mappings.');
      })
      .finally(() => setLoading(false));
  }, [isOpen, templateId, actors]);

  if (!isOpen) return null;

  const handleSelectLane = (actor: string, laneId: string) => {
    setMappingState((prev) => ({
      ...prev,
      [actor]: laneId,
    }));
  };

  const handleApply = () => {
    onApplyMapping(mappingState);
    onClose();
  };

  const effectiveActors = actors.length > 0 ? actors : Object.keys(mappingState);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        id="lane-mapping-modal"
        className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-stone-200 overflow-hidden flex flex-col max-h-[85vh]"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-stone-200 flex items-center justify-between bg-stone-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center border border-blue-200">
              <GitMerge className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h3 className="text-sm font-bold text-stone-900">Swimlane Role Mapping</h3>
                <InfoTooltip
                  title="Swimlane Role Alignment"
                  content="Maps detected actors or departmental roles from your process text to specific swimlanes inside the selected BPMN reference template."
                />
              </div>
              <p className="text-xs text-stone-500">
                Template: <span className="font-semibold text-stone-700">{templateName}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-stone-400 hover:text-stone-700 hover:bg-stone-200 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
              <span>{error}</span>
            </div>
          )}

          <div className="bg-stone-50 border border-stone-200/80 rounded-lg p-3 text-xs text-stone-600">
            <p className="leading-relaxed">
              Verify how actors discovered in your workflow route to the reference swimlanes. Unmapped
              actors will be assigned to the template's default primary lane.
            </p>
          </div>

          {loading ? (
            <div className="py-8 flex flex-col items-center justify-center gap-2 text-stone-400">
              <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
              <span className="text-xs">Analyzing template swimlanes...</span>
            </div>
          ) : effectiveActors.length === 0 ? (
            <div className="py-6 text-center text-xs text-stone-500">
              No actors detected yet. Generate a process to view actor swimlane mappings.
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-12 gap-2 text-[11px] font-semibold text-stone-500 uppercase tracking-wider px-1">
                <div className="col-span-5 flex items-center gap-1">
                  Extracted Actor
                  <InfoTooltip content="The performer, department, or system role detected in your source text or document." />
                </div>
                <div className="col-span-1 text-center"></div>
                <div className="col-span-6 flex items-center gap-1">
                  Target Swimlane
                  <InfoTooltip content="The physical BPMN swimlane in the reference template where this actor's tasks will be placed." />
                </div>
              </div>

              {effectiveActors.map((actor) => {
                const mappedLaneId = mappingState[actor] || '';
                const conf = autoConfidence[actor];

                return (
                  <div
                    key={actor}
                    className="grid grid-cols-12 gap-2 items-center p-2.5 bg-stone-50/50 hover:bg-stone-50 border border-stone-200 rounded-lg text-xs"
                  >
                    <div className="col-span-5 font-medium text-stone-800 truncate" title={actor}>
                      {actor}
                      {conf !== undefined && conf > 0.8 && (
                        <span className="ml-1.5 inline-block text-[9px] font-semibold text-emerald-700 bg-emerald-100/70 px-1.5 py-0.2 rounded">
                          {Math.round(conf * 100)}% match
                        </span>
                      )}
                    </div>

                    <div className="col-span-1 flex justify-center text-stone-400">
                      <ArrowRight className="w-3.5 h-3.5" />
                    </div>

                    <div className="col-span-6">
                      <select
                        value={mappedLaneId}
                        onChange={(e) => handleSelectLane(actor, e.target.value)}
                        className="w-full px-2 py-1.5 text-xs bg-white border border-stone-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium text-stone-800"
                      >
                        <option value="">-- Unassigned (Auto-place) --</option>
                        {availableLanes.map((lane) => (
                          <option key={lane.id} value={lane.id}>
                            {lane.name || lane.id} {lane.pool_name ? `(${lane.pool_name})` : ''}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-stone-200 bg-stone-50/80 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setMappingState({})}
            className="text-xs text-stone-500 hover:text-stone-800 font-medium transition-colors"
          >
            Reset Mappings
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-200/70 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              id="save-lane-mappings-btn"
              onClick={handleApply}
              className="px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" />
              Confirm Mappings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
