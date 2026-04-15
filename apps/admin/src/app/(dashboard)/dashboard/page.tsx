"use client";

import { useTenants } from "@/hooks/use-api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge, PlanBadge } from "@/components/ui/badge";
import { Plus, Users, Activity, TrendingUp, Zap, ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { formatDate } from "@/lib/utils";
import { CreateTenantDialog } from "@/components/domain/create-tenant-dialog";
import { useState } from "react";

export default function DashboardPage() {
  const { data, isLoading } = useTenants();
  const [showCreate, setShowCreate] = useState(false);

  const tenants = data?.data ?? [];
  const total = data?.pagination?.total_returned ?? 0;
  const active = tenants.filter((t) => t.status === "active").length;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage your NIA AI assistant tenants
            </p>
          </div>
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4 mr-1.5" />
            New Tenant
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: "Total Tenants", value: total, icon: Users, bg: "bg-[#007AFF]/8", fg: "text-[#007AFF]" },
            { label: "Active", value: active, icon: Activity, bg: "bg-[#34C759]/8", fg: "text-[#34C759]" },
            { label: "Professional+", value: tenants.filter((t) => t.plan !== "starter").length, icon: TrendingUp, bg: "bg-[#AF52DE]/8", fg: "text-[#AF52DE]" },
            { label: "Skills Running", value: active * 7, icon: Zap, bg: "bg-[#FF9500]/8", fg: "text-[#FF9500]" },
          ].map(({ label, value, icon: Icon, bg, fg }) => (
            <div key={label} className="rounded-xl border border-black/[0.04] bg-white p-4 shadow-apple transition-shadow hover:shadow-apple-md">
              <div className="flex items-center gap-3">
                <div className={`rounded-xl p-2.5 ${bg}`}>
                  <Icon className={`h-4 w-4 ${fg}`} />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
                  {isLoading ? (
                    <div className="h-6 w-12 rounded-lg bg-muted animate-pulse mt-0.5" />
                  ) : (
                    <p className="text-xl font-semibold tabular-nums tracking-tight">{value}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Tenants list */}
        <div className="space-y-2">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-sm font-semibold">Tenants</h2>
            {!isLoading && tenants.length > 0 && (
              <span className="text-xs text-muted-foreground">{tenants.length} total</span>
            )}
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Loading tenants…</span>
            </div>
          ) : tenants.length === 0 ? (
            <div className="rounded-xl border border-dashed bg-card">
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="rounded-full bg-muted p-4 mb-4">
                  <Users className="h-7 w-7 text-muted-foreground" />
                </div>
                <h3 className="font-semibold mb-1">No tenants yet</h3>
                <p className="text-sm text-muted-foreground max-w-sm mb-4">
                  Create your first tenant to start configuring AI assistants, FSM flows, and knowledge bases.
                </p>
                <Button onClick={() => setShowCreate(true)} size="sm">
                  <Plus className="h-3.5 w-3.5 mr-1.5" />
                  Create Tenant
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-black/[0.04] bg-white shadow-apple overflow-hidden">
              {/* Table header */}
              <div className="grid grid-cols-[1fr_90px_90px_120px_80px] gap-4 px-4 py-2.5 bg-[#f5f5f7] text-[11px] font-medium text-muted-foreground border-b border-black/[0.04]">
                <span>Tenant</span>
                <span>Status</span>
                <span>Plan</span>
                <span className="text-right">Created</span>
                <span />
              </div>
              {tenants.map((tenant, i) => (
                <Link
                  key={tenant.id}
                  href={`/dashboard/tenants/${tenant.id}/config`}
                  className={`grid grid-cols-[1fr_90px_90px_120px_80px] gap-4 items-center px-4 py-3 text-sm hover:bg-black/[0.02] transition-colors group ${
                    i < tenants.length - 1 ? "border-b border-black/[0.04]" : ""
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                      <span className="text-xs font-bold text-primary">
                        {tenant.name[0].toUpperCase()}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{tenant.name}</p>
                      <p className="text-[11px] text-muted-foreground font-mono truncate">{tenant.id}</p>
                    </div>
                  </div>
                  <StatusBadge status={tenant.status} />
                  <PlanBadge plan={tenant.plan} />
                  <p className="text-xs text-muted-foreground text-right">{formatDate(tenant.created_at)}</p>
                  <div className="flex justify-end">
                    <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <CreateTenantDialog open={showCreate} onClose={() => setShowCreate(false)} />
      </div>
    </div>
  );
}
