"use client";

import { use, useState } from "react";
import { useAnalytics, useSessions } from "@/hooks/use-api";
import { transcriptApi } from "@/lib/api";
import type { SessionItem } from "@/lib/api";
import { formatDate, formatCurrency, formatNumber } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  MessageSquare,
  Users,
  Star,
  DollarSign,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { useSession } from "next-auth/react";

const DAY_OPTIONS = [7, 14, 30, 90];

export default function AnalyticsPage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  const [days, setDays] = useState(30);
  const [page, setPage] = useState(1);
  const [transcriptSession, setTranscriptSession] = useState<SessionItem | null>(null);

  const { data: analyticsData, isLoading: analyticsLoading } = useAnalytics(tenantId, days);
  const { data: sessionsData, isLoading: sessionsLoading } = useSessions(tenantId, page, 20, days);

  const analytics = analyticsData?.data;
  const sessions = sessionsData?.data;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header + day selector */}
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Conversation metrics and session history
            </p>
          </div>
          <div className="flex gap-0.5 rounded-lg border p-0.5 bg-muted/50">
            {DAY_OPTIONS.map((d) => (
              <button
                key={d}
                onClick={() => { setDays(d); setPage(1); }}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  days === d
                    ? "bg-background shadow-sm text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

      {/* KPI cards */}
      <div className="grid grid-cols-4 gap-3">
        <KpiCard
          icon={<MessageSquare className="h-4 w-4" />}
          label="Conversations"
          value={formatNumber(analytics?.total_conversations)}
          loading={analyticsLoading}
          bg="bg-blue-50"
          fg="text-blue-600"
        />
        <KpiCard
          icon={<Users className="h-4 w-4" />}
          label="Messages"
          value={formatNumber(analytics?.total_messages)}
          loading={analyticsLoading}
          bg="bg-violet-50"
          fg="text-violet-600"
        />
        <KpiCard
          icon={<Star className="h-4 w-4" />}
          label="Avg NPS"
          value={analytics?.avg_nps != null ? analytics.avg_nps.toFixed(1) : "—"}
          sub={analytics?.nps_responses ? `${analytics.nps_responses} responses` : undefined}
          loading={analyticsLoading}
          bg="bg-amber-50"
          fg="text-amber-600"
        />
        <KpiCard
          icon={<DollarSign className="h-4 w-4" />}
          label="Est. Cost"
          value={formatCurrency(analytics?.estimated_cost_usd)}
          sub={analytics?.total_tokens ? `${formatNumber(analytics.total_tokens)} tokens` : undefined}
          loading={analyticsLoading}
          bg="bg-emerald-50"
          fg="text-emerald-600"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-3 gap-3">
        {/* Daily volume area chart */}
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Daily Message Volume</CardTitle>
          </CardHeader>
          <CardContent>
            {analyticsLoading ? (
              <div className="h-48 rounded-lg bg-muted animate-pulse" />
            ) : (analytics?.daily_volume?.length ?? 0) === 0 ? (
              <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
                No data for this period
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={analytics!.daily_volume}>
                  <defs>
                    <linearGradient id="msgGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => v.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 10 }} width={32} />
                  <Tooltip
                    contentStyle={{ fontSize: 12 }}
                    formatter={(v: number) => [v, "Messages"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="messages"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fill="url(#msgGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Top intents bar chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Top Intents</CardTitle>
          </CardHeader>
          <CardContent>
            {analyticsLoading ? (
              <div className="h-48 rounded-lg bg-muted animate-pulse" />
            ) : (analytics?.top_intents?.length ?? 0) === 0 ? (
              <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
                No intent data
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={analytics!.top_intents.slice(0, 6)}
                  layout="vertical"
                  margin={{ left: 8, right: 16 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10 }} width={32} />
                  <YAxis
                    type="category"
                    dataKey="intent"
                    tick={{ fontSize: 10 }}
                    width={80}
                    tickFormatter={(v: string) => v.length > 12 ? v.slice(0, 12) + "…" : v}
                  />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Bar dataKey="count" fill="#10b981" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Sessions table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">
              Sessions
              {sessions?.total != null && (
                <span className="ml-2 text-muted-foreground font-normal text-xs">
                  ({formatNumber(sessions.total)} total)
                </span>
              )}
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="icon"
                className="h-7 w-7"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <span className="text-xs text-muted-foreground">{page}</span>
              <Button
                variant="outline"
                size="icon"
                className="h-7 w-7"
                onClick={() => setPage((p) => p + 1)}
                disabled={!sessions?.has_more}
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {sessionsLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-10 rounded bg-muted animate-pulse" />
              ))}
            </div>
          ) : !sessions?.items?.length ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              No sessions in this period
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground">
                    <th className="text-left py-2 pr-4 font-medium">Session</th>
                    <th className="text-left py-2 pr-4 font-medium">Lead</th>
                    <th className="text-right py-2 pr-4 font-medium">Messages</th>
                    <th className="text-right py-2 pr-4 font-medium">NPS</th>
                    <th className="text-left py-2 pr-4 font-medium">Created</th>
                    <th className="text-right py-2 font-medium">Transcript</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.items.map((s) => (
                    <tr
                      key={s.session_id}
                      className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                    >
                      <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                        {s.session_id.slice(0, 16)}…
                      </td>
                      <td className="py-2 pr-4">
                        {s.lead_name ? (
                          <div>
                            <div className="font-medium">{s.lead_name}</div>
                            {s.lead_email && (
                              <div className="text-xs text-muted-foreground">{s.lead_email}</div>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-xs">Anonymous</span>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-right tabular-nums">
                        {s.messages_count}
                      </td>
                      <td className="py-2 pr-4 text-right">
                        {s.nps_score != null ? (
                          <Badge
                            variant={
                              s.nps_score >= 9 ? "success"
                              : s.nps_score >= 7 ? "warning"
                              : "destructive"
                            }
                          >
                            {s.nps_score}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground text-xs">—</span>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-xs text-muted-foreground">
                        {formatDate(s.created_at)}
                      </td>
                      <td className="py-2 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => setTranscriptSession(s)}
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Transcript modal */}
      {transcriptSession && (
        <TranscriptModal
          session={transcriptSession}
          tenantId={tenantId}
          onClose={() => setTranscriptSession(null)}
        />
      )}
      </div>
    </div>
  );
}

// ─── KPI Card ──────────────────────────────────────────────────

function KpiCard({
  icon,
  label,
  value,
  sub,
  loading,
  bg,
  fg,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  loading: boolean;
  bg: string;
  fg: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4 transition-colors hover:bg-accent/30">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2 ${bg}`}>
          <span className={fg}>{icon}</span>
        </div>
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground">{label}</div>
          {loading ? (
            <div className="h-6 w-16 rounded bg-muted animate-pulse mt-0.5" />
          ) : (
            <>
              <div className="text-xl font-bold tabular-nums">{value}</div>
              {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Transcript modal ──────────────────────────────────────────

function TranscriptModal({
  session,
  tenantId,
  onClose,
}: {
  session: SessionItem;
  tenantId: string;
  onClose: () => void;
}) {
  const { data: authSession } = useSession();
  const token = (authSession as any)?.accessToken as string | undefined;
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch transcript on mount
  useState(() => {
    if (!token) return;
    transcriptApi
      .getTranscript(token, tenantId, session.session_id)
      .then((res) => setMessages((res as any).messages ?? []))
      .catch(() => setMessages([]))
      .finally(() => setLoading(false));
  });

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm font-semibold">
            Transcript — {session.session_id.slice(0, 20)}…
          </DialogTitle>
          {session.lead_name && (
            <p className="text-xs text-muted-foreground">{session.lead_name}</p>
          )}
        </DialogHeader>
        <div className="flex-1 overflow-y-auto space-y-3 py-2">
          {loading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-10 rounded bg-muted animate-pulse" />
              ))}
            </div>
          ) : messages.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No messages found
            </p>
          ) : (
            messages.map((msg: any, i: number) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`rounded-2xl px-4 py-2.5 max-w-[80%] text-sm ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  }`}
                >
                  {msg.content}
                  <div className="text-[10px] opacity-60 mt-1">
                    {msg.timestamp ? formatDate(msg.timestamp) : ""}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="border-t pt-2 flex justify-end">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
