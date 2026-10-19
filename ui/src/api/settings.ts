/** Model settings: read, save, list a provider's models, test a connection. */
import { api, call } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];
export type LLMSettings = Schemas["LLMSettingsView"];
export type ProviderSettings = Schemas["ProviderView"];
export type LLMSettingsUpdate = Schemas["LLMSettingsUpdate"];
export type ConnectionResult = Schemas["ConnectionResult"];
export type ProviderId = ProviderSettings["id"];

export const fetchLLMSettings = () => call(api.GET("/settings/llm"));

export const saveLLMSettings = (update: LLMSettingsUpdate) =>
  call(api.PUT("/settings/llm", { body: update }));

export const fetchModels = (provider: ProviderId) =>
  call(api.GET("/settings/llm/models", { params: { query: { provider } } })).then((r) => r.models);

export const testConnection = (provider: ProviderId, model?: string) =>
  call(api.POST("/settings/llm/test", { body: { provider, model: model || null } }));

/** Well-known local servers and the address each listens on by default. */
export const LOCAL_SERVERS = [
  { name: "Ollama", url: "http://localhost:11434" },
  { name: "LM Studio", url: "http://localhost:1234" },
  { name: "llama.cpp", url: "http://localhost:8080" },
  { name: "vLLM", url: "http://localhost:8000" },
] as const;

export const PROVIDER_NAME: Record<ProviderId, string> = {
  local: "Local",
  anthropic: "Anthropic",
  openai: "OpenAI",
};
