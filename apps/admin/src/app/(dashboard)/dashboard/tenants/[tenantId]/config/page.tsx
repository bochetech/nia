"use client";

import { use, useState } from "react";
import { useTenantConfig, useUpdateAIConfig } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { AIConfig } from "@/lib/api";
import { ApiKeysPanel } from "@/components/domain/api-keys-panel";
import { Eye, EyeOff, Cpu, Zap, SlidersHorizontal, Server } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Providers catalog ──────────────────────────────────────────

const PROVIDERS = [
  { key: "lmstudio",      label: "LM Studio",            hint: "Local OpenAI-compatible server" },
  { key: "openai_compat", label: "OpenAI-compatible API", hint: "Any server with /v1/chat/completions" },
  { key: "openai",        label: "OpenAI",                hint: "api.openai.com" },
  { key: "anthropic",     label: "Anthropic",             hint: "api.anthropic.com" },
  { key: "vertex_ai",     label: "Google Vertex AI",      hint: "GCP Vertex AI" },
] as const;

const PROVIDER_DEFAULTS: Record<string, { url: string; keyRequired: boolean }> = {
  lmstudio:      { url: "http://localhost:1234", keyRequired: false },
  openai_compat: { url: "",                      keyRequired: false },
  openai:        { url: "https://api.openai.com", keyRequired: true },
  anthropic:     { url: "https://api.anthropic.com", keyRequired: true },
  vertex_ai:     { url: "",                      keyRequired: false },
};

// ─── Zod schema ─────────────────────────────────────────────────

const aiSchema = z.object({
  primary_provider:     z.string().min(1),
  primary_model:        z.string(),
  primary_endpoint_url: z.string(),
  primary_api_key:      z.string(),
  fallback_provider:    z.string().min(1),
  fallback_model:       z.string(),
  fallback_endpoint_url: z.string(),
  fallback_api_key:     z.string(),
  temperature:          z.number().min(0).max(1),
  max_tokens:           z.number().min(100).max(32000),
  top_p:                z.number().min(0).max(1),
  system_prompt_override: z.string(),
  enable_caching:       z.boolean(),
  cost_optimization:    z.boolean(),
  input_cost_per_million:  z.number().min(0),
  output_cost_per_million: z.number().min(0),
});

// ─── Page ────────────────────────────────────────────────────────

export default function TenantConfigPage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  const { data, isLoading } = useTenantConfig(tenantId);
  const cfg = data?.data;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
        <span className="ml-2 text-sm text-muted-foreground">Loading configuration…</span>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Configuration</h1>
          <p className="text-sm text-muted-foreground mt-1">
            AI model connections, generation parameters and API access
          </p>
        </div>

        <Tabs defaultValue="ai">
          <TabsList>
            <TabsTrigger value="ai" className="text-xs">AI Model</TabsTrigger>
            <TabsTrigger value="limits" className="text-xs">Limits</TabsTrigger>
            <TabsTrigger value="keys" className="text-xs">API Keys</TabsTrigger>
          </TabsList>

          <TabsContent value="ai" className="mt-4">
            {cfg && <AIConfigForm tenantId={tenantId} config={cfg.ai_config} />}
          </TabsContent>

          <TabsContent value="limits" className="mt-4">
            {cfg && <LimitsPanel config={cfg} />}
          </TabsContent>

          <TabsContent value="keys" className="mt-4">
            <ApiKeysPanel tenantId={tenantId} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

// ─── API Key field with show/hide toggle ──────────────────────

function ApiKeyField({
  value,
  onChange,
  placeholder = "sk-…",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <Input
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pr-10 font-mono text-sm"
        autoComplete="off"
      />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
        tabIndex={-1}
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

// ─── Connection block (primary or fallback) ────────────────────

function ConnectionBlock({
  title,
  icon,
  providerField,
  modelField,
  urlField,
  keyField,
  providerValue,
  onProviderChange,
  register,
  setValue,
  watch,
  badge,
}: {
  title: string;
  icon: React.ReactNode;
  providerField: string;
  modelField: string;
  urlField: string;
  keyField: string;
  providerValue: string;
  onProviderChange: (v: string) => void;
  register: any;
  setValue: any;
  watch: any;
  badge?: string;
}) {
  const providerInfo = PROVIDERS.find((p) => p.key === providerValue);
  const defaults = PROVIDER_DEFAULTS[providerValue] ?? { url: "", keyRequired: false };

  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <span className="text-slate-500">{icon}</span>
          <span className="font-semibold text-sm text-slate-800">{title}</span>
          {badge && (
            <Badge variant="secondary" className="text-[10px] h-4 px-1.5">{badge}</Badge>
          )}
        </div>
        {providerInfo && (
          <span className="text-xs text-muted-foreground">{providerInfo.hint}</span>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Provider */}
        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-slate-700">Provider type</Label>
          <Select
            value={providerValue}
            onValueChange={(v) => {
              onProviderChange(v);
              // Auto-fill URL default if field is blank
              const currentUrl = watch(urlField);
              if (!currentUrl) {
                setValue(urlField, PROVIDER_DEFAULTS[v]?.url ?? "");
              }
            }}
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROVIDERS.map((p) => (
                <SelectItem key={p.key} value={p.key} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span>{p.label}</span>
                    <span className="text-xs text-muted-foreground">{p.hint}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Endpoint URL */}
        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-slate-700">
            Endpoint URL
            <span className="ml-1.5 text-slate-400 font-normal">
              {defaults.url ? `default: ${defaults.url}` : "required"}
            </span>
          </Label>
          <Input
            {...register(urlField)}
            placeholder={defaults.url || "https://…"}
            className="font-mono text-sm h-9"
          />
        </div>

        {/* Model + API key side by side */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-slate-700">
              Model
              <span className="ml-1.5 text-slate-400 font-normal">as reported by the API</span>
            </Label>
            <Input
              {...register(modelField)}
              placeholder="e.g. google/gemma-4-e4b"
              className="font-mono text-sm h-9"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-slate-700">
              API Key
              {!defaults.keyRequired && (
                <span className="ml-1.5 text-slate-400 font-normal">optional</span>
              )}
            </Label>
            <ApiKeyField
              value={watch(keyField) ?? ""}
              onChange={(v) => setValue(keyField, v)}
              placeholder={defaults.keyRequired ? "Required" : "Leave blank if not needed"}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── AI Config form ───────────────────────────────────────────

function AIConfigForm({ tenantId, config }: { tenantId: string; config: AIConfig }) {
  const update = useUpdateAIConfig(tenantId);
  const { register, handleSubmit, setValue, watch, control, formState: { isDirty, isSubmitting } } = useForm({
    resolver: zodResolver(aiSchema),
    defaultValues: {
      ...config,
      primary_endpoint_url:  config.primary_endpoint_url  ?? "",
      primary_api_key:       config.primary_api_key       ?? "",
      fallback_endpoint_url: config.fallback_endpoint_url ?? "",
      fallback_api_key:      config.fallback_api_key      ?? "",
      input_cost_per_million:  config.input_cost_per_million  ?? 0.15,
      output_cost_per_million: config.output_cost_per_million ?? 0.60,
    },
  });

  const primaryProvider  = watch("primary_provider");
  const fallbackProvider = watch("fallback_provider");

  return (
    <form onSubmit={handleSubmit((d) => update.mutateAsync(d))} className="space-y-5">

      {/* ── Primary connection ─────────────────────── */}
      <ConnectionBlock
        title="Primary Connection"
        icon={<Server className="h-4 w-4" />}
        badge="active"
        providerField="primary_provider"
        modelField="primary_model"
        urlField="primary_endpoint_url"
        keyField="primary_api_key"
        providerValue={primaryProvider}
        onProviderChange={(v) => setValue("primary_provider", v, { shouldDirty: true })}
        register={register}
        setValue={setValue}
        watch={watch}
      />

      {/* ── Fallback connection ────────────────────── */}
      <ConnectionBlock
        title="Fallback Connection"
        icon={<Zap className="h-4 w-4" />}
        providerField="fallback_provider"
        modelField="fallback_model"
        urlField="fallback_endpoint_url"
        keyField="fallback_api_key"
        providerValue={fallbackProvider}
        onProviderChange={(v) => setValue("fallback_provider", v, { shouldDirty: true })}
        register={register}
        setValue={setValue}
        watch={watch}
      />

      {/* ── Generation parameters ──────────────────── */}
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-200">
          <SlidersHorizontal className="h-4 w-4 text-slate-500" />
          <span className="font-semibold text-sm text-slate-800">Generation Parameters</span>
        </div>
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-slate-700">
                Temperature
                <span className="ml-1.5 text-slate-400 font-normal">0 – 1</span>
              </Label>
              <Input
                type="number" step="0.05" min="0" max="1"
                {...register("temperature", { valueAsNumber: true })}
                className="h-9 text-sm"
              />
              <p className="text-[11px] text-slate-400">0 = precise · 1 = creative</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-slate-700">Max Tokens</Label>
              <Input
                type="number" min="100" max="32000"
                {...register("max_tokens", { valueAsNumber: true })}
                className="h-9 text-sm"
              />
              <p className="text-[11px] text-slate-400">Max length of each reply</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-slate-700">
                Top-P
                <span className="ml-1.5 text-slate-400 font-normal">nucleus</span>
              </Label>
              <Input
                type="number" step="0.05" min="0" max="1"
                {...register("top_p", { valueAsNumber: true })}
                className="h-9 text-sm"
              />
              <p className="text-[11px] text-slate-400">Token probability cutoff</p>
            </div>
          </div>

          {/* Cost per million tokens */}
          <div className="grid grid-cols-2 gap-4 pt-1">
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-slate-700">
                Input cost
                <span className="ml-1.5 text-slate-400 font-normal">USD / 1M tokens</span>
              </Label>
              <Input
                type="number" step="0.01" min="0"
                {...register("input_cost_per_million", { valueAsNumber: true })}
                className="h-9 text-sm"
                placeholder="0.15"
              />
              <p className="text-[11px] text-slate-400">Used to estimate conversation cost</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-slate-700">
                Output cost
                <span className="ml-1.5 text-slate-400 font-normal">USD / 1M tokens</span>
              </Label>
              <Input
                type="number" step="0.01" min="0"
                {...register("output_cost_per_million", { valueAsNumber: true })}
                className="h-9 text-sm"
                placeholder="0.60"
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── System prompt ──────────────────────────── */}
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-200">
          <Cpu className="h-4 w-4 text-slate-500" />
          <span className="font-semibold text-sm text-slate-800">System Prompt Override</span>
          <span className="text-xs text-slate-400 ml-1">optional</span>
        </div>
        <div className="p-4">
          <Textarea
            rows={5}
            placeholder="Leave empty to use the default NIA system prompt. Write a custom system prompt here to give the bot a specific personality, restrictions, or business context…"
            {...register("system_prompt_override")}
            className="text-sm resize-none"
          />
          <p className="text-[11px] text-slate-400 mt-2">
            When set, this replaces the built-in NIA prompt entirely. Use <code className="bg-slate-100 px-1 rounded">{"{{tenant_name}}"}</code> as a variable.
          </p>
        </div>
      </div>

      {/* ── Save ───────────────────────────────────── */}
      <div className="flex justify-end">
        <Button
          type="submit"
          disabled={!isDirty}
          loading={isSubmitting}
          className="px-6"
        >
          Save Configuration
        </Button>
      </div>
    </form>
  );
}

// ─── Limits panel (read-only for now) ───────────────────────────

function LimitsPanel({ config }: { config: any }) {
  const lim = config.limits_config ?? {};
  const rag = config.rag_config ?? {};

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Conversation Limits</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            {[
              ["Max Conversations / Month", lim.max_conversations_per_month ?? "Unlimited"],
              ["Max Tokens / Session", lim.max_tokens_per_session ?? "Unlimited"],
              ["Handoff Enabled", lim.handoff_enabled ? "Yes" : "No"],
              ["RAG Top-K Chunks", rag.top_k ?? 8],
              ["RAG Min Confidence", rag.min_confidence ?? 0.5],
            ].map(([k, v]) => (
              <div key={String(k)}>
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="font-medium mt-0.5">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
