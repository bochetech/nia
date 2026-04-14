"use client";

import { useTenants } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge, PlanBadge } from "@/components/ui/badge";
import { Plus, Users, Activity, TrendingUp, Zap } from "lucide-react";
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
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Overview</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage your NIA AI assistant tenants
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" />
          New Tenant
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Tenants", value: total, icon: Users, color: "text-blue-500" },
          { label: "Active", value: active, icon: Activity, color: "text-emerald-500" },
          { label: "Professional+", value: tenants.filter((t) => t.plan !== "starter").length, icon: TrendingUp, color: "text-violet-500" },
          { label: "Skills Running", value: active * 7, icon: Zap, color: "text-amber-500" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{label}</p>
                  <p className="text-2xl font-bold mt-1">
                    {isLoading ? "—" : value}
                  </p>
                </div>
                <Icon className={`h-8 w-8 ${color} opacity-80`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tenants table */}
      <Card>
        <CardHeader>
          <CardTitle>Tenants</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground text-sm">Loading…</div>
          ) : tenants.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">
              No tenants yet.{" "}
              <button
                onClick={() => setShowCreate(true)}
                className="text-primary hover:underline"
              >
                Create your first tenant
              </button>
            </div>
          ) : (
            <div className="divide-y">
              {tenants.map((tenant) => (
                <div
                  key={tenant.id}
                  className="flex items-center gap-4 px-6 py-4 hover:bg-muted/30 transition-colors"
                >
                  <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-primary">
                      {tenant.name[0].toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{tenant.name}</p>
                    <p className="text-xs text-muted-foreground">{tenant.id}</p>
                  </div>
                  <StatusBadge status={tenant.status} />
                  <PlanBadge plan={tenant.plan} />
                  <p className="text-xs text-muted-foreground hidden md:block w-32 text-right">
                    {formatDate(tenant.created_at)}
                  </p>
                  <Link
                    href={`/dashboard/tenants/${tenant.id}/config`}
                    className="ml-2"
                  >
                    <Button variant="outline" size="sm">
                      Manage
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <CreateTenantDialog open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  );
}
