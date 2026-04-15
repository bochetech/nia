"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { debugApi, createTraceEventSource } from "@/lib/api";
import type { WidgetSession, ChatResult, TenantConfigDTO } from "@/lib/api";
import { useTenant, useTenantConfig } from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Bug,
  Send,
  RotateCcw,
  Radio,
  Loader2,
  Bot,
  User,
  Zap,
  GitBranch,
  Hash,
  Clock,
  ArrowRight,
  Brain,
  MessageSquare,
  Activity,
  Circle,
  ChevronDown,
  DollarSign,
} from "lucide-react";
import { toast } from "sonner";

// ─── Types ─────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  timestamp: Date;
  meta?: {
    fsm_state?: string;
    tokens_used?: number;
    latency_ms?: number;
  };
}

interface TraceEvent {
  id: string;
  type: string;
  ts: number;
  [key: string]: unknown;
}

// ─── Helpers ───────────────────────────────────────────────────

function fsmStateBadgeColor(state: string): string {
  const map: Record<string, string> = {
    idle: "bg-gray-100 text-gray-600",
    greeting: "bg-blue-100 text-blue-700",
    discovery: "bg-indigo-100 text-indigo-700",
    faq_answer: "bg-emerald-100 text-emerald-700",
    recommending: "bg-amber-100 text-amber-700",
    product_selected: "bg-orange-100 text-orange-700",
    checkout_init: "bg-pink-100 text-pink-700",
    awaiting_payment: "bg-purple-100 text-purple-700",
    confirmed: "bg-green-100 text-green-700",
    handoff_active: "bg-red-100 text-red-700",
    closed: "bg-gray-200 text-gray-500",
  };
  return map[state] ?? "bg-slate-100 text-slate-600";
}

function traceIcon(type: string) {
  switch (type) {
    case "fsm_transition":
      return <GitBranch className="h-3 w-3 text-violet-500" />;
    case "intent_detected":
      return <Brain className="h-3 w-3 text-blue-500" />;
    case "skill_call":
      return <Zap className="h-3 w-3 text-amber-500" />;
    case "session_end":
      return <Circle className="h-3 w-3 text-gray-400" />;
    case "connected":
      return <Radio className="h-3 w-3 text-green-500" />;
    default:
      return <Activity className="h-3 w-3 text-slate-400" />;
  }
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

// ─── Main page ─────────────────────────────────────────────────

export default function DebugConsolePage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const { data: tenantData } = useTenant(tenantId);
  const { data: configData } = useTenantConfig(tenantId);
  const tenantName = tenantData?.data?.name ?? tenantId;

  // Widget styling from tenant config
  const tenantConfig = configData?.data as TenantConfigDTO | undefined;
  const uiConfig = tenantConfig?.ui_config;
  const aiConfig = tenantConfig?.ai_config;
  const primaryColor = uiConfig?.primary_color ?? "#7C3AED";
  const chatTitle = uiConfig?.chat_title ?? uiConfig?.header_title ?? tenantName;
  const welcomeMessage = uiConfig?.welcome_message ?? `Hi! I'm the assistant for ${tenantName}. How can I help you?`;
  const logoUrl = uiConfig?.logo_url;

  // Cost rates (USD per 1M tokens, default GPT-4o-mini pricing)
  const inputRate = (aiConfig?.input_cost_per_million ?? 0.15) / 1_000_000;
  const outputRate = (aiConfig?.output_cost_per_million ?? 0.60) / 1_000_000;

  // Session state
  const [widgetSession, setWidgetSession] = useState<WidgetSession | null>(null);
  const [connecting, setConnecting] = useState(false);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [sending, setSending] = useState(false);

  // Trace state
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [traceConnected, setTraceConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  // Counters
  const [currentFsmState, setCurrentFsmState] = useState<string>("idle");
  const [totalTokens, setTotalTokens] = useState(0);
  const [totalInputTokens, setTotalInputTokens] = useState(0);
  const [totalOutputTokens, setTotalOutputTokens] = useState(0);
  const [messageCount, setMessageCount] = useState(0);
  const [intentsDetected, setIntentsDetected] = useState<string[]>([]);
  const [stateTransitions, setStateTransitions] = useState<{ from: string; to: string; ts: number }[]>([]);

  // Derived: conversation cost in USD
  // Formula: (input_tokens × input_rate) + (output_tokens × output_rate)
  const totalCost = totalInputTokens * inputRate + totalOutputTokens * outputRate;

  // Refs for auto-scroll
  const chatEndRef = useRef<HTMLDivElement>(null);
  const traceEndRef = useRef<HTMLDivElement>(null);

  // ── Start a debug session ────────────────────────────────────

  const startSession = useCallback(async () => {
    setConnecting(true);
    try {
      const res = await debugApi.getWidgetToken(tenantId);
      setWidgetSession(res.data);
      setMessages([{
        id: "system-start",
        role: "system",
        text: `Debug session started. Session ID: ${res.data.session_id}`,
        timestamp: new Date(),
      }]);
      setTraceEvents([]);
      setCurrentFsmState("idle");
      setTotalTokens(0);
      setTotalInputTokens(0);
      setTotalOutputTokens(0);
      setMessageCount(0);
      setIntentsDetected([]);
      setStateTransitions([]);
      toast.success("Debug session started");
    } catch (e: any) {
      toast.error(`Failed to start session: ${e.message}`);
    } finally {
      setConnecting(false);
    }
  }, [tenantId]);

  // ── Connect SSE trace ────────────────────────────────────────

  useEffect(() => {
    if (!widgetSession?.token || !widgetSession?.session_id) return;

    esRef.current?.close();
    const es = createTraceEventSource(widgetSession.token, widgetSession.session_id);
    esRef.current = es;

    es.addEventListener("open", () => setTraceConnected(true));
    es.addEventListener("error", () => setTraceConnected(false));
    es.addEventListener("message", (evt) => {
      try {
        const event = JSON.parse(evt.data);
        const traceEvt: TraceEvent = {
          ...event,
          id: `trace-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          ts: event.ts ?? Date.now() / 1000,
        };
        setTraceEvents((prev) => [...prev, traceEvt].slice(-200));

        // Update state from trace events
        if (event.type === "fsm_transition") {
          if (event.to) setCurrentFsmState(event.to);
          setStateTransitions((prev) => [...prev, { from: event.from ?? "?", to: event.to ?? "?", ts: event.ts }]);
        }
        if (event.type === "intent_detected") {
          if (event.intent) setIntentsDetected((prev) => [...prev, event.intent]);
          if (event.fsm_state) setCurrentFsmState(event.fsm_state);
        }
        if (event.type === "llm_call") {
          const inp = (event.input_tokens as number) ?? 0;
          const out = (event.output_tokens as number) ?? 0;
          setTotalInputTokens((t) => t + inp);
          setTotalOutputTokens((t) => t + out);
        }
      } catch {}
    });

    return () => {
      es.close();
      setTraceConnected(false);
    };
  }, [widgetSession?.token, widgetSession?.session_id]);

  // ── Send message ─────────────────────────────────────────────

  const sendMessage = useCallback(async () => {
    if (!inputText.trim() || !widgetSession?.token) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: inputText.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setSending(true);
    setMessageCount((c) => c + 1);
    const startTime = performance.now();

    try {
      const res = await debugApi.sendMessage(widgetSession.token, userMsg.text);
      const latency = performance.now() - startTime;
      const data: ChatResult = res.data;

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: data.response,
        timestamp: new Date(),
        meta: {
          fsm_state: data.fsm_state,
          tokens_used: data.tokens_used,
          latency_ms: latency,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setCurrentFsmState(data.fsm_state);
      setTotalTokens((t) => t + data.tokens_used);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: "system",
          text: `Error: ${e.message}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }, [inputText, widgetSession?.token]);

  // ── Auto-scroll ──────────────────────────────────────────────

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [traceEvents]);

  // ── Reset session ────────────────────────────────────────────

  const resetSession = useCallback(() => {
    esRef.current?.close();
    setWidgetSession(null);
    setMessages([]);
    setTraceEvents([]);
    setTraceConnected(false);
    setCurrentFsmState("idle");
    setTotalTokens(0);
    setTotalInputTokens(0);
    setTotalOutputTokens(0);
    setMessageCount(0);
    setIntentsDetected([]);
    setStateTransitions([]);
  }, []);

  // ── No session state ─────────────────────────────────────────

  if (!widgetSession) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Card className="max-w-md w-full">
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-3 h-12 w-12 rounded-2xl bg-gradient-to-br from-violet-100 to-blue-100 flex items-center justify-center">
              <Bug className="h-6 w-6 text-violet-600" />
            </div>
            <CardTitle className="text-lg">Debug Console</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Start a live chat session with <strong>{tenantName}</strong> and see the full execution trace in real time.
            </p>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-3 pt-2">
            <Button onClick={startSession} disabled={connecting} className="w-full max-w-xs">
              {connecting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Radio className="h-4 w-4 mr-2" />
              )}
              {connecting ? "Connecting…" : "Start Debug Session"}
            </Button>
            <p className="text-[11px] text-muted-foreground text-center">
              This creates a real widget session with SSE trace. Messages are processed by the orchestrator exactly like a real user.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Active session layout ────────────────────────────────────

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* ── Left: Chat (widget-styled) ──────────────────── */}
      <div className="w-[380px] flex flex-col border-r bg-white shadow-sm">
        {/* Widget header */}
        <div
          className="px-4 py-3 flex items-center justify-between"
          style={{ backgroundColor: primaryColor }}
        >
          <div className="flex items-center gap-2.5">
            {logoUrl ? (
              <img src={logoUrl} alt="logo" className="h-8 w-8 rounded-full object-cover" />
            ) : (
              <div className="h-8 w-8 rounded-full bg-white/20 flex items-center justify-center">
                <MessageSquare className="h-4 w-4 text-white" />
              </div>
            )}
            <div>
              <div className="text-[13px] font-semibold text-white">{chatTitle}</div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <div className="h-1.5 w-1.5 rounded-full bg-green-300 animate-pulse" />
                <span className="text-[10px] text-white/70">Online · Debug Mode</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn("text-[9px] border-white/30 text-white bg-white/15 font-mono")}
            >
              {currentFsmState}
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-white/70 hover:text-white hover:bg-white/10"
              onClick={resetSession}
              title="Reset session"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 bg-slate-50">
          {/* Welcome bubble (always shown) */}
          <div className="flex gap-2.5">
            <div
              className="h-7 w-7 rounded-full flex items-center justify-center shrink-0 mt-0.5"
              style={{ backgroundColor: `${primaryColor}20` }}
            >
              {logoUrl ? (
                <img src={logoUrl} alt="bot" className="h-5 w-5 rounded-full object-cover" />
              ) : (
                <Bot className="h-3.5 w-3.5" style={{ color: primaryColor }} />
              )}
            </div>
            <div className="max-w-[80%] rounded-xl rounded-bl-sm px-3 py-2 text-[13px] leading-relaxed bg-white border border-slate-100 shadow-sm text-slate-800">
              {welcomeMessage}
            </div>
          </div>

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "flex gap-2.5",
                msg.role === "user" ? "flex-row-reverse" : "flex-row"
              )}
            >
              {msg.role !== "system" && (
                <div
                  className="h-7 w-7 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                  style={msg.role === "user"
                    ? { backgroundColor: `${primaryColor}18` }
                    : { backgroundColor: `${primaryColor}20` }
                  }
                >
                  {msg.role === "user" ? (
                    <User className="h-3.5 w-3.5" style={{ color: primaryColor }} />
                  ) : logoUrl ? (
                    <img src={logoUrl} alt="bot" className="h-5 w-5 rounded-full object-cover" />
                  ) : (
                    <Bot className="h-3.5 w-3.5" style={{ color: primaryColor }} />
                  )}
                </div>
              )}
              <div
                className={cn(
                  "max-w-[80%] rounded-xl px-3 py-2 text-[13px] leading-relaxed",
                  msg.role === "user"
                    ? "rounded-br-sm text-white shadow-sm"
                    : msg.role === "assistant"
                    ? "bg-white border border-slate-100 shadow-sm rounded-bl-sm text-slate-800"
                    : "bg-transparent text-muted-foreground text-[11px] italic text-center w-full"
                )}
                style={msg.role === "user" ? { backgroundColor: primaryColor } : undefined}
              >
                {msg.text}
                {msg.meta && (
                  <div className="flex items-center gap-2 mt-1.5 pt-1.5 border-t border-white/20 text-[10px] opacity-70">
                    {msg.meta.fsm_state && (
                      <span className="flex items-center gap-0.5">
                        <GitBranch className="h-2.5 w-2.5" />
                        {msg.meta.fsm_state}
                      </span>
                    )}
                    {msg.meta.tokens_used != null && (
                      <span className="flex items-center gap-0.5">
                        <Hash className="h-2.5 w-2.5" />
                        {msg.meta.tokens_used} tok
                      </span>
                    )}
                    {msg.meta.tokens_used != null && (
                      <span className="flex items-center gap-0.5">
                        <DollarSign className="h-2.5 w-2.5" />
                        {/* Blended estimate: avg of input + output rate × total tokens */}
                        ${(msg.meta.tokens_used * ((inputRate + outputRate) / 2)).toFixed(5)}
                      </span>
                    )}
                    {msg.meta.latency_ms != null && (
                      <span className="flex items-center gap-0.5">
                        <Clock className="h-2.5 w-2.5" />
                        {formatMs(msg.meta.latency_ms)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex gap-2.5">
              <div className="h-7 w-7 rounded-full bg-gradient-to-br from-violet-100 to-blue-100 flex items-center justify-center shrink-0">
                <Bot className="h-3.5 w-3.5 text-violet-600" />
              </div>
              <div className="bg-muted rounded-xl rounded-bl-sm px-3 py-2">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="px-4 py-3 border-t bg-white">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
            className="flex gap-2"
          >
            <Input
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={uiConfig?.input_placeholder ?? uiConfig?.placeholder ?? "Type a message…"}
              disabled={sending}
              className="flex-1 text-[13px]"
              autoFocus
            />
            <Button
              type="submit"
              size="icon"
              disabled={sending || !inputText.trim()}
              style={{ backgroundColor: primaryColor }}
              className="hover:opacity-90 text-white border-0"
            >
              <Send className="h-4 w-4" />
            </Button>
          </form>
          <div className="mt-1.5 flex items-center justify-between">
            <span className="text-[10px] text-muted-foreground font-mono">
              {widgetSession.session_id.slice(0, 12)}…
            </span>
            {uiConfig?.show_powered_by !== false && (
              <span className="text-[10px] text-muted-foreground">
                Powered by <strong>NIA</strong>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Right: Trace & Metrics ──────────────────────── */}
      <div className="flex-1 flex flex-col bg-slate-50/50 overflow-hidden">
        {/* Metrics bar */}
        <div className="grid grid-cols-6 gap-2 px-4 py-3 border-b bg-white">
          <MetricCard
            icon={<GitBranch className="h-3.5 w-3.5 text-violet-500" />}
            label="FSM State"
            value={currentFsmState}
            className={fsmStateBadgeColor(currentFsmState)}
          />
          <MetricCard
            icon={<Hash className="h-3.5 w-3.5 text-blue-500" />}
            label="Tokens Used"
            value={totalTokens.toLocaleString()}
          />
          <MetricCard
            icon={<DollarSign className="h-3.5 w-3.5 text-green-600" />}
            label="Est. Cost"
            value={totalCost < 0.01 ? `$${totalCost.toFixed(4)}` : `$${totalCost.toFixed(3)}`}
            subtitle={`in ${totalInputTokens.toLocaleString()} / out ${totalOutputTokens.toLocaleString()}`}
          />
          <MetricCard
            icon={<MessageSquare className="h-3.5 w-3.5 text-emerald-500" />}
            label="Messages"
            value={messageCount.toString()}
          />
          <MetricCard
            icon={<Brain className="h-3.5 w-3.5 text-amber-500" />}
            label="Intents"
            value={intentsDetected.length.toString()}
          />
          <MetricCard
            icon={<Activity className="h-3.5 w-3.5 text-pink-500" />}
            label="Transitions"
            value={stateTransitions.length.toString()}
          />
        </div>

        {/* Trace + side panels */}
        <div className="flex-1 flex overflow-hidden">
          {/* Trace log */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="px-4 py-2 border-b bg-white flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-slate-400" />
                <span className="text-[12px] font-semibold text-slate-600">Event Trace</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className={cn(
                    "h-2 w-2 rounded-full",
                    traceConnected ? "bg-green-500 animate-pulse" : "bg-red-400"
                  )}
                />
                <span className="text-[10px] text-muted-foreground">
                  {traceConnected ? "Connected" : "Disconnected"}
                </span>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
              {traceEvents.length === 0 && (
                <div className="flex items-center justify-center py-12 text-[12px] text-muted-foreground">
                  <Activity className="h-4 w-4 mr-2 opacity-40" />
                  Waiting for trace events… Send a message to begin.
                </div>
              )}
              {traceEvents.map((evt) => (
                <TraceEventRow key={evt.id} event={evt} />
              ))}
              <div ref={traceEndRef} />
            </div>
          </div>

          {/* Side panel: intents + transitions */}
          <div className="w-56 border-l bg-white overflow-y-auto">
            {/* Intents detected */}
            <div className="p-3 border-b">
              <div className="flex items-center gap-1.5 mb-2">
                <Brain className="h-3 w-3 text-amber-500" />
                <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                  Intents
                </span>
              </div>
              {intentsDetected.length === 0 ? (
                <p className="text-[11px] text-muted-foreground italic">None detected yet</p>
              ) : (
                <div className="space-y-1">
                  {intentsDetected.map((intent, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-1.5 text-[11px] bg-amber-50 text-amber-700 rounded-md px-2 py-1"
                    >
                      <span className="text-[9px] text-amber-400 font-mono">{i + 1}</span>
                      <span className="truncate">{intent}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* State transitions */}
            <div className="p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <GitBranch className="h-3 w-3 text-violet-500" />
                <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                  State Flow
                </span>
              </div>
              {stateTransitions.length === 0 ? (
                <p className="text-[11px] text-muted-foreground italic">No transitions yet</p>
              ) : (
                <div className="space-y-1">
                  {stateTransitions.map((t, i) => (
                    <div key={i} className="flex items-center gap-1 text-[11px]">
                      <Badge
                        variant="outline"
                        className={cn("text-[9px] px-1 py-0", fsmStateBadgeColor(t.from))}
                      >
                        {t.from}
                      </Badge>
                      <ArrowRight className="h-2.5 w-2.5 text-slate-300 shrink-0" />
                      <Badge
                        variant="outline"
                        className={cn("text-[9px] px-1 py-0", fsmStateBadgeColor(t.to))}
                      >
                        {t.to}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ────────────────────────────────────────────

function MetricCard({
  icon,
  label,
  value,
  className,
  subtitle,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  className?: string;
  subtitle?: string;
}) {
  return (
    <div className="rounded-lg border bg-white px-3 py-2">
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wide">
          {label}
        </span>
      </div>
      <div
        className={cn(
          "text-[13px] font-semibold text-slate-800 truncate",
          className && `rounded px-1.5 py-0.5 text-[11px] ${className}`
        )}
      >
        {value}
      </div>
      {subtitle && (
        <div className="text-[9px] text-muted-foreground mt-0.5 truncate">{subtitle}</div>
      )}
    </div>
  );
}

function TraceEventRow({ event }: { event: TraceEvent }) {
  const [expanded, setExpanded] = useState(false);

  const typeLabels: Record<string, string> = {
    connected: "SSE Connected",
    fsm_transition: "FSM Transition",
    intent_detected: "Intent Detected",
    skill_call: "Skill Execution",
    session_end: "Session Ended",
    llm_call: "LLM Call",
    rag_query: "RAG Query",
  };

  const label = typeLabels[event.type] ?? event.type;

  // Summary text per event type
  let summary = "";
  if (event.type === "fsm_transition") {
    summary = `${event.from ?? "?"} → ${event.to ?? "?"}`;
  } else if (event.type === "intent_detected") {
    summary = `${event.intent ?? "unknown"}${event.confidence ? ` (${(event.confidence as number * 100).toFixed(0)}%)` : ""}`;
  } else if (event.type === "skill_call") {
    summary = `${event.action ?? event.skill ?? "?"}${event.latency_ms ? ` · ${formatMs(event.latency_ms as number)}` : ""}`;
  } else if (event.type === "llm_call") {
    const inp = (event.input_tokens as number) ?? 0;
    const out = (event.output_tokens as number) ?? 0;
    const tok = inp + out || (event.tokens as number) || 0;
    summary = `${event.model ?? "model"}${tok ? ` · ${tok} tok` : ""}`;
  } else if (event.type === "connected") {
    summary = `session ${(event.session_id as string)?.slice(0, 8) ?? ""}…`;
  }

  // Collect all extra fields for expanded view
  const extraKeys = Object.keys(event).filter(
    (k) => !["id", "type", "ts"].includes(k) && event[k] != null
  );

  return (
    <button
      onClick={() => setExpanded(!expanded)}
      className="w-full text-left rounded-md border bg-white hover:bg-slate-50 transition-colors px-2.5 py-1.5 group"
    >
      <div className="flex items-center gap-2">
        {traceIcon(event.type)}
        <span className="text-[11px] font-medium text-slate-700 flex-1 truncate">
          {label}
        </span>
        <span className="text-[10px] text-muted-foreground font-mono">
          {event.ts ? new Date(event.ts * 1000).toLocaleTimeString() : "—"}
        </span>
        <ChevronDown
          className={cn(
            "h-3 w-3 text-slate-300 transition-transform",
            expanded && "rotate-180"
          )}
        />
      </div>
      {summary && (
        <div className="text-[10px] text-slate-500 mt-0.5 pl-5 truncate">{summary}</div>
      )}
      {expanded && extraKeys.length > 0 && (
        <div className="mt-1.5 pl-5 pt-1.5 border-t border-slate-100 space-y-0.5">
          {extraKeys.map((k) => (
            <div key={k} className="flex items-start gap-2 text-[10px]">
              <span className="font-mono text-slate-400 shrink-0">{k}:</span>
              <span className="text-slate-600 break-all">
                {typeof event[k] === "object" ? JSON.stringify(event[k]) : String(event[k])}
              </span>
            </div>
          ))}
        </div>
      )}
    </button>
  );
}
