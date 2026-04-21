"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { useTheme } from "next-themes";
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
  Sun,
  Moon,
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
  const { resolvedTheme, setTheme } = useTheme();

  const tenantIdMatch = pathname.match(/\/dashboard\/tenants\/([^/]+)/);
  const tenantId = tenantIdProp ?? tenantIdMatch?.[1];

  const { data: tenantData } = useTenant(tenantId ?? "");
  const tenantName = tenantData?.data?.name;
  const isInsideTenant = !!tenantId;
  const isDark = resolvedTheme === "dark";

  return (
    <aside className="flex h-screen flex-col shrink-0 select-none bg-sidebar border-r border-sidebar-border" style={{ width: 214 }}>

      {/* Logo */}
      <div className="flex items-center gap-3 px-[18px] py-5 border-b border-sidebar-border">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div
            className="flex items-center justify-center rounded-lg shrink-0 text-white font-bold text-sm"
            style={{ width: 30, height: 30, background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}
          >
            N
          </div>
          <div>
            <div className="text-[14px] font-semibold text-sidebar-foreground leading-tight">NIA</div>
            <div className="text-[9px] text-sidebar-muted tracking-[.1em]">ADMIN CONSOLE</div>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-2.5">
        {isInsideTenant ? (
          <>
            <Link
              href="/dashboard"
              className="flex items-center gap-2 rounded-lg px-3 py-2 mb-2.5 text-[12px] font-medium text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              All Tenants
            </Link>

            <div className="rounded-lg px-3 py-2.5 mb-2.5 bg-primary/[0.08] border border-primary/[0.15]">
              <div className="flex items-center gap-2.5">
                <div className="flex items-center justify-center rounded-lg shrink-0 text-primary text-xs font-bold bg-primary/20" style={{ width: 28, height: 28 }}>
                  {(tenantName ?? tenantId ?? "T")[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="text-[12px] font-medium text-primary truncate">{tenantName ?? "Loading…"}</p>
                  <p className="text-[10px] text-muted-foreground truncate font-mono">{tenantId}</p>
                </div>
              </div>
            </div>

            <div className="space-y-0.5">
              {TENANT_NAV(tenantId).map(({ href, icon: Icon, label }) => {
                const active = pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors",
                      active
                        ? "bg-primary/[0.12] text-primary font-medium"
                        : "text-muted-foreground hover:bg-primary/[0.06] hover:text-foreground",
                    )}
                  >
                    <Icon className="shrink-0 h-[15px] w-[15px]" strokeWidth={active ? 2 : 1.5} />
                    <span className="flex-1">{label}</span>
                  </Link>
                );
              })}
            </div>
          </>
        ) : (
          <div className="space-y-0.5">
            {[
              { href: "/dashboard",         icon: LayoutDashboard, label: "Dashboard" },
              { href: "/dashboard/tenants", icon: Users,           label: "Tenants" },
            ].map(({ href, icon: Icon, label }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors",
                    active
                      ? "bg-primary/[0.12] text-primary font-medium"
                      : "text-muted-foreground hover:bg-primary/[0.06] hover:text-foreground",
                  )}
                >
                  <Icon className="shrink-0 h-[15px] w-[15px]" strokeWidth={active ? 2 : 1.5} />
                  {label}
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* Footer */}
      <div className="flex items-center gap-2 px-3 py-3 border-t border-sidebar-border">
        <div className="flex items-center justify-center rounded-full shrink-0 bg-primary/20 text-primary text-[10px] font-semibold" style={{ width: 26, height: 26 }}>
          {(session?.user?.email ?? "A")[0].toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[12px] text-foreground truncate">{session?.user?.email ?? "admin"}</p>
          <p className="text-[9px] text-muted-foreground">Super Admin</p>
        </div>
        <button
          onClick={() => setTheme(isDark ? "light" : "dark")}
          title={isDark ? "Switch to light" : "Switch to dark"}
          className="rounded-lg p-1.5 text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
        >
          {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </button>
        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          title="Sign out"
          className="rounded-lg p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
        >
          <LogOut className="h-3.5 w-3.5" />
        </button>
      </div>
    </aside>
  );
}

