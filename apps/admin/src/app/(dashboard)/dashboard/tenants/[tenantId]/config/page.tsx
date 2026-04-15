"use client";

import { use } from "react";
import { useTenantConfig, useUpdateAIConfig } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { AIConfig } from "@/lib/api";
import { ApiKeysPanel } from "@/components/domain/api-keys-panel";

const aiSchema = z.object({
  primary_provider: z.string(),
  primary_model: z.string(),
  fallback_provider: z.string(),
  fallback_model: z.string(),
  temperature: z.number().min(0).max(1),
  max_tokens: z.number().min(100).max(8000),
  top_p: z.number().min(0).max(1),
  system_prompt_override: z.string(),
  enable_caching: z.boolean(),
  cost_optimization: z.boolean(),
});

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
      <div className="p-6 flex items-center justify-center h-64">
        <div className="text-muted-foreground text-sm">Loading configuration…</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Configuration</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          AI model, generation parameters, limits and API access
        </p>
      </div>

      <Tabs defaultValue="ai">
        <TabsList>
          <TabsTrigger value="ai">AI Model</TabsTrigger>
          <TabsTrigger value="limits">Limits</TabsTrigger>
          <TabsTrigger value="keys">API Keys</TabsTrigger>
        </TabsList>

        <TabsContent value="ai">
          {cfg && <AIConfigForm tenantId={tenantId} config={cfg.ai_config} />}
        </TabsContent>

        <TabsContent value="limits">
          {cfg && <LimitsPanel config={cfg} />}
        </TabsContent>

        <TabsContent value="keys">
          <ApiKeysPanel tenantId={tenantId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ─── AI Config form ───────────────────────────────────────────

function AIConfigForm({ tenantId, config }: { tenantId: string; config: AIConfig }) {
  const update = useUpdateAIConfig(tenantId);
  const { register, handleSubmit, setValue, formState: { isDirty, isSubmitting } } = useForm({
    resolver: zodResolver(aiSchema),
    defaultValues: config,
  });

  const PROVIDERS = ["vertex_ai", "openai", "anthropic", "lmstudio"];
  const MODELS: Record<string, string[]> = {
    vertex_ai: ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
    openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    anthropic: ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
    lmstudio: ["llama-3.2-3b-instruct", "mistral-7b-instruct"],
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Model Configuration</CardTitle>
        <CardDescription>
          Configure the LLM provider, model, and generation parameters
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit((d) => update.mutateAsync(d))} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Primary Provider</Label>
              <Select
                defaultValue={config.primary_provider}
                onValueChange={(v) => setValue("primary_provider", v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map((p) => (
                    <SelectItem key={p} value={p}>{p}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Primary Model</Label>
              <Input {...register("primary_model")} placeholder="gemini-2.0-flash" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Fallback Provider</Label>
              <Select
                defaultValue={config.fallback_provider}
                onValueChange={(v) => setValue("fallback_provider", v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map((p) => (
                    <SelectItem key={p} value={p}>{p}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Fallback Model</Label>
              <Input {...register("fallback_model")} placeholder="gpt-4o-mini" />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label>Temperature <span className="text-muted-foreground text-xs">(0–1)</span></Label>
              <Input type="number" step="0.05" min="0" max="1" {...register("temperature", { valueAsNumber: true })} />
            </div>
            <div className="space-y-1.5">
              <Label>Max Tokens</Label>
              <Input type="number" min="100" max="8000" {...register("max_tokens", { valueAsNumber: true })} />
            </div>
            <div className="space-y-1.5">
              <Label>Top-P</Label>
              <Input type="number" step="0.05" min="0" max="1" {...register("top_p", { valueAsNumber: true })} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>System Prompt Override</Label>
            <Textarea
              rows={5}
              placeholder="Leave empty to use the default NIA system prompt…"
              {...register("system_prompt_override")}
            />
          </div>

          <div className="flex justify-end pt-2">
            <Button type="submit" disabled={!isDirty} loading={isSubmitting}>
              Save AI Config
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
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
