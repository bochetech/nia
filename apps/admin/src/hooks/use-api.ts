"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { tenantManagerApi, ragApi } from "@/lib/api";
import type {
  Tenant,
  UIConfig,
  AIConfig,
  TelegramConfig,
  TeamsConfig,
  PaymentConfig,
  FSMConfig,
  IntentDefinition,
  FlowTransition,
  SkillConfig,
} from "@/lib/api";
import { toast } from "sonner";

function useToken(): string {
  const { data: session } = useSession();
  return (session as any)?.accessToken ?? "";
}

// ---------------------------------------------------------------------------
// Tenants
// ---------------------------------------------------------------------------

export function useTenants(page = 1, pageSize = 20) {
  const token = useToken();
  return useQuery({
    queryKey: ["tenants", page, pageSize],
    queryFn: () => tenantManagerApi.listTenants(token, page, pageSize),
    enabled: !!token,
  });
}

export function useTenant(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["tenant", tenantId],
    queryFn: () => tenantManagerApi.getTenant(token, tenantId),
    enabled: !!token && !!tenantId,
  });
}

export function useTenantConfig(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["tenantConfig", tenantId],
    queryFn: () => tenantManagerApi.getTenantConfig(token, tenantId),
    enabled: !!token && !!tenantId,
  });
}

export function useCreateTenant() {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof tenantManagerApi.createTenant>[1]) =>
      tenantManagerApi.createTenant(token, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      toast.success("Tenant created successfully");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateTenant(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Tenant>) =>
      tenantManagerApi.updateTenant(token, tenantId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenant", tenantId] });
      qc.invalidateQueries({ queryKey: ["tenants"] });
      toast.success("Tenant updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useSuspendTenant(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => tenantManagerApi.suspendTenant(token, tenantId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      toast.success("Tenant suspended");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ---------------------------------------------------------------------------
// API Keys
// ---------------------------------------------------------------------------

export function useApiKeys(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["apiKeys", tenantId],
    queryFn: () => tenantManagerApi.listApiKeys(token, tenantId),
    enabled: !!token && !!tenantId,
  });
}

export function useCreateApiKey(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label: string) =>
      tenantManagerApi.createApiKey(token, tenantId, label),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["apiKeys", tenantId] });
      toast.success("API key created");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ---------------------------------------------------------------------------
// Intents
// ---------------------------------------------------------------------------

export function useIntents(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["intents", tenantId],
    queryFn: () => tenantManagerApi.listIntents(token, tenantId),
    enabled: !!token && !!tenantId,
  });
}

export function useCreateIntent(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (intent: IntentDefinition) =>
      tenantManagerApi.createIntent(token, tenantId, intent),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intents", tenantId] });
      toast.success("Intent created");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateIntent(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, updates }: { key: string; updates: Partial<IntentDefinition> }) =>
      tenantManagerApi.updateIntent(token, tenantId, key, updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intents", tenantId] });
      toast.success("Intent updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteIntent(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) =>
      tenantManagerApi.deleteIntent(token, tenantId, key),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intents", tenantId] });
      toast.success("Intent deleted");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ---------------------------------------------------------------------------
// Actions (catalog — read only)
// ---------------------------------------------------------------------------

export function useActions(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["actions", tenantId],
    queryFn: () => tenantManagerApi.listActions(token, tenantId),
    enabled: !!token && !!tenantId,
    staleTime: Infinity, // actions are static
  });
}

export function useFSMStates(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["fsmStates", tenantId],
    queryFn: () => tenantManagerApi.listFSMStates(token, tenantId),
    enabled: !!token && !!tenantId,
    staleTime: 30_000,
  });
}

export function useCreateFSMState(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, label }: { key: string; label: string }) =>
      tenantManagerApi.createFSMState(token, tenantId, key, label),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fsmStates", tenantId] });
      toast.success("State created");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteFSMState(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (stateKey: string) =>
      tenantManagerApi.deleteFSMState(token, tenantId, stateKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fsmStates", tenantId] });
      toast.success("State deleted");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ---------------------------------------------------------------------------
// Transitions
// ---------------------------------------------------------------------------

export function useTransitions(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["transitions", tenantId],
    queryFn: () => tenantManagerApi.listTransitions(token, tenantId),
    enabled: !!token && !!tenantId,
  });
}

export function useReplaceTransitions(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (transitions: FlowTransition[]) =>
      tenantManagerApi.replaceTransitions(token, tenantId, transitions),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transitions", tenantId] });
      toast.success("Flow saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ---------------------------------------------------------------------------
// Skills
// ---------------------------------------------------------------------------

export function useSkills(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["skills", tenantId],
    queryFn: () => tenantManagerApi.listSkills(token, tenantId),
    enabled: !!token && !!tenantId,
  });
}

export function useUpsertSkill(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ actionKey, skill }: { actionKey: string; skill: SkillConfig }) =>
      tenantManagerApi.upsertSkill(token, tenantId, actionKey, skill),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["skills", tenantId] });
      toast.success("Skill configuration saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useDeleteSkill(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (actionKey: string) =>
      tenantManagerApi.deleteSkill(token, tenantId, actionKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["skills", tenantId] });
      toast.success("Skill deleted");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ---------------------------------------------------------------------------
// Config patches
// ---------------------------------------------------------------------------

export function useUpdateUIConfig(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<UIConfig>) =>
      tenantManagerApi.updateUIConfig(token, tenantId, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenantConfig", tenantId] });
      toast.success("UI config saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateAIConfig(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<AIConfig>) =>
      tenantManagerApi.updateAIConfig(token, tenantId, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenantConfig", tenantId] });
      toast.success("AI config saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateTelegramConfig(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<TelegramConfig>) =>
      tenantManagerApi.updateTelegramConfig(token, tenantId, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenantConfig", tenantId] });
      toast.success("Telegram config saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdateTeamsConfig(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<TeamsConfig>) =>
      tenantManagerApi.updateTeamsConfig(token, tenantId, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenantConfig", tenantId] });
      toast.success("Teams config saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useUpdatePaymentConfig(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<PaymentConfig>) =>
      tenantManagerApi.updatePaymentConfig(token, tenantId, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenantConfig", tenantId] });
      toast.success("Payment config saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export function useAnalytics(tenantId: string, days = 30) {
  const token = useToken();
  return useQuery({
    queryKey: ["analytics", tenantId, days],
    queryFn: () => tenantManagerApi.getAnalytics(token, tenantId, days),
    enabled: !!token && !!tenantId,
    refetchInterval: 60_000, // refresh every minute
  });
}

export function useSessions(tenantId: string, page = 1, pageSize = 20, days = 30) {
  const token = useToken();
  return useQuery({
    queryKey: ["sessions", tenantId, page, pageSize, days],
    queryFn: () => tenantManagerApi.listSessions(token, tenantId, page, pageSize, days),
    enabled: !!token && !!tenantId,
  });
}

export function useRagStats(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["ragStats", tenantId],
    queryFn: () => tenantManagerApi.getRagStats(token, tenantId),
    enabled: !!token && !!tenantId,
    refetchInterval: 30_000,
  });
}

// ---------------------------------------------------------------------------
// RAG Ingest
// ---------------------------------------------------------------------------

export function useIngestDocument(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, collectionName }: { file: File; collectionName?: string }) =>
      ragApi.ingest(token, tenantId, file, collectionName),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["ragStats", tenantId] });
      qc.invalidateQueries({ queryKey: ["ragDocuments", tenantId] });
      toast.success(`Ingested ${res.data.chunks_created} chunks from "${res.data.filename}"`);
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useRagDocuments(tenantId: string) {
  const token = useToken();
  return useQuery({
    queryKey: ["ragDocuments", tenantId],
    queryFn: () => ragApi.listDocuments(token, tenantId),
    enabled: !!token && !!tenantId,
    refetchInterval: 30_000,
  });
}

export function useRagDocumentChunks(tenantId: string, docId: string | null) {
  const token = useToken();
  return useQuery({
    queryKey: ["ragChunks", tenantId, docId],
    queryFn: () => ragApi.getDocumentChunks(token, docId!, tenantId),
    enabled: !!token && !!tenantId && !!docId,
  });
}

export function useDeleteRagDocument(tenantId: string) {
  const token = useToken();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) => ragApi.deleteDocument(token, docId, tenantId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ragStats", tenantId] });
      qc.invalidateQueries({ queryKey: ["ragDocuments", tenantId] });
      toast.success("Document deleted");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useTestRagQuery(tenantId: string) {
  const token = useToken();
  return useMutation({
    mutationFn: (query: string) => ragApi.testQuery(token, tenantId, query),
    onError: (e: Error) => toast.error(e.message),
  });
}
