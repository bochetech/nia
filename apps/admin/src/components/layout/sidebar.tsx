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
  ChevronRight,
  ChevronLeft,
  Bot,
  Bug,
} from "lucide-react";
import { cn } from "@/lib/utils";

const TENANT_NAV = (id: string) => [
  { href: `/dashboard/tenants/${id}/config`, icon: Bot, label: "Configuration" },
  { href: `/dashboard/tenants/${id}/fsm`, icon: GitBranch, label: "Conversation Flow" },
  { href: `/dashboard/tenants/${id}/skills`, icon: Zap, label: "Skills" },
  { href: `/dashboard/tenants/${id}/knowledge`, icon: BookOpen, label: "Knowledge" },
  { href: `/dashboard/tenants/${id}/channels`, icon: Puzzle, label: "Channels" },
  { href: `/dashboard/tenants/${id}/analytics`, icon: BarChart2, label: "Analytics" },
  { href: `/dashboard/tenants/${id}/debug`, icon: Bug, label: "Debug Console" },
];

export function Sidebar({ tenantId: tenantIdProp }: { tenantId?: string }) {
  const pathname = usePathname();
  const { data: session } = useSession();

  const tenantIdMatch = pathname.match(/\/dashboard\/tenants\/([^/]+)/);
  const tenantId = tenantIdProp ?? tenantIdMatch?.[1];

  // Fetch tenant name when inside a tenant context
  const { data: tenantData } = useTenant(tenantId ?? "");

  const tenantName = tenantData?.data?.name;
  const isInsideTenant = !!tenantId;

  return (
    <aside className="flex h-screen w-[220px] flex-col bg-sidebar border-r border-sidebar-border select-none">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-14 border-b border-sidebar-border">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-[8px] bg-gradient-to-b from-primary to-primary/80 flex items-center justify-center shadow-apple-sm">
            <span className="text-white font-semibold text-xs">N</span>
          </div>
          <span className="font-semibold text-sidebar-foreground text-[13px] tracking-tight">
            NIA Admin
          </span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-3">
        {isInsideTenant ? (
          /* ── Tenant context ────────────────────────────── */
          <>
            {/* Back to overview */}
            <Link
              href="/dashboard"
              className="flex items-center gap-2 rounded-lg px-2.5 py-[7px] text-[12px] font-medium text-sidebar-foreground/45 hover:text-sidebar-foreground hover:bg-black/[0.04] transition-all duration-150 mb-3"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              All Tenants
            </Link>

            {/* Tenant identity card */}
            <div className="rounded-xl bg-sidebar-accent/60 border border-sidebar-border px-3 py-2.5 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-lg bg-primary/12 flex items-center justify-center shrink-0">
                  <span className="text-[11px] font-bold text-primary">
                    {(tenantName ?? tenantId ?? "T")[0].toUpperCase()}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="text-[12px] font-semibold text-sidebar-foreground truncate">
                    {tenantName ?? "Loading…"}
                  </p>
                  <p className="text-[10px] text-sidebar-foreground/35 font-mono truncate">
                    {tenantId}
                  </p>
                </div>
              </div>
            </div>

            {/* Tenant navigation */}
            <div className="space-y-0.5">
              {TENANT_NAV(tenantId).map(({ href, icon: Icon, label }) => {
                const active = pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13px] font-medium transition-all duration-150",
                      active
                        ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-apple-sm"
                        : "text-sidebar-foreground/60 hover:bg-black/[0.04] hover:text-sidebar-foreground"
                    )}
                  >
                    <Icon className="h-[16px] w-[16px] shrink-0" strokeWidth={active ? 2 : 1.5} />
                    <span className="flex-1">{label}</span>
                    {active && (
                      <ChevronRight className="h-3 w-3 text-sidebar-accent-foreground/40" />
                    )}
                  </Link>
                );
              })}
            </div>
          </>
        ) : (
          /* ── Overview context ──────────────────────────── */
          <Link
            href="/dashboard"
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13px] font-medium transition-all duration-150",
              pathname === "/dashboard"
                ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-apple-sm"
                : "text-sidebar-foreground/60 hover:bg-black/[0.04] hover:text-sidebar-foreground"
            )}
          >
            <LayoutDashboard className="h-[16px] w-[16px] shrink-0" strokeWidth={pathname === "/dashboard" ? 2 : 1.5} />
            Overview
          </Link>
        )}
      </nav>

      {/* User */}
      <div className="border-t border-sidebar-border px-3 py-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2.5 py-1.5">
          <div className="h-7 w-7 rounded-full bg-gradient-to-b from-primary/20 to-primary/10 flex items-center justify-center shrink-0">
            <span className="text-[11px] font-semibold text-primary">
              {(session?.user?.email ?? "A")[0].toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[12px] font-medium text-sidebar-foreground truncate">
              {session?.user?.email ?? "admin"}
            </p>
            <p className="text-[11px] text-sidebar-foreground/40">Admin</p>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="text-sidebar-foreground/30 hover:text-sidebar-foreground/60 transition-colors"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
