"use client";

import { useApiKeys, useCreateApiKey } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { APIResponse } from "@/lib/api";
import { useState } from "react";
import { Copy, KeyRound, Plus } from "lucide-react";
import { toast } from "sonner";

export function ApiKeysPanel({ tenantId }: { tenantId: string }) {
  const { data, isLoading } = useApiKeys(tenantId);
  const create = useCreateApiKey(tenantId);
  const [newKeyValue, setNewKeyValue] = useState<string | null>(null);

  const keys = data?.data ?? [];

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  const handleCreate = () => {
    create.mutate("New key", {
      onSuccess: (res: APIResponse<{ api_key: string; prefix: string }>) => {
        // The full api_key is only returned at creation time
        if (res?.data?.api_key) {
          setNewKeyValue(res.data.api_key);
        }
      },
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>API Keys</CardTitle>
            <CardDescription>Manage access credentials for this tenant</CardDescription>
          </div>
          <Button
            size="sm"
            onClick={handleCreate}
            disabled={create.isPending}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            New Key
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* One-time key reveal banner */}
        {newKeyValue && (
          <div className="rounded-xl border border-[#FF9500]/20 bg-[#FF9500]/5 p-3 text-sm">
            <p className="font-medium text-[#FF9500] mb-1">
              Copy your new API key — it won&apos;t be shown again
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 font-mono text-xs break-all select-all">
                {newKeyValue}
              </code>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={() => copyToClipboard(newKeyValue)}
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="text-sm text-muted-foreground py-4 text-center">Loading…</div>
        ) : keys.length === 0 ? (
          <div className="text-sm text-muted-foreground py-4 text-center">No API keys yet</div>
        ) : (
          <div className="space-y-3">
            {keys.map((k) => (
              <div
                key={k.id}
                className="flex items-center gap-3 rounded-lg border p-3 text-sm"
              >
                <KeyRound className="h-4 w-4 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{k.label ?? "API Key"}</div>
                  <div className="font-mono text-xs text-muted-foreground mt-0.5">
                    {k.prefix}{"•".repeat(24)}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    Created {new Date(k.created_at).toLocaleDateString()}
                    {k.last_used_at && ` · Last used ${new Date(k.last_used_at).toLocaleDateString()}`}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Badge variant="secondary">Active</Badge>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => copyToClipboard(k.prefix)}
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
