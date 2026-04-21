"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { useTenant } from "@/hooks/use-api";
import {
  LayoutDashboard,
  GitBranch,
  Zap,
  BookOpen,
  BarChart2,
  Puzzle,
  LogOut,
  ChevronLeft,
  Bot,
  Bug,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const TENANT_NAV = (id: string) => [
  { href: `/dashboard/tenants/${id}/config`,    icon: Bot,          label: "Configuration" },
  { href: `/dashboard/tenants/${id}/fsm`,        icon: GitBranch,    label: "Conversation Flow" },
  { href: `/dashboard/tenants/${id}/skills`,     icon: Zap,          label: "Skills" },
  { href: `/dashboard/tenants/${id}/knowledge`,  icon: BookOpen,     label: "Knowledge" },
  { href: `/dashboard/tenants/${id}/channels`,   icon: Puzzle,       label: "Channels" },
  { href: `/dashboard/tenants/${id}/analytics`,  icon: BarChart2,    label: "Analytics" },
  { href: `/dashboard/tenants/${id}/debug`,      icon: Bug,          label: "Debug Console" },
];

export function Sidebar({ tenantId: tenantIdProp }: { tenantId?: string }) {
  const pathname = usePathname();
  const { data: session } = useSession();

  const tenantIdMatch = pathname.match(/\/dashboard\/tenants\/([^/]+)/);
  const tenantId = tenantIdProp ?? tenantIdMatch?.[1];

  const { data: tenantData } = useTenant(tenantId ?? "");
  const tenantName = tenantData?.data?.name;
  const isInsideTenant = !!tenantId;

  return (
    <aside
      className="flex h-screen flex-col shrink-0 select-none"
      style={{ width: 214, background: "#0a0a10", borderRight: "1px solid rgba(255,255,255,0.06)" }}
    >
      {/* ── Logo ───────────────────────────────────────────── */}
      <div
        className="flex items-center gap-3 px-[18px] py-5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <Link href="/dashboard" className="flex items-center gap-3">
          <div
            className="flex items-center justify-center rounded-lg shrink-0"
            style={{
              width: 30, height: 30,
              background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
              fontSize: 14, fontWeight: 700, color: "#fff",
            }}
          >
            N
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#e2e2f0", lineHeight: 1.2 }}>NIA</div>
            <div style={{ fontSize: 9, color: "#444", letterSpacing: ".1em" }}>ADMIN CONSOLE</div>
          </div>
        </Link>
      </div>

      {/* ── Navigation ────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto px-2 py-3" style={{ paddingTop: 10, paddingBottom: 10 }}>
        {isInsideTenant ? (
          <>
            {/* Back */}
            <Link
              href="/dashboard"
              className="flex items-center gap-2 rounded-lg px-3 py-2 mb-3 transition-colors"
              style={{ fontSize: 12, fontWeight: 500, color: "#555" }}
              onMouseOver={e => (e.currentTarget.style.color = "#818cf8")}
              onMouseOut={e => (e.currentTarget.style.color = "#555")}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              All Tenants
            </Link>

            {/* Tenant identity card */}
            <div
              className="rounded-lg px-3 py-2.5 mb-3"
              style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)" }}
            >
              <div className="flex items-center gap-2.5">
                <div
                  className="flex items-center justify-center rounded-lg shrink-0"
                  style={{ width: 28, height: 28, background: "rgba(99,102,241,0.25)", fontSize: 12, fontWeight: 700, color: "#818cf8" }}
                >
                  {(tenantName ?? tenantId ?? "T")[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p style={{ fontSize: 12, fontWeight: 500, color: "#818cf8" }} className="truncate">
                    {tenantName ?? "Loading…"}
                  </p>
                  <p style={{ fontSize: 10, color: "#444", fontFamily: "'IBM Plex Mono',monospace" }} className="truncate">
                    {tenantId}
                  </p>
                </div>
              </div>
            </div>

            {/* Tenant nav links */}
            <div className="space-y-0.5">
              {TENANT_NAV(tenantId).map(({ href, icon: Icon, label }) => {
                const active = pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className="flex items-center gap-2.5 rounded-lg px-3 py-2 transition-colors"
                    style={{
                      fontSize: 13,
                      fontWeight: active ? 500 : 400,
                      color: active ? "#818cf8" : "#666",
                      background: active ? "rgba(99,102,241,0.15)" : "transparent",
                    }}
                    onMouseOver={e => { if (!active) { e.currentTarget.style.background = "rgba(255,255,255,0.04)"; e.currentTarget.style.color = "#ccc"; } }}
                    onMouseOut={e => { if (!active) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#666"; } }}
                  >
                    <Icon className="shrink-0" style={{ width: 15, height: 15 }} strokeWidth={active ? 2 : 1.5} />
                    <span className="flex-1">{label}</span>
                  </Link>
                );
              })}
            </div>
          </>
        ) : (
          /* Overview */
          <div className="space-y-0.5">
            {[
              { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
              { href: "/dashboard/tenants", icon: Users, label: "Tenants" },
            ].map(({ href, icon: Icon, label }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-2.5 rounded-lg px-3 py-2 transition-colors"
                  style={{
                    fontSize: 13,
                    fontWeight: active ? 500 : 400,
                    color: active ? "#818cf8" : "#666",
                    background: active ? "rgba(99,102,241,0.15)" : "transparent",
                  }}
                  onMouseOver={e => { if (!active) { e.currentTarget.style.background = "rgba(255,255,255,0.04)"; e.currentTarget.style.color = "#ccc"; } }}
                  onMouseOut={e => { if (!active) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#666"; } }}
                >
                  <Icon className="shrink-0" style={{ width: 15, height: 15 }} strokeWidth={active ? 2 : 1.5} />
                  {label}
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* ── User footer ───────────────────────────────────── */}
      <div
        className="flex items-center gap-2.5 px-[18px] py-3"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div
          className="flex items-center justify-center rounded-full shrink-0"
          style={{ width: 26, height: 26, background: "rgba(99,102,241,0.3)", fontSize: 10, fontWeight: 600, color: "#818cf8" }}
        >
          {(session?.user?.email ?? "A")[0].toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <p style={{ fontSize: 12, color: "#ccc" }} className="truncate">
            {session?.user?.email ?? "admin"}
          </p>
          <p style={{ fontSize: 9, color: "#444" }}>Super Admin</p>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          title="Sign out"
          style={{ color: "#444", background: "none", border: "none", cursor: "pointer", padding: 4 }}
          onMouseOver={e => (e.currentTarget.style.color = "#818cf8")}
          onMouseOut={e => (e.currentTarget.style.color = "#444")}
        >
          <LogOut style={{ width: 14, height: 14 }} />
        </button>
      </div>
    </aside>
  );
}

