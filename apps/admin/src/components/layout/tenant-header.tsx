"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, Save, PauseCircle } from "lucide-react";
import { useTenant } from "@/hooks/use-api";

const TABS = (id: string) => [
  { href: `/dashboard/tenants/${id}/fsm`,       label: "FSM Builder" },
  { href: `/dashboard/tenants/${id}/skills`,    label: "Skills" },
  { href: `/dashboard/tenants/${id}/debug`,     label: "Debug" },
  { href: `/dashboard/tenants/${id}/channels`,  label: "Channels" },
  { href: `/dashboard/tenants/${id}/analytics`, label: "Analytics" },
  { href: `/dashboard/tenants/${id}/config`,    label: "Settings" },
];

interface TenantHeaderProps {
  tenantId: string;
}

export function TenantHeader({ tenantId }: TenantHeaderProps) {
  const pathname = usePathname();
  const { data: tenantData } = useTenant(tenantId);
  const tenant = tenantData?.data;

  const planLabels: Record<string, string> = { starter: "Starter", pro: "Pro", enterprise: "Enterprise" };
  const statusColor = (status: string) =>
    status === "active" ? { bg: "rgba(16,185,129,0.12)", color: "#10b981" } : { bg: "rgba(239,68,68,0.12)", color: "#ef4444" };

  return (
    <header
      className="flex flex-col shrink-0"
      style={{ background: "#0a0a10", borderBottom: "1px solid rgba(255,255,255,0.08)" }}
    >
      {/* ── Top bar: breadcrumb + actions ─────────────────── */}
      <div className="flex items-center gap-3 px-5 pt-3 pb-2">
        <Link
          href="/dashboard"
          className="flex items-center gap-1.5 transition-colors"
          style={{ color: "#555", fontSize: 12 }}
          onMouseOver={e => (e.currentTarget.style.color = "#818cf8")}
          onMouseOut={e => (e.currentTarget.style.color = "#555")}
        >
          <ChevronLeft style={{ width: 14, height: 14 }} />
          Tenants
        </Link>

        <span style={{ color: "#2a2a3a", fontSize: 12 }}>/</span>

        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <span style={{ fontSize: 13, fontWeight: 500, color: "#e2e2f0" }} className="truncate">
            {tenant?.name ?? tenantId}
          </span>

          <span
            style={{ fontSize: 9, fontFamily: "'IBM Plex Mono',monospace", color: "#555",
              background: "rgba(255,255,255,0.04)", borderRadius: 4, padding: "2px 6px" }}
          >
            {tenantId}
          </span>

          {tenant?.plan && (
            <span style={{ fontSize: 10, borderRadius: 4, padding: "2px 7px",
              background: "rgba(99,102,241,0.12)", color: "#818cf8" }}>
              {planLabels[tenant.plan] ?? tenant.plan}
            </span>
          )}

          {tenant?.status && (() => {
            const s = statusColor(tenant.status);
            return (
              <span style={{ fontSize: 10, borderRadius: 4, padding: "2px 7px",
                background: s.bg, color: s.color }}>
                {tenant.status}
              </span>
            );
          })()}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-opacity hover:opacity-80"
            style={{ fontSize: 12, fontWeight: 500, color: "#e2e2f0",
              background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
              cursor: "pointer" }}
          >
            <PauseCircle style={{ width: 13, height: 13 }} />
            Suspend
          </button>
          <button
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-opacity hover:opacity-80"
            style={{ fontSize: 12, fontWeight: 500, color: "#fff",
              background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
              border: "none", cursor: "pointer" }}
          >
            <Save style={{ width: 13, height: 13 }} />
            Save
          </button>
        </div>
      </div>

      {/* ── Tabs ──────────────────────────────────────────── */}
      <div className="flex items-end gap-0 px-5">
        {TABS(tenantId).map(({ href, label }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className="relative px-4 py-2 transition-colors"
              style={{
                fontSize: 13,
                fontWeight: active ? 500 : 400,
                color: active ? "#818cf8" : "#555",
                borderBottom: active ? "2px solid #6366f1" : "2px solid transparent",
                whiteSpace: "nowrap",
              }}
              onMouseOver={e => { if (!active) e.currentTarget.style.color = "#aaa"; }}
              onMouseOut={e => { if (!active) e.currentTarget.style.color = "#555"; }}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
