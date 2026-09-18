import React, { useState } from 'react';
import { ProfileMetadata, LintResult } from '../types';
import { ShieldCheck, AlertCircle, Info, ChevronDown, Check, ExternalLink } from 'lucide-react';
import { InfoTooltip } from './InfoTooltip';

interface ProfileSelectorProps {
  profiles: ProfileMetadata[];
  selectedProfileId: string;
  onSelectProfile: (id: string) => void;
  lintResult?: LintResult;
}

export const ProfileSelector: React.FC<ProfileSelectorProps> = ({
  profiles,
  selectedProfileId,
  onSelectProfile,
  lintResult,
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [showAssumptionsModal, setShowAssumptionsModal] = useState(false);

  const activeProfile = profiles.find((p) => p.id === selectedProfileId) || profiles[0];

  return (
    <div className="relative flex items-center gap-1.5">
      {/* Target Tool Profile Dropdown */}
      <div className="relative flex items-center gap-1">
        <button
          id="profile-dropdown-btn"
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-2 px-3 py-1.5 bg-white hover:bg-stone-50 border border-stone-200 rounded-lg text-xs font-semibold text-stone-800 shadow-2xs transition-all cursor-pointer"
        >
          <span className="text-stone-400 font-normal">Profile:</span>
          <span>{activeProfile?.displayName || selectedProfileId}</span>
          <ChevronDown className="w-3.5 h-3.5 text-stone-400 ml-1" />
        </button>
        <InfoTooltip
          title="Vendor Target Profile"
          content="Selects the target BPMN 2.0 tool dialect (Camunda 8, SAP Signavio, Celonis, ARIS, or Generic). Adjusts XML namespaces, attributes, and linting rules to guarantee clean import."
        />

        {dropdownOpen && (
          <>
            <div
              className="fixed inset-0 z-30"
              onClick={() => setDropdownOpen(false)}
            />
            <div className="absolute left-0 top-full mt-1.5 w-72 bg-white border border-stone-200 rounded-xl shadow-lg z-40 py-1 overflow-hidden">
              <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-stone-400 border-b border-stone-100 flex items-center justify-between">
                <span>Target BPMN 2.0 Tool</span>
                <InfoTooltip content="Each vendor profile defines specific visual extensions, layout rules, and required BPMN metadata." />
              </div>
              {profiles.map((p) => {
                const isSelected = p.id === selectedProfileId;
                return (
                  <button
                    key={p.id}
                    onClick={() => {
                      onSelectProfile(p.id);
                      setDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 flex items-start justify-between gap-2 hover:bg-stone-50 transition-colors ${
                      isSelected ? 'bg-blue-50/50 text-blue-900' : 'text-stone-700'
                    }`}
                  >
                    <div>
                      <p className="text-xs font-semibold">{p.displayName}</p>
                      <p className="text-[11px] text-stone-500 line-clamp-1">{p.description}</p>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />}
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Assumptions & Compliance Pill */}
      <div className="flex items-center gap-1">
        <button
          id="profile-assumptions-btn"
          onClick={() => setShowAssumptionsModal(true)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 bg-stone-100 hover:bg-stone-200/80 text-stone-700 text-xs font-medium rounded-lg transition-colors cursor-pointer"
          title="View profile assumptions & rules"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-stone-600" />
          <span>Rules</span>
          {lintResult?.warnings && lintResult.warnings.length > 0 && (
            <span className="px-1.5 py-0.2 bg-amber-100 text-amber-800 text-[10px] font-bold rounded-full">
              {lintResult.warnings.length}
            </span>
          )}
        </button>
        <InfoTooltip
          title="Profile Rules & Assumptions"
          content="Lists modeling rules, auto-corrections, and assumptions applied for the selected vendor profile."
        />
      </div>

      {/* Modal for Assumptions and Linter warnings */}
      {showAssumptionsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full max-h-[85vh] flex flex-col shadow-xl border border-stone-200 overflow-hidden">
            <div className="p-4 bg-stone-50 border-b border-stone-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-stone-900">
                  {activeProfile?.displayName} Export Profile
                </h3>
                <p className="text-xs text-stone-500">{activeProfile?.description}</p>
              </div>
              <button
                onClick={() => setShowAssumptionsModal(false)}
                className="text-stone-400 hover:text-stone-700 text-lg leading-none p-1 font-bold"
              >
                &times;
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-4 text-xs">
              {/* Profile Assumptions */}
              <div>
                <h4 className="font-bold text-stone-800 uppercase tracking-wider text-[11px] mb-2 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  Tool Assumptions & Formatting Rules
                </h4>
                <div className="space-y-1.5">
                  {(activeProfile?.assumptions || []).map((assump, i) => (
                    <div key={i} className="p-2 bg-stone-50 rounded-lg border border-stone-200/80 text-stone-700">
                      • {assump}
                    </div>
                  ))}
                </div>
              </div>

              {/* Linter Warnings */}
              {lintResult && (
                <div>
                  <h4 className="font-bold text-stone-800 uppercase tracking-wider text-[11px] mb-2 flex items-center gap-1.5">
                    <AlertCircle className="w-4 h-4 text-amber-600" />
                    Profile Linter Report
                  </h4>
                  {lintResult.warnings.length === 0 ? (
                    <div className="p-2.5 bg-emerald-50 text-emerald-800 rounded-lg border border-emerald-200 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" />
                      <span>100% compliant with {activeProfile?.displayName} specifications.</span>
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {lintResult.warnings.map((w, idx) => (
                        <div
                          key={idx}
                          className="p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-amber-900 flex items-start gap-2"
                        >
                          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-mono font-bold text-[10px] text-amber-700 uppercase block">
                              [{w.code}] {w.element_id ? `on ${w.element_id}` : ''}
                            </span>
                            <span>{w.message}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="p-3 bg-stone-50 border-t border-stone-200 flex justify-end">
              <button
                onClick={() => setShowAssumptionsModal(false)}
                className="px-3 py-1.5 text-xs font-semibold bg-stone-900 text-white hover:bg-stone-800 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
