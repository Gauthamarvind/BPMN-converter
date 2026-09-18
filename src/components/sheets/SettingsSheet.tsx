import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { LLMSettings, ServerConfig, LLMPingResult } from '../../types';
import { Sheet } from '../ui/Sheet';
import { Input, Select } from '../ui/Field';
import { Button } from '../ui/Button';

export interface SettingsSheetProps {
  isOpen: boolean;
  onClose: () => void;
  settings: LLMSettings;
  serverConfig?: ServerConfig | null;
  onSave: (newSettings: LLMSettings) => void;
}

const PROVIDER_OPTIONS = [
  { value: '', label: 'Server default (from .env)' },
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'anthropic', label: 'Anthropic Claude' },
  { value: 'openai_compatible', label: 'OpenAI-compatible (OpenAI, Ollama, vLLM, Groq, Mistral…)' },
  { value: 'mock', label: 'Rule engine only (no model, testing)' },
];

const MODEL_HINTS: Record<string, string> = {
  gemini: 'e.g. gemini-2.5-flash',
  anthropic: 'e.g. claude-sonnet-4-5',
  openai_compatible: 'e.g. gpt-4o-mini, llama3.1, mistral',
};

export const SettingsSheet: React.FC<SettingsSheetProps> = ({
  isOpen,
  onClose,
  settings,
  serverConfig,
  onSave,
}) => {
  const [localSettings, setLocalSettings] = useState<LLMSettings>({ ...settings });
  const [ping, setPing] = useState<LLMPingResult | null>(null);
  const [isPinging, setIsPinging] = useState(false);

  useEffect(() => {
    setLocalSettings({ ...settings });
    setPing(null);
  }, [settings, isOpen]);

  const usingServerDefault = !localSettings.provider;
  const serverSummary = serverConfig
    ? `${serverConfig.active_provider} · ${serverConfig.active_model}${
        serverConfig.api_key_set ? ` · key ${serverConfig.api_key_hint || 'set'}` : ' · no API key'
      }`
    : 'loading…';

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    onSave(localSettings);
    onClose();
  };

  const testConnection = async () => {
    setIsPinging(true);
    setPing(null);
    try {
      const res = await fetch('/api/llm/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: localSettings.provider || undefined,
          model: localSettings.model || undefined,
          base_url:
            localSettings.provider === 'openai_compatible' && localSettings.baseUrl
              ? localSettings.baseUrl
              : undefined,
          api_key: localSettings.apiKey || undefined,
        }),
      });
      const data: LLMPingResult = await res.json();
      setPing(data);
    } catch (err) {
      setPing({ ok: false, kind: 'NetworkError', error: err instanceof Error ? err.message : String(err) });
    } finally {
      setIsPinging(false);
    }
  };

  return (
    <Sheet
      id="settings-sheet"
      isOpen={isOpen}
      onClose={onClose}
      title="Model settings"
      subtitle="Which language model turns text into a process. Structured templates never need one."
      footer={
        <>
          <Button variant="ghost" size="md" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="md" onClick={() => handleSubmit()}>
            Save
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5 text-left">
        {/* What the server is configured with */}
        <div className="p-3 rounded-[12px] bg-[var(--surface-subtle)] text-[13px] space-y-0.5">
          <div className="font-medium text-[var(--text)]">Server configuration (.env)</div>
          <div className="text-[var(--text-secondary-color)] break-all">{serverSummary}</div>
          {serverConfig && !serverConfig.api_key_set && serverConfig.active_provider !== 'ollama' && serverConfig.active_provider !== 'mock' && (
            <div className="text-[var(--danger)] pt-1">
              No API key in .env — set LLM_API_KEY and restart, or enter a key below for this session.
            </div>
          )}
          {serverConfig && serverConfig.client_llm_overrides === false && (
            <div className="text-[var(--text-secondary-color)] pt-1">
              This deployment uses the server's model for everyone; provider, model, endpoint and key
              overrides entered here are ignored (only "Rule engine" still applies).
            </div>
          )}
        </div>

        <Select
          label="Provider"
          caption={
            usingServerDefault
              ? 'Requests use the server configuration above.'
              : 'Overrides the server configuration for this browser. The key is kept only for this session.'
          }
          value={localSettings.provider}
          onChange={(e) => {
            const provider = e.target.value as LLMSettings['provider'];
            setLocalSettings({
              ...localSettings,
              provider,
              // A base URL only applies to OpenAI-compatible endpoints; never carry an
              // Ollama address over to Gemini or Anthropic.
              baseUrl: provider === 'openai_compatible' ? localSettings.baseUrl : '',
            });
            setPing(null);
          }}
          options={PROVIDER_OPTIONS}
        />

        {!usingServerDefault && localSettings.provider !== 'mock' && (
          <>
            <Input
              label="Model"
              caption={MODEL_HINTS[localSettings.provider] || 'Model name as your provider lists it.'}
              value={localSettings.model}
              onChange={(e) => setLocalSettings({ ...localSettings, model: e.target.value })}
              placeholder={MODEL_HINTS[localSettings.provider]?.replace('e.g. ', '') || 'model name'}
            />

            {localSettings.provider === 'openai_compatible' && (
              <Input
                label="Base URL"
                caption="Leave empty for a local Ollama at http://localhost:11434/v1. For hosted services paste their API base URL."
                value={localSettings.baseUrl}
                onChange={(e) => setLocalSettings({ ...localSettings, baseUrl: e.target.value })}
                placeholder="http://localhost:11434/v1"
              />
            )}

            <Input
              type="password"
              label="API key"
              caption={
                localSettings.provider === 'openai_compatible'
                  ? 'Not needed for a local Ollama. Required for OpenAI, Groq, Mistral and similar.'
                  : 'Required. Stored in memory for this session only — never saved or sent anywhere except the provider.'
              }
              value={localSettings.apiKey}
              onChange={(e) => setLocalSettings({ ...localSettings, apiKey: e.target.value })}
              placeholder={localSettings.provider === 'openai_compatible' ? 'optional for local models' : 'paste your key'}
              autoComplete="off"
            />
          </>
        )}

        {/* Connection test */}
        <div className="flex items-center gap-3 pt-1">
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={testConnection}
            isLoading={isPinging}
            disabled={isPinging || localSettings.provider === 'mock'}
          >
            Test connection
          </Button>
          {isPinging && (
            <span className="inline-flex items-center gap-1.5 text-[13px] text-[var(--text-secondary-color)]">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Contacting model…
            </span>
          )}
          {!isPinging && ping && ping.ok && (
            <span className="inline-flex items-center gap-1.5 text-[13px] text-[var(--success)]">
              <CheckCircle2 className="w-4 h-4" />
              {ping.provider} · {ping.model} answered in {ping.latency_ms} ms
            </span>
          )}
        </div>
        {!isPinging && ping && !ping.ok && (
          <div className="p-3 rounded-[12px] bg-[var(--danger-subtle)] text-[13px] space-y-1">
            <div className="inline-flex items-center gap-1.5 text-[var(--danger)] font-medium">
              <XCircle className="w-4 h-4" /> {ping.kind || 'Connection failed'}
            </div>
            <div className="text-[var(--text)] break-words">{ping.error}</div>
          </div>
        )}
      </form>
    </Sheet>
  );
};
