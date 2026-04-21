"use client";

import { useTenant } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

interface TenantHeaderProps {
  tenantId: string;
}

export function TenantHeader({ tenantId }: TenantHeaderProps) {
  const { data: tenantData } = useTenant(tenantId);
  const tenant = tenantData?.data;

  const planLabels: Record<string, string> = { starter: "Starter", pro: "Pro", enterprise: "Enterprise" };

  return (
    <header className="flex items-center gap-3 px-6 h-12 shrink-0 border-b border-border bg-background/80 backdrop-blur-sm">
      {/* Tenant name + badges */}
      <div className="flex items-center gap-2.5 flex-1 min-w-0">
        <span className="text-[13px] font-semibold text-foreground truncate">
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
    </header>
  );
}
