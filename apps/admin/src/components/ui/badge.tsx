"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning";
}

const badgeVariants = {
  default: "bg-primary/8 text-primary border-transparent",
  secondary: "bg-secondary text-secondary-foreground border-transparent",
  destructive: "bg-red-50 text-red-600 border-transparent dark:bg-red-950 dark:text-red-400",
  outline: "bg-transparent text-muted-foreground border-border",
  success: "bg-emerald-50 text-emerald-600 border-transparent dark:bg-emerald-950 dark:text-emerald-400",
  warning: "bg-orange-50 text-orange-600 border-transparent dark:bg-orange-950 dark:text-orange-400",
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-tight transition-colors",
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
