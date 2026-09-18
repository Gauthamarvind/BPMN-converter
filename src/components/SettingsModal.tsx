import React from 'react';
import { LLMSettings } from '../types';
import { Settings, Cpu, Key, Sliders, Server, Save } from 'lucide-react';

interface SettingsModalProps {
  settings: LLMSettings;
  onSave: (newSettings: LLMSettings) => void;
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  settings,
  onSave,
  isOpen,
  onClose,
}) => {
  const [localSettings, setLocalSettings] = React.useState<LLMSettings>({ ...settings });

  React.useEffect(() => {
    setLocalSettings({ ...settings });
  }, [settings, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(localSettings);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-stone-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="p-4 bg-stone-50 border-b border-stone-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-stone-700" />
            <h3 className="text-sm font-bold text-stone-900">LLM Provider & Model Configuration</h3>
          </div>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-stone-700 text-lg leading-none p-1 font-bold"
          >
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
          {/* Provider Selection */}
          <div>
            <label className="font-semibold text-stone-700 flex items-center gap-1.5 mb-1.5">
              <Cpu className="w-3.5 h-3.5 text-blue-600" />
              Extraction Engine Provider
            </label>
            <select
              value={localSettings.provider}
              onChange={(e) =>
                setLocalSettings({ ...localSettings, provider: e.target.value as any })
              }
              className="w-full p-2 border border-stone-300 rounded-lg text-xs font-medium text-stone-800 bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            >
              <option value="openai_compatible">OpenAI-Compatible (Ollama / Local / vLLM / LM Studio)</option>
              <option value="gemini">Google Gemini</option>
              <option value="anthropic">Anthropic Claude</option>
              <option value="mock">Deterministic Rule Engine (Offline / Standalone)</option>
            </select>
          </div>

          {/* Model Name */}
          <div>
            <label className="font-semibold text-stone-700 flex items-center gap-1.5 mb-1.5">
              <Server className="w-3.5 h-3.5 text-stone-500" />
              Model Name / Tag
            </label>
            <input
              type="text"
              value={localSettings.model}
              onChange={(e) => setLocalSettings({ ...localSettings, model: e.target.value })}
              placeholder="e.g. llama3, mistral, gpt-4o, claude-3-5-sonnet-20241022"
              className="w-full p-2 border border-stone-300 rounded-lg text-xs text-stone-800 bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            />
          </div>

          {/* Base URL (if openai_compatible) */}
          {localSettings.provider === 'openai_compatible' && (
            <div>
              <label className="font-semibold text-stone-700 flex items-center gap-1.5 mb-1.5">
                <Server className="w-3.5 h-3.5 text-stone-500" />
                API Base URL
              </label>
              <input
                type="text"
                value={localSettings.baseUrl}
                onChange={(e) => setLocalSettings({ ...localSettings, baseUrl: e.target.value })}
                placeholder="http://localhost:11434/v1"
                className="w-full p-2 border border-stone-300 rounded-lg text-xs text-stone-800 font-mono bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
              />
              <span className="text-[10px] text-stone-400 mt-1 block">
                Local Ollama uses http://localhost:11434/v1
              </span>
            </div>
          )}

          {/* API Key (Optional / if remote) */}
          {localSettings.provider !== 'mock' && (
            <div>
              <label className="font-semibold text-stone-700 flex items-center gap-1.5 mb-1.5">
                <Key className="w-3.5 h-3.5 text-stone-500" />
                API Key (Optional for local Ollama)
              </label>
              <input
                type="password"
                value={localSettings.apiKey}
                onChange={(e) => setLocalSettings({ ...localSettings, apiKey: e.target.value })}
                placeholder="sk-... or leave blank for local models"
                className="w-full p-2 border border-stone-300 rounded-lg text-xs text-stone-800 bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none font-mono"
              />
            </div>
          )}

          {/* Temperature */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="font-semibold text-stone-700 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-stone-500" />
                Temperature: {localSettings.temperature}
              </label>
              <span className="text-[11px] text-stone-400">Low = strict structured JSON</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="1.0"
              step="0.05"
              value={localSettings.temperature}
              onChange={(e) =>
                setLocalSettings({ ...localSettings, temperature: parseFloat(e.target.value) })
              }
              className="w-full accent-blue-600"
            />
          </div>

          <div className="pt-3 border-t border-stone-200 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-semibold text-stone-600 hover:text-stone-900 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-1.5 shadow-2xs"
            >
              <Save className="w-3.5 h-3.5" />
              Save Configuration
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
