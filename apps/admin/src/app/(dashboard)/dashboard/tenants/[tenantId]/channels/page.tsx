"use client";

import { use } from "react";
import {
  useTenantConfig,
  useUpdateTelegramConfig,
  useUpdateTeamsConfig,
  useUpdatePaymentConfig,
  useUpdateUIConfig,
} from "@/hooks/use-api";
import type { TelegramConfig, TeamsConfig, PaymentConfig, UIConfig } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { useForm, Controller } from "react-hook-form";
import { Save, MessageCircle, Send, CreditCard, Blocks } from "lucide-react";
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
            Configure Widget, Telegram, Microsoft Teams, and Payment integrations
          </p>
        </div>

        <Tabs defaultValue="widget">
          <TabsList className="grid grid-cols-4 w-full">
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
            <TabsTrigger value="payment" className="text-xs">
              <CreditCard className="h-3.5 w-3.5 mr-1.5" />
              Payment
            </TabsTrigger>
          </TabsList>

        <TabsContent value="widget">
          {cfg ? (
            <WidgetTab tenantId={tenantId} uiConfig={cfg.ui_config} />
          ) : null}
        </TabsContent>

        <TabsContent value="telegram">
          {cfg ? (
            <TelegramTab tenantId={tenantId} config={cfg.telegram_config} />
          ) : null}
        </TabsContent>

        <TabsContent value="teams">
          {cfg ? (
            <TeamsTab tenantId={tenantId} config={cfg.teams_config} />
          ) : null}
        </TabsContent>

        <TabsContent value="payment">
          {cfg ? (
            <PaymentTab tenantId={tenantId} config={cfg.payment_config} />
          ) : null}
        </TabsContent>
      </Tabs>
      </div>
    </div>
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
        {/* Live preview */}
        <div>
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Live Preview
          </div>
          <div className="rounded-2xl border shadow-lg overflow-hidden bg-white max-w-[260px]">
            {/* Widget header */}
            <div
              className="px-4 py-3 text-white text-sm font-semibold"
              style={{ backgroundColor: primaryColor }}
            >
              {chatTitle}
            </div>
            {/* Messages area */}
            <div className="bg-gray-50 p-3 min-h-[140px] space-y-2">
              <div className="flex justify-start">
                <div className="bg-white rounded-2xl rounded-tl-sm px-3 py-2 text-xs shadow-sm max-w-[80%]">
                  {welcomeMsg}
                </div>
              </div>
              <div className="flex justify-end">
                <div
                  className="rounded-2xl rounded-tr-sm px-3 py-2 text-xs text-white max-w-[80%]"
                  style={{ backgroundColor: primaryColor }}
                >
                  Hello! I need help.
                </div>
              </div>
            </div>
            {/* Input */}
            <div className="border-t px-3 py-2 flex items-center gap-2 bg-white">
              <div className="flex-1 h-6 rounded-full bg-gray-100 text-xs px-3 text-gray-400 flex items-center">
                {uiConfig.input_placeholder ?? "Type a message…"}
              </div>
              <div
                className="h-6 w-6 rounded-full flex items-center justify-center"
                style={{ backgroundColor: primaryColor }}
              >
                <Send className="h-3 w-3 text-white" />
              </div>
            </div>
          </div>
        </div>

        {/* Form */}
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
              <input
                type="color"
                className="h-8 w-12 rounded border border-input p-1 cursor-pointer"
                {...register("primary_color")}
              />
              <Input
                {...register("primary_color")}
                className="h-8 text-xs font-mono flex-1"
              />
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

      {/* Embed code */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Embed Code</CardTitle>
          <CardDescription>Add this snippet to your website's HTML before &lt;/body&gt;</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="bg-muted rounded-lg p-4 text-xs overflow-x-auto font-mono whitespace-pre-wrap">
{`<script>
  window.NIAConfig = {
    tenantId: "${tenantId}",
    position: "bottom-right"
  };
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
  const { register, handleSubmit, control, formState: { isDirty, isSubmitting } } = useForm({
    defaultValues: config,
  });

  return (
    <form
      onSubmit={handleSubmit((d) => update.mutateAsync(d))}
      className="mt-4 space-y-4"
    >
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Send className="h-4 w-4 text-blue-500" />
              Telegram Bot
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
            Connect a Telegram bot to receive and respond to messages
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Bot Token</Label>
              <Input
                type="password"
                placeholder="123456:ABC-DEF…"
                className="font-mono text-xs"
                {...register("bot_token")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Bot Username</Label>
              <Input
                placeholder="@my_nia_bot"
                {...register("bot_username")}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Welcome Message</Label>
            <Input
              placeholder="Hi! I'm NIA, how can I help you?"
              {...register("welcome_message")}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={!isDirty} loading={isSubmitting}>
          <Save className="h-3.5 w-3.5 mr-1" />
          Save Telegram Config
        </Button>
      </div>
    </form>
  );
}

// ─── Teams tab ─────────────────────────────────────────────────

function TeamsTab({ tenantId, config }: { tenantId: string; config: TeamsConfig }) {
  const update = useUpdateTeamsConfig(tenantId);
  const { register, handleSubmit, control, formState: { isDirty, isSubmitting } } = useForm({
    defaultValues: {
      ...config,
      auto_handoff_keywords: config.auto_handoff_keywords?.join(", ") ?? "",
    },
  });

  const onSubmit = handleSubmit(async (d: any) => {
    await update.mutateAsync({
      ...d,
      auto_handoff_keywords: d.auto_handoff_keywords
        .split(",")
        .map((s: string) => s.trim())
        .filter(Boolean),
    });
  });

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Blocks className="h-4 w-4 text-indigo-500" />
              Microsoft Teams
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
            Post NIA conversations to a Teams channel via webhook
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label>Incoming Webhook URL</Label>
            <Input
              type="password"
              placeholder="https://contoso.webhook.office.com/…"
              className="font-mono text-xs"
              {...register("webhook_url")}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Channel ID</Label>
              <Input
                placeholder="19:abc123…"
                className="font-mono text-xs"
                {...register("channel_id")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Escalation Timeout (min)</Label>
              <Input
                type="number"
                min="1"
                {...register("escalation_timeout_minutes", { valueAsNumber: true })}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>
              Auto-handoff Keywords{" "}
              <span className="text-xs text-muted-foreground">(comma-separated)</span>
            </Label>
            <Input
              placeholder="speak to human, agent, help please"
              {...register("auto_handoff_keywords")}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={!isDirty} loading={isSubmitting}>
          <Save className="h-3.5 w-3.5 mr-1" />
          Save Teams Config
        </Button>
      </div>
    </form>
  );
}

// ─── Payment tab ───────────────────────────────────────────────

function PaymentTab({ tenantId, config }: { tenantId: string; config: PaymentConfig }) {
  const update = useUpdatePaymentConfig(tenantId);
  const { register, handleSubmit, control, formState: { isDirty, isSubmitting } } = useForm({
    defaultValues: config,
  });

  return (
    <form
      onSubmit={handleSubmit((d) => update.mutateAsync(d))}
      className="mt-4 space-y-4"
    >
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-emerald-500" />
              Stripe Payments
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
            Accept payments inside the chat using Stripe Checkout
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Publishable Key</Label>
              <Input
                placeholder="pk_live_…"
                className="font-mono text-xs"
                {...register("stripe_public_key")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Secret Key</Label>
              <Input
                type="password"
                placeholder="sk_live_…"
                className="font-mono text-xs"
                {...register("stripe_secret_key")}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Default Currency</Label>
              <Input
                placeholder="USD"
                className="font-mono text-xs uppercase"
                {...register("currency_default")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Session Expiry (min)</Label>
              <Input
                type="number"
                min="5"
                {...register("checkout_session_expires_minutes", { valueAsNumber: true })}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Success URL</Label>
              <Input
                placeholder="https://example.com/success?session={CHECKOUT_SESSION_ID}"
                className="text-xs"
                {...register("success_url_template")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Cancel URL</Label>
              <Input
                placeholder="https://example.com/cancel"
                className="text-xs"
                {...register("cancel_url_template")}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Webhook Secret</Label>
            <Input
              type="password"
              placeholder="whsec_…"
              className="font-mono text-xs"
              {...register("webhook_secret")}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={!isDirty} loading={isSubmitting}>
          <Save className="h-3.5 w-3.5 mr-1" />
          Save Payment Config
        </Button>
      </div>
    </form>
  );
}
