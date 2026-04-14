"use client";

import { use, useCallback, useRef, useState, type DragEvent } from "react";
import { useRagStats, useIngestDocument } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Upload,
  FileText,
  Database,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

const ACCEPTED = [".txt", ".md", ".json", ".pdf", ".csv"];

export default function KnowledgePage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  const { data: statsData, isLoading: statsLoading, refetch } = useRagStats(tenantId);
  const ingest = useIngestDocument(tenantId);

  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState<string[]>([]);
  const [done, setDone] = useState<string[]>([]);
  const [failed, setFailed] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const stats = statsData?.data;

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const fileArr = Array.from(files);
      for (const file of fileArr) {
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (!ACCEPTED.includes(ext)) {
          toast.error(`Unsupported file type: ${file.name}`);
          setFailed((f: string[]) => [...f, file.name]);
          continue;
        }
        setUploading((u: string[]) => [...u, file.name]);
        try {
          await ingest.mutateAsync({ file });
          setDone((d: string[]) => [...d, file.name]);
        } catch {
          setFailed((f: string[]) => [...f, file.name]);
          toast.error(`Failed to ingest: ${file.name}`);
        } finally {
          setUploading((u: string[]) => u.filter((n: string) => n !== file.name));
        }
      }
      await refetch();
    },
    [ingest, refetch]
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
      }
    },
    [handleFiles]
  );

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Knowledge Base</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage documents ingested into the RAG vector store for this tenant
        </p>
      </div>

      {/* Stats card */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          icon={<Database className="h-4 w-4" />}
          label="Collection"
          value={stats?.collection_name ?? "—"}
          loading={statsLoading}
        />
        <StatCard
          icon={<FileText className="h-4 w-4" />}
          label="Vectors"
          value={stats?.vectors_count?.toLocaleString() ?? "—"}
          loading={statsLoading}
        />
        <StatCard
          icon={<Database className="h-4 w-4" />}
          label="Points"
          value={stats?.points_count?.toLocaleString() ?? "—"}
          loading={statsLoading}
        />
      </div>

      {stats && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Status:</span>
          <Badge
            variant={
              stats.status === "green"
                ? "success"
                : stats.status === "yellow"
                ? "warning"
                : "destructive"
            }
          >
            {stats.status ?? "unknown"}
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto h-7 text-xs"
            onClick={() => refetch()}
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            Refresh
          </Button>
        </div>
      )}

      {/* Upload zone */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Documents</CardTitle>
          <CardDescription>
            Supported formats: {ACCEPTED.join(", ")}. Files are chunked and embedded automatically.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={`
              relative flex flex-col items-center justify-center gap-3
              rounded-xl border-2 border-dashed p-12 text-center cursor-pointer
              transition-all duration-200 select-none
              ${isDragOver
                ? "border-primary bg-primary/5 scale-[1.01]"
                : "border-muted-foreground/30 hover:border-muted-foreground/60 hover:bg-muted/30"
              }
            `}
          >
            <div className={`rounded-full p-3 ${isDragOver ? "bg-primary/10" : "bg-muted"}`}>
              <Upload className={`h-6 w-6 ${isDragOver ? "text-primary" : "text-muted-foreground"}`} />
            </div>
            <div>
              <p className="font-medium text-sm">
                {isDragOver ? "Drop files here" : "Drag & drop files, or click to browse"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Multiple files supported
              </p>
            </div>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept={ACCEPTED.join(",")}
              className="hidden"
              onChange={(e) => e.target.files && handleFiles(e.target.files)}
            />
          </div>

          {/* File status list */}
          {(uploading.length > 0 || done.length > 0 || failed.length > 0) && (
            <div className="mt-4 space-y-1.5">
              {uploading.map((name) => (
                <FileStatusRow
                  key={name}
                  name={name}
                  status="uploading"
                />
              ))}
              {done.map((name) => (
                <FileStatusRow key={name} name={name} status="done" />
              ))}
              {failed.map((name) => (
                <FileStatusRow key={name} name={name} status="failed" />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tips</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>• Documents are automatically chunked (512 tokens) with 64-token overlap.</p>
          <p>• Use <strong>.md</strong> files for structured knowledge articles.</p>
          <p>• Upload FAQ sheets as <strong>.txt</strong> or <strong>.csv</strong> for best recall.</p>
          <p>• Re-uploading a file with the same name will create additional chunks — delete the collection first to replace.</p>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  loading,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  loading: boolean;
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
        {icon}
        {label}
      </div>
      {loading ? (
        <div className="h-5 w-16 rounded bg-muted animate-pulse" />
      ) : (
        <div className="font-semibold text-sm truncate">{value}</div>
      )}
    </div>
  );
}

function FileStatusRow({
  name,
  status,
}: {
  name: string;
  status: "uploading" | "done" | "failed";
}) {
  return (
    <div className="flex items-center gap-2.5 text-xs rounded-md border px-3 py-2">
      {status === "uploading" && <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin shrink-0" />}
      {status === "done" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />}
      {status === "failed" && <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0" />}
      <span className="font-mono truncate flex-1">{name}</span>
      <span className={
        status === "uploading" ? "text-blue-500" :
        status === "done" ? "text-emerald-600" :
        "text-destructive"
      }>
        {status === "uploading" ? "Processing…" : status === "done" ? "Ingested" : "Failed"}
      </span>
    </div>
  );
}
