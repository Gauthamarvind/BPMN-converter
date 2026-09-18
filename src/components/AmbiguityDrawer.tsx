import React from 'react';
import { HelpCircle, AlertTriangle, CheckCircle, ArrowRight, ShieldAlert } from 'lucide-react';
import { ValidationIssue } from '../types';

interface AmbiguityDrawerProps {
  openQuestions?: string[];
  assumptions?: string[];
  validationIssues?: ValidationIssue[];
  isOpen: boolean;
  onToggle: () => void;
}

export const AmbiguityDrawer: React.FC<AmbiguityDrawerProps> = ({
  openQuestions = [],
  assumptions = [],
  validationIssues = [],
  isOpen,
  onToggle,
}) => {
  const totalItems = openQuestions.length + assumptions.length + validationIssues.length;

  return (
    <div className="relative">
      {/* Drawer Toggle Button */}
      <button
        id="ambiguity-toggle-btn"
        onClick={onToggle}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all ${
          totalItems > 0
            ? 'bg-amber-50 text-amber-900 border-amber-200 hover:bg-amber-100'
            : 'bg-stone-50 text-stone-600 border-stone-200 hover:bg-stone-100'
        }`}
      >
        <HelpCircle className="w-3.5 h-3.5 text-amber-600" />
        <span>Ambiguities & Questions</span>
        {totalItems > 0 && (
          <span className="px-1.5 py-0.2 bg-amber-500 text-white rounded-full text-[10px] font-bold">
            {totalItems}
          </span>
        )}
      </button>

      {/* Floating Flyout Drawer */}
      {isOpen && (
        <>
          <div className="fixed inset-0 z-30" onClick={onToggle} />
          <div className="absolute right-0 mt-2 w-96 max-h-[80vh] bg-white border border-stone-200 rounded-2xl shadow-xl z-40 flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-3.5 bg-stone-50 border-b border-stone-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-amber-600" />
                <h3 className="text-xs font-bold text-stone-900 uppercase tracking-wider">
                  Ambiguity & Validation Report
                </h3>
              </div>
              <button
                onClick={onToggle}
                className="text-stone-400 hover:text-stone-700 text-sm font-bold"
              >
                &times;
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-4 text-xs">
              {/* Open Questions (Missing roles, ambiguous conditions) */}
              <div>
                <h4 className="font-bold text-stone-700 mb-2 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                  Open Questions for Process Owner ({openQuestions.length})
                </h4>
                {openQuestions.length === 0 ? (
                  <p className="text-stone-400 italic">No unresolved ambiguities flagged.</p>
                ) : (
                  <div className="space-y-2">
                    {openQuestions.map((q, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 bg-amber-50/70 border border-amber-200 rounded-lg text-amber-950 flex items-start gap-2"
                      >
                        <span className="w-4 h-4 bg-amber-200 text-amber-900 rounded-full flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                          ?
                        </span>
                        <div>
                          <p className="leading-snug">{q}</p>
                          <span className="text-[10px] text-amber-700 font-semibold block mt-1">
                            Recommendation: Confirm branch rule with business team.
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Automatic Pipeline Repairs */}
              <div>
                <h4 className="font-bold text-stone-700 mb-2 flex items-center gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                  Automatic Graph Repairs ({validationIssues.filter((i) => i.auto_fixed).length})
                </h4>
                {validationIssues.filter((i) => i.auto_fixed).length === 0 ? (
                  <p className="text-stone-400 italic">Graph was well-formed without automated repairs.</p>
                ) : (
                  <div className="space-y-1.5">
                    {validationIssues
                      .filter((i) => i.auto_fixed)
                      .map((iss, idx) => (
                        <div
                          key={idx}
                          className="p-2 bg-emerald-50/60 border border-emerald-200 rounded-lg text-emerald-900 flex items-start gap-2 text-[11px]"
                        >
                          <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                          <span>{iss.message}</span>
                        </div>
                      ))}
                  </div>
                )}
              </div>

              {/* Documented Assumptions */}
              <div>
                <h4 className="font-bold text-stone-700 mb-2 flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-blue-600" />
                  Documented Assumptions ({assumptions.length})
                </h4>
                {assumptions.length === 0 ? (
                  <p className="text-stone-400 italic">No additional assumptions recorded.</p>
                ) : (
                  <div className="space-y-1.5">
                    {assumptions.map((a, idx) => (
                      <div
                        key={idx}
                        className="p-2 bg-blue-50/50 border border-blue-100 rounded-lg text-blue-900 text-[11px]"
                      >
                        • {a}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
