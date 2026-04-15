"use client";

import { use, useCallback, useRef, useState, type DragEvent } from "react";
import {
  useRagStats,
  useIngestDocument,
  useRagDocuments,
  useRagDocumentChunks,
  useDeleteRagDocument,
  useTestRagQuery,
} from "@/hooks/use-api";
import type { RAGDocument, RAGChunk } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import {
  Upload,
  FileText,
  Database,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Trash2,
  Search,
  BookOpen,
  Hash,
  Layers,
  MessageSquare,
  Send,
  Eye,
  BarChart3,
  Info,
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
  const { data: docsData, isLoading: docsLoading } = useRagDocuments(tenantId);
  const ingest = useIngestDocument(tenantId);
  const deleteDoc = useDeleteRagDocument(tenantId);
  const testQuery = useTestRagQuery(tenantId);

  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState<string[]>([]);
  const [done, setDone] = useState<string[]>([]);
  const [failed, setFailed] = useState<string[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<RAGDocument | null>(null);
  const [queryText, setQueryText] = useState("");
  const [queryResult, setQueryResult] = useState<{
    answer: string;
    confidence_score: number;
    chunks_used: { text?: string; score?: number; source?: string }[];
  } | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<RAGDocument | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const stats = statsData?.data;
  const documents: RAGDocument[] = docsData?.data ?? [];

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const fileArr = Array.from(files);
      for (const file of fileArr) {
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (!ACCEPTED.includes(ext)) {
          toast.error(`Unsupported file type: ${file.name}`);
          setFailed((f) => [...f, file.name]);
          continue;
        }
        setUploading((u) => [...u, file.name]);
        try {
          await ingest.mutateAsync({ file });
          setDone((d) => [...d, file.name]);
        } catch {
          setFailed((f) => [...f, file.name]);
          toast.error(`Failed to ingest: ${file.name}`);
        } finally {
          setUploading((u) => u.filter((n) => n !== file.name));
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

  async function handleTestQuery() {
    if (!queryText.trim()) return;
    const res = await testQuery.mutateAsync(queryText.trim());
    setQueryResult(res.data);
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage your RAG document collection — upload, browse, and test queries.
            </p>
          </div>
          <Button variant="ghost" size="sm" className="text-xs" onClick={() => refetch()}>
            <RefreshCw className="h-3 w-3 mr-1" />
            Refresh
          </Button>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-3">
          <StatCard
            icon={<Database className="h-4 w-4" />}
            label="Collection"
            value={stats?.collection_name ?? "—"}
            loading={statsLoading}
          />
          <StatCard
            icon={<Layers className="h-4 w-4" />}
            label="Vectors"
            value={stats?.vectors_count?.toLocaleString() ?? "0"}
            loading={statsLoading}
          />
          <StatCard
            icon={<Hash className="h-4 w-4" />}
            label="Points"
            value={stats?.points_count?.toLocaleString() ?? "0"}
            loading={statsLoading}
          />
          <StatCard
            icon={<FileText className="h-4 w-4" />}
            label="Documents"
            value={documents.length.toString()}
            loading={docsLoading}
          />
        </div>

        {/* Main tabs */}
        <Tabs defaultValue="documents" className="space-y-4">
          <TabsList>
            <TabsTrigger value="documents" className="text-xs">
              <BookOpen className="h-3.5 w-3.5 mr-1.5" />
              Documents
            </TabsTrigger>
            <TabsTrigger value="upload" className="text-xs">
              <Upload className="h-3.5 w-3.5 mr-1.5" />
              Upload
            </TabsTrigger>
            <TabsTrigger value="test" className="text-xs">
              <Search className="h-3.5 w-3.5 mr-1.5" />
              Test Query
            </TabsTrigger>
          </TabsList>

          {/* ── Documents tab ─────────────────────────── */}
          <TabsContent value="documents" className="space-y-3">
            {docsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Loading documents…</span>
              </div>
            ) : documents.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="rounded-full bg-muted p-4 mb-4">
                    <BookOpen className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <h3 className="font-semibold mb-1">No documents yet</h3>
                  <p className="text-sm text-muted-foreground max-w-sm">
                    Upload .txt, .md, .json, .pdf, or .csv files to build your knowledge base.
                    Documents are automatically chunked and embedded for semantic search.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="rounded-lg border overflow-hidden">
                {/* Table header */}
                <div className="grid grid-cols-[1fr_100px_100px_80px] gap-4 px-4 py-2 bg-muted/50 text-xs font-medium text-muted-foreground border-b">
                  <span>Document</span>
                  <span className="text-right">Chunks</span>
                  <span className="text-right">Tokens</span>
                  <span />
                </div>
                {documents.map((doc, i) => (
                  <div
                    key={doc.doc_id}
                    className={cn(
                      "grid grid-cols-[1fr_100px_100px_80px] gap-4 items-center px-4 py-3 text-sm hover:bg-black/[0.02] transition-colors group",
                      i < documents.length - 1 && "border-b"
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="rounded-lg bg-[#007AFF]/8 p-1.5 shrink-0">
                        <FileText className="h-3.5 w-3.5 text-[#007AFF]" />
                      </div>
                      <span className="font-medium truncate text-sm">{doc.filename}</span>
                    </div>
                    <span className="text-right text-muted-foreground tabular-nums">{doc.chunks_count}</span>
                    <span className="text-right text-muted-foreground tabular-nums">~{doc.total_tokens.toLocaleString()}</span>
                    <div className="flex items-center justify-end gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => setSelectedDoc(doc)}
                        title="View chunks"
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive hover:text-destructive"
                        onClick={() => setDeleteConfirm(doc)}
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* ── Upload tab ────────────────────────────── */}
          <TabsContent value="upload" className="space-y-4">
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={onDrop}
              onClick={() => inputRef.current?.click()}
              className={cn(
                "relative flex flex-col items-center justify-center gap-3",
                "rounded-xl border-2 border-dashed p-10 text-center cursor-pointer",
                "transition-all duration-200 select-none",
                isDragOver
                  ? "border-primary bg-primary/5 scale-[1.005]"
                  : "border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-muted/20"
              )}
            >
              <div className={cn("rounded-full p-3", isDragOver ? "bg-primary/10" : "bg-muted")}>
                <Upload className={cn("h-6 w-6", isDragOver ? "text-primary" : "text-muted-foreground")} />
              </div>
              <div>
                <p className="font-medium text-sm">
                  {isDragOver ? "Drop files here" : "Drag & drop files, or click to browse"}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Supports {ACCEPTED.join(", ")} — multiple files
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

            {/* File status */}
            {(uploading.length > 0 || done.length > 0 || failed.length > 0) && (
              <div className="space-y-1.5">
                {uploading.map((name) => (
                  <FileStatusRow key={name} name={name} status="uploading" />
                ))}
                {done.map((name) => (
                  <FileStatusRow key={name} name={name} status="done" />
                ))}
                {failed.map((name) => (
                  <FileStatusRow key={name} name={name} status="failed" />
                ))}
              </div>
            )}

            {/* Tips */}
            <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Info className="h-4 w-4 text-muted-foreground" />
                Ingestion Tips
              </div>
              <div className="text-xs text-muted-foreground space-y-1.5 pl-6">
                <p>• Documents are automatically chunked (~400 tokens) with overlap for context preservation.</p>
                <p>• <strong>.md</strong> files preserve heading structure — ideal for knowledge articles.</p>
                <p>• <strong>.json</strong> files are auto-detected: each top-level object becomes one chunk.</p>
                <p>• <strong>.csv</strong> and <strong>.txt</strong> FAQ sheets provide best recall for Q&A.</p>
                <p>• To <strong>replace</strong> a document, delete it first then re-upload.</p>
              </div>
            </div>
          </TabsContent>

          {/* ── Test query tab ─────────────────────────── */}
          <TabsContent value="test" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Search className="h-4 w-4" />
                  Test RAG Query
                </CardTitle>
                <CardDescription>
                  Ask a question to see how the knowledge base responds, including which chunks were retrieved and confidence scores.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    placeholder="e.g. ¿Cuál es el horario de la viña?"
                    value={queryText}
                    onChange={(e) => setQueryText(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleTestQuery()}
                    className="text-sm"
                  />
                  <Button
                    onClick={handleTestQuery}
                    disabled={!queryText.trim() || testQuery.isPending}
                    loading={testQuery.isPending}
                  >
                    <Send className="h-4 w-4 mr-1.5" />
                    Ask
                  </Button>
                </div>

                {queryResult && (
                  <div className="space-y-3">
                    {/* Answer */}
                    <div className="rounded-xl border border-[#34C759]/15 bg-[#34C759]/5 p-4">
                      <div className="flex items-center gap-2 text-xs font-medium text-[#34C759] mb-2">
                        <MessageSquare className="h-3.5 w-3.5" />
                        Answer
                        <Badge variant="secondary" className="ml-auto text-[10px]">
                          Confidence: {(queryResult.confidence_score * 100).toFixed(0)}%
                        </Badge>
                      </div>
                      <p className="text-sm leading-relaxed">{queryResult.answer}</p>
                    </div>

                    {/* Chunks used */}
                    {queryResult.chunks_used?.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                          <BarChart3 className="h-3.5 w-3.5" />
                          Retrieved Chunks ({queryResult.chunks_used.length})
                        </div>
                        {queryResult.chunks_used.map((chunk, i) => (
                          <div key={i} className="rounded-md border bg-muted/30 p-3 text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-muted-foreground">#{i + 1}</span>
                              {chunk.score != null && (
                                <Badge variant="secondary" className="text-[10px]">
                                  score: {typeof chunk.score === "number" ? chunk.score.toFixed(3) : chunk.score}
                                </Badge>
                              )}
                            </div>
                            <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">
                              {chunk.text ?? JSON.stringify(chunk)}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* ── Chunk viewer dialog ──────────────────────────── */}
      {selectedDoc && (
        <ChunkViewerDialog
          tenantId={tenantId}
          doc={selectedDoc}
          onClose={() => setSelectedDoc(null)}
        />
      )}

      {/* ── Delete confirm dialog ────────────────────────── */}
      <Dialog open={!!deleteConfirm} onOpenChange={(o) => !o && setDeleteConfirm(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Document</DialogTitle>
            <DialogDescription>
              This will permanently remove <strong>{deleteConfirm?.filename}</strong> and
              all {deleteConfirm?.chunks_count} chunks. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button
              variant="destructive"
              loading={deleteDoc.isPending}
              onClick={async () => {
                if (!deleteConfirm) return;
                await deleteDoc.mutateAsync(deleteConfirm.doc_id);
                setDeleteConfirm(null);
              }}
            >
              <Trash2 className="h-3.5 w-3.5 mr-1.5" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Chunk viewer dialog ───────────────────────────────────────

function ChunkViewerDialog({
  tenantId,
  doc,
  onClose,
}: {
  tenantId: string;
  doc: RAGDocument;
  onClose: () => void;
}) {
  const { data: chunksData, isLoading } = useRagDocumentChunks(tenantId, doc.doc_id);
  const chunks: RAGChunk[] = chunksData?.data ?? [];

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4 text-[#007AFF]" />
            {doc.filename}
          </DialogTitle>
          <DialogDescription>
            {doc.chunks_count} chunks · ~{doc.total_tokens.toLocaleString()} tokens
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-2 min-h-0 pr-1">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : chunks.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No chunks found. The document may have been deleted.
            </p>
          ) : (
            chunks.map((chunk) => (
              <div key={chunk.chunk_id} className="rounded-lg border p-3 space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <span className="font-mono font-medium">Chunk #{chunk.chunk_index}</span>
                    {chunk.section && <span className="text-slate-400">· {chunk.section}</span>}
                  </div>
                  <Badge variant="secondary" className="text-[10px]">
                    {chunk.tokens} tokens
                  </Badge>
                </div>
                <p className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto">
                  {chunk.text}
                </p>
              </div>
            ))
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Shared components ─────────────────────────────────────────

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
    <div className="rounded-xl border bg-card p-4 transition-colors hover:bg-accent/30">
      <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1.5">
        {icon}
        {label}
      </div>
      {loading ? (
        <div className="h-5 w-20 rounded bg-muted animate-pulse" />
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
    <div className="flex items-center gap-2.5 text-xs rounded-lg border px-3 py-2.5">
      {status === "uploading" && <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin shrink-0" />}
      {status === "done" && <CheckCircle2 className="h-3.5 w-3.5 text-[#34C759] shrink-0" />}
      {status === "failed" && <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0" />}
      <span className="font-mono truncate flex-1">{name}</span>
      <span className={cn(
        "text-[10px] font-medium",
        status === "uploading" ? "text-[#007AFF]" :
        status === "done" ? "text-[#34C759]" :
        "text-destructive"
      )}>
        {status === "uploading" ? "Processing…" : status === "done" ? "Ingested" : "Failed"}
      </span>
    </div>
  );
}
