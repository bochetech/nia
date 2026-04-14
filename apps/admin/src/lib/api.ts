/**
 * Typed API client for NIA microservices.
 * Uses openapi-fetch with runtime URL composition.
 */

const TENANT_MANAGER =
  process.env.NEXT_PUBLIC_TENANT_MANAGER_URL ?? "http://localhost:8003";
const ORCHESTRATOR =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ?? "http://localhost:8001";
const RAG_URL = process.env.NEXT_PUBLIC_RAG_URL ?? "http://localhost:8002";
const TRANSCRIPT_URL =
  process.env.NEXT_PUBLIC_TRANSCRIPT_URL ?? "http://localhost:8008";

// ---------------------------------------------------------------------------
// Base fetch helper — injects Authorization header automatically
// ---------------------------------------------------------------------------

async function apiFetch(
  url: string,
  options: RequestInit & { token?: string } = {}
): Promise<Response> {
  const { token, ...init } = options;
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(url, { ...init, headers });
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API response wrapper matching the backend APIResponse / PaginatedResponse
// ---------------------------------------------------------------------------

export interface APIResponse<T> {
  data: T;
  success: boolean;
  error?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    total_returned: number;
    has_more: boolean;
    limit: number;
  };
}

// ---------------------------------------------------------------------------
// Domain types (matching shared/models/domain.py)
// ---------------------------------------------------------------------------

export type TenantStatus = "active" | "suspended" | "provisioning";
export type TenantPlan = "starter" | "professional" | "enterprise";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: TenantPlan;
  status: TenantStatus;
  contact_email: string;
  created_at: string;
  updated_at: string;
}

export interface UIConfig {
  primary_color: string;
  secondary_color: string;
  chat_title: string;
  header_title: string;
  welcome_message: string;
  placeholder: string;
  logo_url: string;
  show_powered_by: boolean;
  show_welcome_message: boolean;
  input_placeholder: string;
}

export interface LeadField {
  name: string;
  label: string;
  type: string;
  required: boolean;
  validation?: string;
  options?: string[];
}

export interface LeadConfig {
  enabled: boolean;
  title: string;
  subtitle: string;
  fields: LeadField[];
  gdpr_text: string;
  submit_label: string;
}

export interface AIConfig {
  primary_provider: string;
  primary_model: string;
  fallback_provider: string;
  fallback_model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  system_prompt_override: string;
  enable_caching: boolean;
  cache_ttl_seconds: number;
  cost_optimization: boolean;
}

export interface RAGConfig {
  collection_name?: string;
  top_k: number;
  min_confidence: number;
  fallback_message: string;
  rerank_enabled: boolean;
}

export interface IntentDefinition {
  key: string;
  name: string;
  description: string;
  examples: string[];
  enabled: boolean;
  priority: number;
}

export interface EntityField {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default?: unknown;
  enum_values: string[];
  examples: string[];
}

export interface SkillConfig {
  action: string;
  name: string;
  description: string;
  entity_schema: EntityField[];
  preparation_prompt: string;
  response_templates: Record<string, string>;
  enabled: boolean;
}

export interface FlowTransition {
  intent: string;
  from_states: string[];
  to_state: string;
  action: string;
  static_message?: string;
  enabled: boolean;
}

export interface FSMConfig {
  intents: IntentDefinition[];
  transitions: FlowTransition[];
  states_enabled: string[];
  max_conversation_turns: number;
  session_timeout_minutes: number;
  nps_enabled: boolean;
  post_chat_delay_seconds: number;
  handoff_triggers: string[];
  auto_close_after_minutes: number;
  skills: SkillConfig[];
}

export interface TelegramConfig {
  enabled: boolean;
  bot_token: string;
  bot_username: string;
  webhook_secret: string;
  allowed_chat_ids: number[];
  welcome_message: string;
  parse_mode: string;
}

export interface TeamsConfig {
  enabled: boolean;
  webhook_url: string;
  channel_id: string;
  auto_handoff_keywords: string[];
  escalation_timeout_minutes: number;
  adaptive_card_template: string;
  mention_users: string[];
}

export interface EmailConfig {
  enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  smtp_from: string;
  smtp_from_name: string;
  use_tls: boolean;
  timeout_seconds: number;
  template_path: string;
}

export interface PaymentConfig {
  enabled: boolean;
  stripe_public_key: string;
  stripe_secret_key: string;
  currency_default: string;
  payment_methods: string[];
  checkout_session_expires_minutes: number;
  success_url_template: string;
  cancel_url_template: string;
  webhook_secret: string;
}

export interface TenantConfigDTO {
  tenant_id: string;
  version: number;
  ui_config: UIConfig;
  lead_config: LeadConfig;
  ai_config: AIConfig;
  rag_config: RAGConfig;
  fsm_config: FSMConfig;
  telegram_config: TelegramConfig;
  teams_config: TeamsConfig;
  email_config: EmailConfig;
  payment_config: PaymentConfig;
  updated_at: string;
}

export interface ApiKey {
  id: string;
  prefix: string;
  created_at: string;
  last_used_at?: string;
  label?: string;
}

export interface AnalyticsData {
  tenant_id: string;
  days: number;
  total_conversations: number;
  total_messages: number;
  avg_nps: number | null;
  nps_responses: number;
  top_intents: { intent: string; count: number }[];
  daily_volume: { date: string; messages: number }[];
  total_tokens: number;
  estimated_cost_usd: number;
}

export interface SessionItem {
  id: string;
  session_id: string;
  messages_count: number;
  nps_score: number | null;
  created_at: string;
  last_active_at: string;
  lead_name: string | null;
  lead_email: string | null;
}

export interface SessionsResponse {
  items: SessionItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface RAGStats {
  collection_name: string;
  vectors_count: number;
  status: string;
  points_count: number;
}

export interface ActionCatalogItem {
  key: string;
  name: string;
  description: string;
}

// ---------------------------------------------------------------------------
// Tenant Manager API
// ---------------------------------------------------------------------------

export const tenantManagerApi = {
  // Auth
  login: async (email: string, password: string) => {
    const res = await fetch(`${TENANT_MANAGER}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, ttl_minutes: 1440 }),
    });
    return json<{
      access_token: string;
      token_type: string;
      expires_in_seconds: number;
      role: string;
      subject: string;
    }>(res);
  },

  // Tenants CRUD
  listTenants: async (token: string, page = 1, pageSize = 20) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants?page=${page}&page_size=${pageSize}`,
      { token }
    );
    return json<PaginatedResponse<Tenant>>(res);
  },

  getTenant: async (token: string, tenantId: string) => {
    const res = await apiFetch(`${TENANT_MANAGER}/api/tenants/${tenantId}`, {
      token,
    });
    return json<APIResponse<Tenant>>(res);
  },

  createTenant: async (token: string, data: Partial<Tenant> & { contact_email: string }) => {
    const res = await apiFetch(`${TENANT_MANAGER}/api/tenants`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      token,
    });
    return json<APIResponse<Tenant & { api_key: string }>>(res);
  },

  updateTenant: async (token: string, tenantId: string, data: Partial<Tenant>) => {
    const res = await apiFetch(`${TENANT_MANAGER}/api/tenants/${tenantId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      token,
    });
    return json<APIResponse<Tenant>>(res);
  },

  suspendTenant: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/suspend`,
      { method: "POST", token }
    );
    return json<APIResponse<Tenant>>(res);
  },

  activateTenant: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/activate`,
      { method: "POST", token }
    );
    return json<APIResponse<Tenant>>(res);
  },

  // Full tenant config
  getTenantConfig: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/config`,
      { token }
    );
    return json<APIResponse<TenantConfigDTO>>(res);
  },

  // Specific config patches
  updateUIConfig: async (token: string, tenantId: string, config: Partial<UIConfig>) => {
    const res = await apiFetch(`${TENANT_MANAGER}/api/tenants/${tenantId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ui_config: config }),
      token,
    });
    return json<APIResponse<Tenant>>(res);
  },

  updateAIConfig: async (token: string, tenantId: string, config: Partial<AIConfig>) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/ai-config`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
        token,
      }
    );
    return json<APIResponse<AIConfig>>(res);
  },

  updateTelegramConfig: async (token: string, tenantId: string, config: Partial<TelegramConfig>) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/telegram-config`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
        token,
      }
    );
    return json<APIResponse<TelegramConfig>>(res);
  },

  updateTeamsConfig: async (token: string, tenantId: string, config: Partial<TeamsConfig>) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/teams-config`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
        token,
      }
    );
    return json<APIResponse<TeamsConfig>>(res);
  },

  updatePaymentConfig: async (token: string, tenantId: string, config: Partial<PaymentConfig>) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/payment-config`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
        token,
      }
    );
    return json<APIResponse<PaymentConfig>>(res);
  },

  updateFSMConfig: async (token: string, tenantId: string, config: Partial<FSMConfig>) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/fsm-config`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
        token,
      }
    );
    return json<APIResponse<FSMConfig>>(res);
  },

  // API Keys
  listApiKeys: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/api-keys`,
      { token }
    );
    return json<APIResponse<ApiKey[]>>(res);
  },

  createApiKey: async (token: string, tenantId: string, label: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/api-keys`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
        token,
      }
    );
    return json<APIResponse<{ api_key: string; prefix: string }>>(res);
  },

  // Intents
  listIntents: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/intents`,
      { token }
    );
    return json<APIResponse<IntentDefinition[]>>(res);
  },

  createIntent: async (token: string, tenantId: string, intent: Omit<IntentDefinition, "key"> & { key: string }) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/intents`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(intent),
        token,
      }
    );
    return json<APIResponse<IntentDefinition>>(res);
  },

  updateIntent: async (token: string, tenantId: string, intentKey: string, updates: Partial<IntentDefinition>) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/intents/${intentKey}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
        token,
      }
    );
    return json<APIResponse<IntentDefinition>>(res);
  },

  deleteIntent: async (token: string, tenantId: string, intentKey: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/intents/${intentKey}`,
      { method: "DELETE", token }
    );
    if (res.status === 204) return;
    return json<void>(res);
  },

  // Actions catalog
  listActions: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/actions`,
      { token }
    );
    return json<APIResponse<ActionCatalogItem[]>>(res);
  },

  // Transitions
  listTransitions: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/transitions`,
      { token }
    );
    return json<APIResponse<FlowTransition[]>>(res);
  },

  replaceTransitions: async (token: string, tenantId: string, transitions: FlowTransition[]) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/transitions`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(transitions),
        token,
      }
    );
    return json<APIResponse<FlowTransition[]>>(res);
  },

  // Skills
  listSkills: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/skills`,
      { token }
    );
    return json<APIResponse<SkillConfig[]>>(res);
  },

  upsertSkill: async (token: string, tenantId: string, actionKey: string, skill: SkillConfig) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/skills/${actionKey}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(skill),
        token,
      }
    );
    return json<APIResponse<SkillConfig>>(res);
  },

  // Analytics
  getAnalytics: async (token: string, tenantId: string, days = 30) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/analytics?days=${days}`,
      { token }
    );
    return json<APIResponse<AnalyticsData>>(res);
  },

  // Sessions list
  listSessions: async (token: string, tenantId: string, page = 1, pageSize = 20, days = 30) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/sessions?page=${page}&page_size=${pageSize}&days=${days}`,
      { token }
    );
    return json<APIResponse<SessionsResponse>>(res);
  },

  // RAG stats
  getRagStats: async (token: string, tenantId: string) => {
    const res = await apiFetch(
      `${TENANT_MANAGER}/api/tenants/${tenantId}/rag/stats`,
      { token }
    );
    return json<APIResponse<RAGStats>>(res);
  },
};

// ---------------------------------------------------------------------------
// RAG Service API
// ---------------------------------------------------------------------------

export const ragApi = {
  ingest: async (
    token: string,
    tenantId: string,
    file: File,
    collectionName?: string
  ) => {
    const form = new FormData();
    form.append("tenant_id", tenantId);
    form.append("file", file);
    if (collectionName) form.append("collection_name", collectionName);

    const res = await apiFetch(`${RAG_URL}/v1/rag/ingest`, {
      method: "POST",
      body: form,
      token,
    });
    return json<APIResponse<{ doc_id: string; chunks_created: number; collection_name: string; filename: string }>>(res);
  },

  query: async (token: string, tenantId: string, query: string) => {
    const res = await apiFetch(`${RAG_URL}/v1/rag/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, tenant_id: tenantId }),
      token,
    });
    return json<APIResponse<{ answer: string; confidence_score: number; chunks_used: unknown[] }>>(res);
  },

  deleteDocument: async (token: string, docId: string, tenantId: string) => {
    const res = await apiFetch(
      `${RAG_URL}/v1/rag/documents/${docId}?tenant_id=${tenantId}`,
      { method: "DELETE", token }
    );
    return json<APIResponse<{ deleted: boolean }>>(res);
  },
};

// ---------------------------------------------------------------------------
// Transcript Service API
// ---------------------------------------------------------------------------

export const transcriptApi = {
  getTranscript: async (token: string, tenantId: string, sessionId: string) => {
    const res = await apiFetch(
      `${TRANSCRIPT_URL}/v1/transcripts/${tenantId}/${sessionId}`,
      { token }
    );
    return json<{ session_id: string; messages: unknown[]; count: number }>(res);
  },
};

// ---------------------------------------------------------------------------
// SSE helpers
// ---------------------------------------------------------------------------

export function createTraceEventSource(
  token: string,
  sessionId: string
): EventSource {
  const url = `${ORCHESTRATOR}/v1/sessions/${sessionId}/trace?token=${encodeURIComponent(token)}`;
  return new EventSource(url);
}
