"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning";
}

const badgeVariants = {
  default: "bg-primary/10 text-primary border-primary/20",
  secondary: "bg-secondary text-secondary-foreground border-secondary",
  destructive: "bg-destructive/10 text-destructive border-destructive/20",
  outline: "bg-transparent text-foreground border-border",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400",
  warning: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-400",
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold transition-colors",
        badgeVariants[variant],
        className
      )}
      {...props}
    />
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; variant: BadgeProps["variant"] }> = {
    active: { label: "Active", variant: "success" },
    suspended: { label: "Suspended", variant: "destructive" },
    provisioning: { label: "Provisioning", variant: "warning" },
  };
  const { label, variant } = map[status] ?? { label: status, variant: "outline" };
  return <Badge variant={variant}>{label}</Badge>;
}

export function PlanBadge({ plan }: { plan: string }) {
  const map: Record<string, { label: string; variant: BadgeProps["variant"] }> = {
    starter: { label: "Starter", variant: "secondary" },
    professional: { label: "Professional", variant: "default" },
    enterprise: { label: "Enterprise", variant: "warning" },
  };
  const { label, variant } = map[plan] ?? { label: plan, variant: "outline" };
  return <Badge variant={variant}>{label}</Badge>;
}
