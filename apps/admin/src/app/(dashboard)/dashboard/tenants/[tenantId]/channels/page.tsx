"use client";

import { use, useState } from "react";
import {
  useTenantConfig,
  useUpdateTelegramConfig,
  useUpdateTeamsConfig,
  useUpdatePaymentConfig,
  useUpdateUIConfig,
  useUpdateChatwootConfig,
} from "@/hooks/use-api";
import type { TelegramConfig, TeamsConfig, PaymentConfig, UIConfig, ChatwootConfig, ChatwootHandoffAgent } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { useForm, Controller } from "react-hook-form";
import { Save, MessageCircle, Send, CreditCard, Blocks, Copy, Check, Plus, Trash2, Users, Webhook } from "lucide-react";
import { toast } from "sonner";

export default function ChannelsPage({
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
        <span className="ml-2 text-sm text-muted-foreground">Loading channels…</span>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Channels</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure Widget, Telegram, Microsoft Teams, Chatwoot and Payment integrations
          </p>
        </div>

        <Tabs defaultValue="widget">
          <TabsList className="grid grid-cols-5 w-full">
            <TabsTrigger value="widget" className="text-xs">
              <MessageCircle className="h-3.5 w-3.5 mr-1.5" />
              Widget
            </TabsTrigger>
            <TabsTrigger value="telegram" className="text-xs">
              <Send className="h-3.5 w-3.5 mr-1.5" />
              Telegram
            </TabsTrigger>
            <TabsTrigger value="teams" className="text-xs">
              <Blocks className="h-3.5 w-3.5 mr-1.5" />
              Teams
            </TabsTrigger>
            <TabsTrigger value="chatwoot" className="text-xs">
              <Users className="h-3.5 w-3.5 mr-1.5" />
              Chatwoot
            </TabsTrigger>
            <TabsTrigger value="payment" className="text-xs">
              <CreditCard className="h-3.5 w-3.5 mr-1.5" />
              Payment
            </TabsTrigger>
          </TabsList>

          <TabsContent value="widget">
            {cfg ? <WidgetTab tenantId={tenantId} uiConfig={cfg.ui_config} /> : null}
          </TabsContent>
          <TabsContent value="telegram">
            {cfg ? <TelegramTab tenantId={tenantId} config={cfg.telegram_config} /> : null}
          </TabsContent>
          <TabsContent value="teams">
            {cfg ? <TeamsTab tenantId={tenantId} config={cfg.teams_config} /> : null}
          </TabsContent>
          <TabsContent value="chatwoot">
            {cfg ? (
              <ChatwootTab
                tenantId={tenantId}
                config={cfg.chatwoot_config ?? {
                  enabled: false, instance_url: "", account_id: 0, bot_inbox_id: 0,
                  api_access_token: "", webhook_hmac_token: "",
                  handoff_enabled: false, handoff_agents: [], handoff_bot_agent_id: null,
                }}
              />
            ) : null}
          </TabsContent>
          <TabsContent value="payment">
            {cfg ? <PaymentTab tenantId={tenantId} config={cfg.payment_config} /> : null}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

// ─── Copy button helper ────────────────────────────────────────

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      title="Copy to clipboard"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

// ─── Chatwoot tab ──────────────────────────────────────────────

const DEFAULT_CHATWOOT_CONFIG: ChatwootConfig = {
  enabled: false,
  instance_url: "",
  account_id: 0,
  bot_inbox_id: 0,
  api_access_token: "",
  webhook_hmac_token: "",
  handoff_enabled: false,
  handoff_agents: [],
  handoff_bot_agent_id: null,
};

function ChatwootTab({ tenantId, config }: { tenantId: string; config: ChatwootConfig }) {
  const update = useUpdateChatwootConfig(tenantId);
  const { register, handleSubmit, control, watch, setValue, formState: { isDirty, isSubmitting } } = useForm<ChatwootConfig>({
    defaultValues: { ...DEFAULT_CHATWOOT_CONFIG, ...config },
  });

  const handoffEnabled = watch("handoff_enabled");
  const handoffAgents = watch("handoff_agents") ?? [];

  // Public URL of the handoff service — must be reachable by Chatwoot
  const handoffBaseUrl = (process.env.NEXT_PUBLIC_HANDOFF_URL ?? "").replace(/\/$/, "");
  const webhookUrl = handoffBaseUrl
    ? `${handoffBaseUrl}/webhooks/chatwoot/${tenantId}`
    : null;

  function addAgent() {
    setValue("handoff_agents", [
      ...handoffAgents,
      { label: "", inbox_id: 0, team_id: null, assignee_id: null, fsm_trigger_state: "" },
    ], { shouldDirty: true });
  }

  function removeAgent(idx: number) {
    setValue(
      "handoff_agents",
      handoffAgents.filter((_, i) => i !== idx),
      { shouldDirty: true },
    );
  }

  return (
    <form onSubmit={handleSubmit((d) => update.mutateAsync(d))} className="mt-4 space-y-4">

      {/* ── Webhook URL card (read-only, prominent) ── */}
      <Card className="border-primary/30 bg-violet-50/40">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2 text-violet-800">
            <Webhook className="h-4 w-4" />
            Webhook URL
          </CardTitle>
          <CardDescription>
            Copy this URL and paste it in your Chatwoot instance under{" "}
            <strong>Settings → Integrations → Webhooks</strong>. Enable the{" "}
            <code className="text-xs bg-violet-100 px-1 rounded">message_created</code> event.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {webhookUrl ? (
            <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-white px-3 py-2">
              <code className="text-xs font-mono text-slate-700 flex-1 break-all">{webhookUrl}</code>
              <CopyButton value={webhookUrl} />
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-primary/30 bg-white px-3 py-2.5 text-xs text-muted-foreground">
              Set <code className="font-mono bg-muted px-1 rounded">NEXT_PUBLIC_HANDOFF_URL</code> in your{" "}
              <code className="font-mono bg-muted px-1 rounded">.env.local</code> to generate this URL.
              <div className="mt-1 font-mono text-[11px] text-slate-400">
                Example: NEXT_PUBLIC_HANDOFF_URL=https://handoff.yourcompany.com
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Connection settings ── */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Users className="h-4 w-4 text-violet-500" />
              Chatwoot Connection
            </CardTitle>
            <Controller
              control={control}
              name="enabled"
              render={({ field }) => (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-muted-foreground">Enabled</span>
                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                </div>
              )}
            />
          </div>
          <CardDescription>
            Connect NIA to a Chatwoot inbox. NIA will respond to incoming messages automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Instance URL */}
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">
              Chatwoot Instance URL
              <span className="ml-1 text-muted-foreground font-normal">
                (cloud: https://app.chatwoot.com — self-hosted: your domain)
              </span>
            </Label>
            <Input
              placeholder="https://app.chatwoot.com"
              className="font-mono text-xs"
              {...register("instance_url")}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Account ID */}
            <div className="space-y-1.5">
              <Label className="text-xs font-medium">
                Account ID
                <span className="ml-1 text-muted-foreground font-normal">
                  (Settings → Account)
                </span>
              </Label>
              <Input
                type="number"
                min="1"
                placeholder="1"
                className="font-mono"
                {...register("account_id", { valueAsNumber: true })}
              />
            </div>

            {/* Bot Inbox ID */}
            <div className="space-y-1.5">
              <Label className="text-xs font-medium">
                Bot Inbox ID
                <span className="ml-1 text-muted-foreground font-normal">
                  (Settings → Inboxes)
                </span>
              </Label>
              <Input
                type="number"
                min="1"
                placeholder="5"
                className="font-mono"
                {...register("bot_inbox_id", { valueAsNumber: true })}
              />
            </div>
          </div>

          {/* API Access Token */}
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">
              API Access Token
              <span className="ml-1 text-muted-foreground font-normal">
                (Profile → Access Token — needs Agent role)
              </span>
            </Label>
            <Input
              type="password"
              placeholder="••••••••••••••••"
              className="font-mono text-xs"
              {...register("api_access_token")}
            />
          </div>

          {/* Webhook HMAC token */}
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">
              Webhook HMAC Token
              <span className="ml-1 text-muted-foreground font-normal">
                (Settings → Integrations → Webhooks → HMAC Token)
              </span>
            </Label>
            <Input
              type="password"
              placeholder="••••••••••••••••"
              className="font-mono text-xs"
              {...register("webhook_hmac_token")}
            />
            <p className="text-[11px] text-muted-foreground">
              Used to verify that webhook calls genuinely come from your Chatwoot instance. Leave empty to skip verification (not recommended in production).
            </p>
          </div>
        </CardContent>
      </Card>

      {/* ── Handoff settings ── */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <Users className="h-4 w-4 text-amber-500" />
              Human Handoff
            </CardTitle>
            <Controller
              control={control}
              name="handoff_enabled"
              render={({ field }) => (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-muted-foreground">Enabled</span>
                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                </div>
              )}
            />
          </div>
          <CardDescription>
            When handoff is triggered, NIA pauses and reassigns the conversation to a human agent group in Chatwoot.
          </CardDescription>
        </CardHeader>

        {handoffEnabled && (
          <CardContent className="space-y-4">
            {/* Bot agent ID */}
            <div className="space-y-1.5">
              <Label className="text-xs font-medium">
                Bot Agent ID
                <span className="ml-1 text-muted-foreground font-normal">
                  (Chatwoot agent ID that represents NIA — optional)
                </span>
              </Label>
              <Input
                type="number"
                min="1"
                placeholder="12"
                className="font-mono"
                {...register("handoff_bot_agent_id", { valueAsNumber: true, setValueAs: v => v === 0 ? null : v })}
              />
              <p className="text-[11px] text-muted-foreground">
                When NIA is in control the conversation is assigned to this agent. On handoff it gets reassigned to the human group.
              </p>
            </div>

            {/* Agent groups */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-medium">Agent Groups</Label>
                <Button type="button" size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={addAgent}>
                  <Plus className="h-3 w-3" />
                  Add group
                </Button>
              </div>

              {handoffAgents.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border py-6 text-center">
                  <Users className="h-6 w-6 text-slate-300 mx-auto mb-2" />
                  <p className="text-xs text-muted-foreground">
                    No agent groups yet — add one to enable routing.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {handoffAgents.map((agent, idx) => (
                    <div key={idx} className="rounded-xl border border-border p-4 space-y-3 bg-muted/50 relative">
                      <div className="flex items-center justify-between">
                        <Badge variant="secondary" className="text-[10px]">Group {idx + 1}</Badge>
                        <button
                          type="button"
                          onClick={() => removeAgent(idx)}
                          className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <Label className="text-xs">Label</Label>
                          <Input
                            placeholder="Technical Support"
                            className="h-8 text-xs"
                            {...register(`handoff_agents.${idx}.label`)}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs">
                            FSM Trigger State
                            <span className="ml-1 text-[10px] text-muted-foreground">(empty = default)</span>
                          </Label>
                          <Input
                            placeholder="handoff_support"
                            className="h-8 text-xs font-mono"
                            {...register(`handoff_agents.${idx}.fsm_trigger_state`)}
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-3">
                        <div className="space-y-1.5">
                          <Label className="text-xs">
                            Inbox ID <span className="text-red-400">*</span>
                          </Label>
                          <Input
                            type="number"
                            min="1"
                            placeholder="7"
                            className="h-8 font-mono"
                            {...register(`handoff_agents.${idx}.inbox_id`, { valueAsNumber: true })}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs">
                            Team ID <span className="text-muted-foreground text-[10px]">(opt)</span>
                          </Label>
                          <Input
                            type="number"
                            min="1"
                            placeholder="3"
                            className="h-8 font-mono"
                            {...register(`handoff_agents.${idx}.team_id`, {
                              valueAsNumber: true,
                              setValueAs: v => v === 0 || v === "" ? null : Number(v),
                            })}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs">
                            Assignee ID <span className="text-muted-foreground text-[10px]">(opt)</span>
                          </Label>
                          <Input
                            type="number"
                            min="1"
                            placeholder="15"
                            className="h-8 font-mono"
                            {...register(`handoff_agents.${idx}.assignee_id`, {
                              valueAsNumber: true,
                              setValueAs: v => v === 0 || v === "" ? null : Number(v),
                            })}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <p className="text-[11px] text-muted-foreground">
                When handoff is triggered, NIA selects the group whose <strong>FSM Trigger State</strong> matches the current FSM state. If none match, it uses the first group.
              </p>
            </div>
          </CardContent>
        )}
      </Card>

      <div className="flex justify-end">
        <Button type="submit" loading={isSubmitting}>
          <Save className="h-3.5 w-3.5 mr-1" />
          Save Chatwoot Config
        </Button>
      </div>
    </form>
  );
}

// ─── Widget tab ────────────────────────────────────────────────

function WidgetTab({ tenantId, uiConfig }: { tenantId: string; uiConfig: UIConfig }) {
  const update = useUpdateUIConfig(tenantId);
  const { register, handleSubmit, watch, formState: { isDirty, isSubmitting } } = useForm({
    defaultValues: uiConfig,
  });

  const primaryColor = watch("primary_color") ?? "#007AFF";
  const chatTitle = watch("chat_title") ?? "NIA Assistant";
  const welcomeMsg = watch("welcome_message") ?? "Hi! How can I help you today?";

  return (
    <div className="space-y-4 mt-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Live Preview</div>
          <div className="rounded-2xl border shadow-lg overflow-hidden bg-white max-w-[260px]">
            <div className="px-4 py-3 text-white text-sm font-semibold" style={{ backgroundColor: primaryColor }}>
              {chatTitle}
            </div>
            <div className="bg-gray-50 p-3 min-h-[140px] space-y-2">
              <div className="flex justify-start">
                <div className="bg-white rounded-2xl rounded-tl-sm px-3 py-2 text-xs shadow-sm max-w-[80%]">{welcomeMsg}</div>
              </div>
              <div className="flex justify-end">
                <div className="rounded-2xl rounded-tr-sm px-3 py-2 text-xs text-white max-w-[80%]" style={{ backgroundColor: primaryColor }}>
                  Hello! I need help.
                </div>
              </div>
            </div>
            <div className="border-t px-3 py-2 flex items-center gap-2 bg-white">
              <div className="flex-1 h-6 rounded-full bg-gray-100 text-xs px-3 text-muted-foreground flex items-center">
                {uiConfig.input_placeholder ?? "Type a message…"}
              </div>
              <div className="h-6 w-6 rounded-full flex items-center justify-center" style={{ backgroundColor: primaryColor }}>
                <Send className="h-3 w-3 text-white" />
              </div>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit((d) => update.mutateAsync(d))} className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Chat Title</Label>
            <Input {...register("chat_title")} className="h-8 text-sm" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Welcome Message</Label>
            <Input {...register("welcome_message")} className="h-8 text-sm" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Primary Color</Label>
            <div className="flex gap-2">
              <input type="color" className="h-8 w-12 rounded border border-input p-1 cursor-pointer" {...register("primary_color")} />
              <Input {...register("primary_color")} className="h-8 text-xs font-mono flex-1" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Input Placeholder</Label>
            <Input {...register("input_placeholder")} className="h-8 text-sm" />
          </div>
          <div className="pt-1">
            <Button type="submit" size="sm" disabled={!isDirty} loading={isSubmitting}>
              <Save className="h-3.5 w-3.5 mr-1" />
              Save Widget Config
            </Button>
          </div>
        </form>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Embed Code</CardTitle>
          <CardDescription>Add this snippet to your website's HTML before &lt;/body&gt;</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="bg-muted rounded-lg p-4 text-xs overflow-x-auto font-mono whitespace-pre-wrap">
{`<script>
  window.NIAConfig = { tenantId: "${tenantId}", position: "bottom-right" };
</script>
<script src="https://cdn.nia.chat/widget.js" async></script>`}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Telegram tab ──────────────────────────────────────────────

function TelegramTab({ tenantId, config }: { tenantId: string; config: TelegramConfig }) {
  const update = useUpdateTelegramConfig(tenantId);
  const { register, handleSubmit, control, formState: { isDirty, isSubmitting } } = useForm({ defaultValues: config });

  return (
    <form onSubmit={handleSubmit((d) => update.mutateAsync(d))} className="mt-4 space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2"><Send className="h-4 w-4 text-blue-500" />Telegram Bot</CardTitle>
            <Controller control={control} name="enabled" render={({ field }) => (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">Enabled</span>
                <Switch checked={field.value} onCheckedChange={field.onChange} />
              </div>
            )} />
          </div>
          <CardDescription>Connect a Telegram bot to receive and respond to messages</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Bot Token</Label>
              <Input type="password" placeholder="123456:ABC-DEF…" className="font-mono text-xs" {...register("bot_token")} />
            </div>
            <div className="space-y-1.5">
              <Label>Bot Username</Label>
              <Input placeholder="@my_nia_bot" {...register("bot_username")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Welcome Message</Label>
            <Input placeholder="Hi! I'm NIA, how can I help you?" {...register("welcome_message")} />
          </div>
        </CardContent>
      </Card>
      <div className="flex justify-end">
        <Button type="submit" disabled={!isDirty} loading={isSubmitting}>
          <Save className="h-3.5 w-3.5 mr-1" />Save Telegram Config
        </Button>
      </div>
    </form>
  );
}

// ─── Teams tab ─────────────────────────────────────────────────

function TeamsTab({ tenantId, config }: { tenantId: string; config: TeamsConfig }) {
  const update = useUpdateTeamsConfig(tenantId);
  const { register, handleSubmit, control, formState: { isDirty, isSubmitting } } = useForm({
    defaultValues: { ...config, auto_handoff_keywords: config.auto_handoff_keywords?.join(", ") ?? "" },
  });

  const onSubmit = handleSubmit(async (d: any) => {
    await update.mutateAsync({
      ...d,
      auto_handoff_keywords: d.auto_handoff_keywords.split(",").map((s: string) => s.trim()).filter(Boolean),
    });
  });

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2"><Blocks className="h-4 w-4 text-indigo-500" />Microsoft Teams</CardTitle>
            <Controller control={control} name="enabled" render={({ field }) => (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">Enabled</span>
                <Switch checked={field.value} onCheckedChange={field.onChange} />
              </div>
            )} />
          </div>
          <CardDescription>Post NIA conversations to a Teams channel via webhook</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label>Incoming Webhook URL</Label>
            <Input type="password" placeholder="https://contoso.webhook.office.com/…" className="font-mono text-xs" {...register("webhook_url")} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Channel ID</Label>
              <Input placeholder="19:abc123…" className="font-mono text-xs" {...register("channel_id")} />
            </div>
            <div className="space-y-1.5">
              <Label>Escalation Timeout (min)</Label>
              <Input type="number" min="1" {...register("escalation_timeout_minutes", { valueAsNumber: true })} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Auto-handoff Keywords <span className="text-xs text-muted-foreground">(comma-separated)</span></Label>
            <Input placeholder="speak to human, agent, help please" {...register("auto_handoff_keywords")} />
          </div>
        </CardContent>
      </Card>
      <div className="flex justify-end">
        <Button type="submit" disabled={!isDirty} loading={isSubmitting}>
          <Save className="h-3.5 w-3.5 mr-1" />Save Teams Config
        </Button>
      </div>
    </form>
  );
}

// ─── Payment tab ───────────────────────────────────────────────

function PaymentTab({ tenantId, config }: { tenantId: string; config: PaymentConfig }) {
  const update = useUpdatePaymentConfig(tenantId);
  const { register, handleSubmit, control, formState: { isDirty, isSubmitting } } = useForm({ defaultValues: config });

  return (
    <form onSubmit={handleSubmit((d) => update.mutateAsync(d))} className="mt-4 space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2"><CreditCard className="h-4 w-4 text-emerald-500" />Stripe Payments</CardTitle>
            <Controller control={control} name="enabled" render={({ field }) => (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">Enabled</span>
                <Switch checked={field.value} onCheckedChange={field.onChange} />
              </div>
            )} />
          </div>
          <CardDescription>Accept payments inside the chat using Stripe Checkout</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Publishable Key</Label>
              <Input placeholder="pk_live_…" className="font-mono text-xs" {...register("stripe_public_key")} />
            </div>
            <div className="space-y-1.5">
              <Label>Secret Key</Label>
              <Input type="password" placeholder="sk_live_…" className="font-mono text-xs" {...register("stripe_secret_key")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Default Currency</Label>
              <Input placeholder="USD" className="font-mono text-xs uppercase" {...register("currency_default")} />
            </div>
            <div className="space-y-1.5">
              <Label>Session Expiry (min)</Label>
              <Input type="number" min="5" {...register("checkout_session_expires_minutes", { valueAsNumber: true })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Success URL</Label>
              <Input placeholder="https://example.com/success" className="text-xs" {...register("success_url_template")} />
            </div>
            <div className="space-y-1.5">
              <Label>Cancel URL</Label>
              <Input placeholder="https://example.com/cancel" className="text-xs" {...register("cancel_url_template")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Webhook Secret</Label>
            <Input type="password" placeholder="whsec_…" className="font-mono text-xs" {...register("webhook_secret")} />
          </div>
        </CardContent>
      </Card>
      <div className="flex justify-end">
        <Button type="submit" disabled={!isDirty} loading={isSubmitting}>
          <Save className="h-3.5 w-3.5 mr-1" />Save Payment Config
        </Button>
      </div>
    </form>
  );
}
