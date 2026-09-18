import React, { useState, useEffect } from 'react';
import { LLMSettings } from '../../types';
import { Sheet } from '../ui/Sheet';
import { Input, Select } from '../ui/Field';
import { Button } from '../ui/Button';

export interface SettingsSheetProps {
  isOpen: boolean;
  onClose: () => void;
  settings: LLMSettings;
  onSave: (newSettings: LLMSettings) => void;
}

export const SettingsSheet: React.FC<SettingsSheetProps> = ({
  isOpen,
  onClose,
  settings,
  onSave,
}) => {
  const [localSettings, setLocalSettings] = useState<LLMSettings>({ ...settings });

  useEffect(() => {
    setLocalSettings({ ...settings });
  }, [settings, isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(localSettings);
    onClose();
  };

  return (
    <Sheet
      id="settings-sheet"
      isOpen={isOpen}
      onClose={onClose}
      title="Extraction Engine Settings"
      subtitle="Configure the language model provider, local endpoints, and temperature."
      footer={
        <>
          <Button variant="ghost" size="md" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="md" onClick={handleSubmit}>
            Save Changes
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5 text-left">
        {/* Provider */}
        <Select
          label="Model Provider"
          caption="Choose local Ollama/vLLM, managed cloud endpoints, or deterministic offline rules."
          value={localSettings.provider}
          onChange={(e) =>
            setLocalSettings({ ...localSettings, provider: e.target.value as any })
          }
          options={[
            { value: 'openai_compatible', label: 'OpenAI-Compatible (Ollama / Local / vLLM)' },
            { value: 'gemini', label: 'Google Gemini' },
            { value: 'anthropic', label: 'Anthropic Claude' },
            { value: 'mock', label: 'Deterministic Rule Engine (Offline)' },
          ]}
        />

        {/* Model Name */}
        <Input
          label="Model Name / Tag"
          caption="For Ollama: llama3, mistral, qwen2.5. For cloud: gpt-4o, claude-3-5-sonnet."
          value={localSettings.model}
          onChange={(e) => setLocalSettings({ ...localSettings, model: e.target.value })}
          placeholder="llama3"
        />

        {/* Base URL */}
        {localSettings.provider === 'openai_compatible' && (
          <Input
            label="API Base URL"
            caption="Local Ollama endpoint defaults to http://localhost:11434/v1."
            value={localSettings.baseUrl}
            onChange={(e) => setLocalSettings({ ...localSettings, baseUrl: e.target.value })}
            placeholder="http://localhost:11434/v1"
          />
        )}

        {/* API Key */}
        {localSettings.provider !== 'mock' && (
          <Input
            type="password"
            label="API Key"
            caption="Optional for local models; required for Gemini or Claude cloud extraction."
            value={localSettings.apiKey}
            onChange={(e) => setLocalSettings({ ...localSettings, apiKey: e.target.value })}
            placeholder={
              localSettings.provider === 'openai_compatible'
                ? 'Optional for local Ollama'
                : 'sk-...'
            }
          />
        )}

        {/* Temperature */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-[13px] font-medium text-[var(--text)]">
              Temperature ({localSettings.temperature})
            </label>
            <span className="text-[12px] text-[var(--text-secondary-color)]">
              {localSettings.temperature <= 0.2 ? 'Deterministic' : 'Creative'}
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={localSettings.temperature}
            onChange={(e) =>
              setLocalSettings({ ...localSettings, temperature: parseFloat(e.target.value) })
            }
            className="w-full accent-[var(--accent)] cursor-pointer"
          />
          <p className="text-[12px] text-[var(--text-secondary-color)]">
            Lower values (0.05–0.2) ensure strictly structured JSON schema adherence.
          </p>
        </div>
      </form>
    </Sheet>
  );
};
