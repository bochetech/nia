"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, Save, PauseCircle } from "lucide-react";
import { useTenant } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

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

  return (
    <header className="flex flex-col shrink-0 bg-sidebar border-b border-border">

      {/* Top bar */}
      <div className="flex items-center gap-3 px-5 pt-3 pb-2">
        <Link
          href="/dashboard"
          className="flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-primary transition-colors"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Tenants
        </Link>

        <span className="text-border text-[12px]">/</span>

        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <span className="text-[13px] font-medium text-foreground truncate">
            {tenant?.name ?? tenantId}
          </span>

          <span className="text-[9px] font-mono text-muted-foreground bg-muted rounded px-1.5 py-0.5">
            {tenantId}
          </span>

          {tenant?.plan && (
            <span className="text-[10px] rounded px-1.5 py-0.5 bg-primary/10 text-primary">
              {planLabels[tenant.plan] ?? tenant.plan}
            </span>
          )}

          {tenant?.status && (
            <span className={cn(
              "text-[10px] rounded px-1.5 py-0.5",
              tenant.status === "active"
                ? "bg-emerald-500/10 text-emerald-500"
                : "bg-destructive/10 text-destructive",
            )}>
              {tenant.status}
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium text-muted-foreground bg-muted border border-border hover:opacity-80 transition-opacity cursor-pointer">
            <PauseCircle className="h-3.5 w-3.5" />
            Suspend
          </button>
          <button
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium text-white hover:opacity-80 transition-opacity cursor-pointer border-0"
            style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-end gap-0 px-5">
        {TABS(tenantId).map(({ href, label }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "px-4 py-2 text-[13px] transition-colors whitespace-nowrap border-b-2",
                active
                  ? "text-primary border-primary font-medium"
                  : "text-muted-foreground border-transparent hover:text-foreground",
              )}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
