import React, { useState, useEffect } from 'react';
import { GitMerge, Check, AlertCircle, ArrowRight } from 'lucide-react';
import { AvailableLane, LaneMappingItem } from '../../types';
import { Sheet } from '../ui/Sheet';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Select } from '../ui/Field';

export interface LaneMappingSheetProps {
  isOpen: boolean;
  onClose: () => void;
  templateId: string;
  templateName: string;
  actors: string[];
  currentMapping: Record<string, string>;
  onApplyMapping: (mapping: Record<string, string>) => void;
}

export const LaneMappingSheet: React.FC<LaneMappingSheetProps> = ({
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
    <Sheet
      id="lane-mapping-sheet"
      isOpen={isOpen}
      onClose={onClose}
      title="Swimlane Alignment"
      subtitle={`Map extracted process actors to swimlanes in "${templateName}".`}
      footer={
        <>
          <Button variant="ghost" size="md" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="md" onClick={handleApply}>
            Apply Mappings
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-left">
        {error && (
          <div className="p-3 bg-[var(--danger-subtle)] text-[var(--danger)] text-[12px] rounded-[8px] flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-[var(--text-secondary-color)] space-y-2">
            <span className="w-6 h-6 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            <span className="text-[13px]">Matching swimlanes via semantic heuristic...</span>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-[13px] text-[var(--text-secondary-color)]">
              Tasks and events performed by each actor will be placed inside their assigned
              template swimlane.
            </p>

            <div className="space-y-2.5">
              {effectiveActors.map((actor) => {
                const conf = autoConfidence[actor];
                const selectedLane = mappingState[actor] || '';

                return (
                  <div
                    key={actor}
                    className="p-3 bg-[var(--surface-subtle)] rounded-[12px] space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] font-semibold text-[var(--text)]">
                        {actor}
                      </span>
                      {conf !== undefined && (
                        <Badge
                          variant={conf > 0.8 ? 'success' : 'neutral'}
                          size="sm"
                        >
                          {Math.round(conf * 100)}% match
                        </Badge>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <ArrowRight className="w-3.5 h-3.5 text-[var(--text-tertiary)] shrink-0" />
                      <select
                        value={selectedLane}
                        onChange={(e) => handleSelectLane(actor, e.target.value)}
                        className="h-8 w-full px-2.5 text-[13px] bg-[var(--surface-solid)] text-[var(--text)] border border-[var(--separator-strong)] rounded-[8px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                      >
                        <option value="">(Auto-create swimlane)</option>
                        {availableLanes.map((lane) => (
                          <option key={lane.id} value={lane.id}>
                            {lane.pool_name ? `${lane.pool_name} → ` : ''}
                            {lane.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Sheet>
  );
};
