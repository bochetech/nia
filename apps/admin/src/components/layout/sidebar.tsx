"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import {
  LayoutDashboard,
  Users,
  GitBranch,
  Zap,
  BookOpen,
  BarChart2,
  Puzzle,
  LogOut,
  ChevronRight,
  Bot,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Overview" },
  { href: "/dashboard/tenants", icon: Users, label: "Tenants" },
];

const TENANT_NAV = (id: string) => [
  { href: `/dashboard/tenants/${id}/config`, icon: Bot, label: "Configuration" },
  { href: `/dashboard/tenants/${id}/fsm`, icon: GitBranch, label: "FSM Flow" },
  { href: `/dashboard/tenants/${id}/skills`, icon: Zap, label: "Skills" },
  { href: `/dashboard/tenants/${id}/knowledge`, icon: BookOpen, label: "Knowledge" },
  { href: `/dashboard/tenants/${id}/analytics`, icon: BarChart2, label: "Analytics" },
  { href: `/dashboard/tenants/${id}/channels`, icon: Puzzle, label: "Channels" },
];

export function Sidebar({ tenantId: tenantIdProp }: { tenantId?: string }) {
  const pathname = usePathname();
  const { data: session } = useSession();

  // Auto-detect tenantId from URL if not passed as prop
  const tenantIdMatch = pathname.match(/\/dashboard\/tenants\/([^/]+)/);
  const tenantId = tenantIdProp ?? tenantIdMatch?.[1];

  return (
    <aside className="flex h-screen w-56 flex-col bg-sidebar border-r border-sidebar-border">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-sidebar-border">
        <div className="h-7 w-7 rounded-lg bg-primary flex items-center justify-center">
          <span className="text-white font-bold text-sm">N</span>
        </div>
        <span className="font-semibold text-sidebar-foreground text-sm tracking-tight">
          NIA Admin
        </span>
      </div>

      {/* Main nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors",
              pathname === href
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </Link>
        ))}

        {/* Per-tenant nav */}
        {tenantId && (
          <div className="mt-4 pt-4 border-t border-sidebar-border">
            <p className="px-2.5 mb-1.5 text-xs font-semibold text-sidebar-foreground/40 uppercase tracking-wider">
              Tenant
            </p>
            {TENANT_NAV(tenantId).map(({ href, icon: Icon, label }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors",
                  pathname.startsWith(href)
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
                )}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                {label}
                {pathname.startsWith(href) && (
                  <ChevronRight className="ml-auto h-3 w-3 opacity-50" />
                )}
              </Link>
            ))}
          </div>
        )}
      </nav>

      {/* User */}
      <div className="border-t border-sidebar-border px-3 py-3">
        <div className="flex items-center gap-2.5 rounded-md px-2.5 py-2">
          <div className="h-7 w-7 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-bold text-primary">
              {(session?.user?.email ?? "A")[0].toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-sidebar-foreground truncate">
              {session?.user?.email ?? "admin"}
            </p>
            <p className="text-xs text-sidebar-foreground/40">Super Admin</p>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="text-sidebar-foreground/40 hover:text-sidebar-foreground transition-colors"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
