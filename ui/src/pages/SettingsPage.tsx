/**
 * Settings: which model the agents use. A local server (Ollama, LM Studio, llama.cpp,
 * vLLM), Anthropic or OpenAI; the model, picked from the provider's own live list; keys;
 * and a connection test. Saved on this computer by the API, and applied to the next run.
 */
import { useEffect, useMemo, useState } from "react";
import { useLoad } from "../api/hooks";
import {
  type ConnectionResult,
  fetchLLMSettings,
  fetchModels,
  type LLMSettings,
  type LLMSettingsUpdate,
  LOCAL_SERVERS,
  PROVIDER_NAME,
  type ProviderId,
  type ProviderSettings,
  saveLLMSettings,
  testConnection,
} from "../api/settings";
import { Button } from "../components/Button";
import { Icon } from "../components/Icon";
import { PageLoading } from "../components/Loading";
import { ErrorState } from "../components/States";
import { PlainTextField } from "../form/Fields";
import pageStyles from "./pages.module.css";
import styles from "./SettingsPage.module.css";

/** The host part of a local server address, so presets can keep it (e.g. in Docker). */
function presetHost(url: string): string {
  try {
    const host = new URL(url).hostname;
    return host === "host.docker.internal" ? host : "localhost";
  } catch {
    return "localhost";
  }
}

type SourceName = ProviderSettings["model_source"];

function SourceNote({ source, what }: { source: SourceName; what: string }) {
  if (source === "environment") {
    return (
      <p className={styles.source} data-kind="locked">
        <Icon name="lock" size={14} /> {what} is set by an environment variable, which takes priority over
        what you save here.
      </p>
    );
  }
  if (source === "env_file") {
    return (
      <p className={styles.source}>
        <Icon name="info" size={14} /> {what} comes from your .env file. Saving here overrides it.
      </p>
    );
  }
  return null;
}

interface Draft {
  provider: ProviderId;
  localUrl: string;
  models: Record<ProviderId, string>;
  keys: Partial<Record<ProviderId, string>>; // only what the user typed; never filled from the server
  maxCost: string;
}

function draftFrom(settings: LLMSettings): Draft {
  const models = Object.fromEntries(settings.providers.map((p) => [p.id, p.model])) as Record<
    ProviderId,
    string
  >;
  return {
    provider: settings.provider,
    localUrl: settings.local_base_url,
    models,
    keys: {},
    maxCost: String(settings.max_cost_usd),
  };
}

function changes(settings: LLMSettings, draft: Draft): LLMSettingsUpdate {
  const update: LLMSettingsUpdate = {};
  if (draft.provider !== settings.provider) update.provider = draft.provider;
  if (draft.localUrl.trim() !== settings.local_base_url) update.local_base_url = draft.localUrl.trim();
  const models: Partial<Record<ProviderId, string>> = {};
  for (const p of settings.providers) {
    const value = draft.models[p.id]?.trim() ?? "";
    if (value !== p.model) models[p.id] = value === p.default_model ? "" : value;
  }
  if (Object.keys(models).length) update.models = models;
  const keys = Object.fromEntries(Object.entries(draft.keys).filter(([, v]) => v !== undefined));
  if (Object.keys(keys).length) update.keys = keys;
  const cost = Number(draft.maxCost);
  if (draft.maxCost.trim() && Number.isFinite(cost) && cost !== settings.max_cost_usd)
    update.max_cost_usd = cost;
  return update;
}

function ProviderCard({
  provider,
  selected,
  inUse,
  onSelect,
}: {
  provider: ProviderSettings;
  selected: boolean;
  inUse: boolean;
  onSelect: () => void;
}) {
  const ready = !provider.needs_key || provider.key_set;
  return (
    <button type="button" className={styles.providerCard} aria-pressed={selected} onClick={onSelect}>
      <span className={styles.providerHead}>
        <Icon name={provider.on_device ? "device" : "cloud"} size={22} duotone={selected} />
        <span className="title-m">{PROVIDER_NAME[provider.id]}</span>
        {inUse && <span className={styles.inUse}>In use</span>}
      </span>
      <code className={styles.providerModel}>{provider.model}</code>
      <span className={styles.providerNote} data-warn={!ready}>
        {provider.on_device
          ? "Stays on this computer"
          : ready
            ? `Key ${provider.key_hint}`
            : "Needs an API key"}
      </span>
    </button>
  );
}

function ModelPicker({
  provider,
  value,
  onChange,
  localUrl,
}: {
  provider: ProviderSettings;
  value: string;
  onChange: (value: string) => void;
  localUrl: string;
}) {
  const [models, setModels] = useState<string[] | null>(null);
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const listId = `models-${provider.id}`;

  const load = async () => {
    setLoading(true);
    setError(undefined);
    try {
      setModels(await fetchModels(provider.id));
    } catch (err) {
      setModels(null);
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // biome-ignore lint/correctness/useExhaustiveDependencies: reload when the provider or server changes
  useEffect(() => {
    setModels(null);
    if (!provider.needs_key || provider.key_set) void load();
  }, [provider.id, provider.key_set, localUrl]);

  return (
    <div className={styles.modelPicker}>
      <PlainTextField
        label="Model"
        value={value}
        onChange={onChange}
        list={listId}
        support={
          error
            ? undefined
            : models
              ? `${models.length} model${models.length === 1 ? "" : "s"} available. Type to filter, or enter any name. Default: ${provider.default_model}.`
              : `Default: ${provider.default_model}.`
        }
        error={error}
      />
      <datalist id={listId}>
        {(models ?? []).map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>
      <Button
        variant="text"
        size="s"
        icon={loading ? "spinner" : "refresh"}
        onClick={load}
        disabled={loading}
      >
        Refresh list
      </Button>
    </div>
  );
}

export function SettingsPage() {
  const loaded = useLoad(fetchLLMSettings);
  const [settings, setSettings] = useState<LLMSettings>();
  const [draft, setDraft] = useState<Draft>();
  const [focus, setFocus] = useState<ProviderId>("local");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string>();
  const [check, setCheck] = useState<ConnectionResult | "running">();

  useEffect(() => {
    if (loaded.data) {
      setSettings(loaded.data);
      setDraft(draftFrom(loaded.data));
      setFocus(loaded.data.provider);
    }
  }, [loaded.data]);

  const pending = useMemo(() => (settings && draft ? changes(settings, draft) : {}), [settings, draft]);
  const dirty = Object.keys(pending).length > 0;

  if (loaded.loading && !settings) return <PageLoading label="Loading settings" />;
  if (loaded.error || !settings || !draft) {
    return (
      <div className={pageStyles.page}>
        {loaded.error && <ErrorState error={loaded.error} onRetry={loaded.reload} />}
      </div>
    );
  }

  const provider = settings.providers.find((p) => p.id === focus) as ProviderSettings;
  const set = (patch: Partial<Draft>) => {
    setDraft({ ...draft, ...patch });
    setSaved(false);
    setCheck(undefined);
  };

  const save = async () => {
    setSaving(true);
    setSaveError(undefined);
    try {
      const next = await saveLLMSettings(pending);
      setSettings(next);
      setDraft(draftFrom(next));
      setSaved(true);
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const runCheck = async () => {
    if (dirty) await save();
    setCheck("running");
    try {
      setCheck(await testConnection(focus, draft.models[focus]));
    } catch (err) {
      setCheck({
        ok: false,
        provider: focus,
        model: draft.models[focus],
        latency_ms: null,
        message: (err as Error).message,
      });
    }
  };

  return (
    <div className={pageStyles.page}>
      <header className={pageStyles.pageHead}>
        <h1>Settings</h1>
        <p className="body-l muted">
          The model margin's agents use. Saved on this computer and used from the next run on.
        </p>
      </header>

      <section className={styles.panel}>
        <h2 className={styles.panelTitle}>Model</h2>
        <fieldset className={styles.providers}>
          <legend className="visually-hidden">Provider</legend>
          {settings.providers.map((p) => (
            <ProviderCard
              key={p.id}
              provider={{ ...p, model: draft.models[p.id] || p.model }}
              selected={focus === p.id}
              inUse={draft.provider === p.id}
              onSelect={() => {
                setFocus(p.id);
                setCheck(undefined);
              }}
            />
          ))}
        </fieldset>
        <SourceNote source={settings.provider_source} what="The provider" />

        {!provider.on_device && (
          <p className={styles.privacy}>
            <Icon name="cloud" size={18} />
            <span>
              With {PROVIDER_NAME[provider.id]}, agents send their prompts to {PROVIDER_NAME[provider.id]}.
              For the AI Code Detector that means samples of the code it reads. A local server keeps
              everything on this computer.
            </span>
          </p>
        )}

        {draft.provider !== provider.id && (
          <div className={styles.useRow}>
            <span className="body-m muted">
              Runs use {PROVIDER_NAME[draft.provider]}. You can set up {PROVIDER_NAME[provider.id]} without
              switching.
            </span>
            <Button
              variant="tonal"
              size="s"
              icon="check"
              disabled={provider.needs_key && !provider.key_set && !draft.keys[provider.id]}
              onClick={() => set({ provider: provider.id })}
            >
              Use {PROVIDER_NAME[provider.id]} for all runs
            </Button>
          </div>
        )}

        <div className={styles.details}>
          {provider.id === "local" && (
            <>
              <fieldset className={styles.presets}>
                <legend className="visually-hidden">Local server</legend>
                {LOCAL_SERVERS.map((s) => {
                  // keep the host the address already uses: inside Docker that is the
                  // host machine (host.docker.internal), not the container's own localhost
                  const url = s.url.replace("localhost", presetHost(draft.localUrl));
                  return (
                    <button
                      key={s.name}
                      type="button"
                      className={styles.preset}
                      aria-pressed={draft.localUrl.replace(/\/$/, "") === url}
                      onClick={() => set({ localUrl: url })}
                    >
                      {s.name}
                      <span>{s.url.replace("http://localhost", "")}</span>
                    </button>
                  );
                })}
              </fieldset>
              <PlainTextField
                label="Server address"
                type="url"
                value={draft.localUrl}
                onChange={(v) => set({ localUrl: v })}
                support="Any server with an OpenAI-compatible API."
              />
              <SourceNote source={settings.local_base_url_source} what="The address" />
            </>
          )}

          {(provider.needs_key || provider.id === "local") && (
            <div className={styles.keyRow}>
              <PlainTextField
                label={provider.id === "local" ? "API key (only if your server needs one)" : "API key"}
                type="password"
                value={draft.keys[provider.id] ?? ""}
                onChange={(v) => set({ keys: { ...draft.keys, [provider.id]: v } })}
                placeholder={
                  provider.key_set ? `Saved key ${provider.key_hint} · type to replace` : undefined
                }
                support="Kept on this computer. It is never shown again, only its last four characters."
              />
              {provider.key_set && provider.key_source === "saved" && (
                <Button
                  variant="text"
                  size="s"
                  icon="close"
                  onClick={() => set({ keys: { ...draft.keys, [provider.id]: "" } })}
                >
                  Remove saved key
                </Button>
              )}
              <SourceNote source={provider.key_source} what="The key" />
            </div>
          )}

          <ModelPicker
            provider={provider}
            value={draft.models[provider.id] ?? ""}
            onChange={(v) => set({ models: { ...draft.models, [provider.id]: v } })}
            localUrl={settings.local_base_url}
          />
          <SourceNote source={provider.model_source} what="The model" />

          {!provider.on_device && (
            <PlainTextField
              label="Spending limit per run (USD)"
              type="number"
              value={draft.maxCost}
              onChange={(v) => set({ maxCost: v })}
              support="A run stops calling the model once its estimated cost reaches this."
            />
          )}
        </div>

        <div className={styles.actions}>
          <Button
            icon={saving ? "spinner" : "check"}
            onClick={save}
            disabled={!dirty || saving || !settings.saving_enabled}
          >
            {saving ? "Saving" : "Save"}
          </Button>
          <Button
            variant="tonal"
            icon={check === "running" ? "spinner" : "test"}
            onClick={runCheck}
            disabled={check === "running"}
          >
            Test {PROVIDER_NAME[focus]}
          </Button>
          {saved && !dirty && (
            <span className={styles.ok}>
              <Icon name="checkCircle" size={18} fill /> Saved
            </span>
          )}
          {dirty && !saving && <span className="body-m muted">Unsaved changes</span>}
        </div>
        {saveError && (
          <p className={styles.result} data-ok="false" role="alert">
            <Icon name="error" size={18} /> {saveError}
          </p>
        )}
        {check && check !== "running" && (
          <p className={styles.result} data-ok={check.ok} role="status">
            <Icon name={check.ok ? "checkCircle" : "error"} size={18} fill={check.ok} />
            <span>
              <b>
                {check.ok ? `${check.model} works` : `${check.model || PROVIDER_NAME[focus]} did not answer`}
              </b>
              {check.ok && check.latency_ms !== null
                ? ` · ${(check.latency_ms / 1000).toFixed(1)} s · `
                : " · "}
              {check.message}
            </span>
          </p>
        )}
        {!settings.saving_enabled && (
          <p className={styles.source} data-kind="locked">
            <Icon name="lock" size={14} /> Saving is turned off on this server (MARGIN_CONFIG_FILE is empty).
          </p>
        )}
        {settings.settings_file && <p className={styles.file}>Saved in {settings.settings_file}</p>}
      </section>
    </div>
  );
}
