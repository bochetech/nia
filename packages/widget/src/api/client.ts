/**
 * API client — llama al tenant-manager y al orchestrator.
 */
export interface WidgetConfig {
  tenantId: string;
  apiUrl: string;
  tenantManagerUrl: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  recommendations?: RecommendationItem[];
  isStreaming?: boolean;
}

export interface RecommendationItem {
  product_id: string;
  name: string;
  category: string;
  base_price: number;
  currency: string;
  duration_minutes: number | null;
  availability_status: string;
  available_slots: { time: string; spots_left: number }[];
  score: number;
  rank: number;
  image_url: string | null;
}

export interface TokenResponse {
  token: string;
  session_id: string;
  expires_in_seconds: number;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  fsm_state: string;
  show_lead_form: boolean;
  recommendations: RecommendationItem[] | null;
  handoff_triggered: boolean;
  checkout_url: string | null;
}

export async function fetchWidgetToken(
  tenantManagerUrl: string,
  tenantId: string,
  apiKey: string,
  pageUrl?: string,
): Promise<TokenResponse> {
  const res = await fetch(`${tenantManagerUrl}/api/tenants/${tenantId}/widget-token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ page_url: pageUrl }),
  });
  if (!res.ok) throw new Error(`Token fetch failed: ${res.status}`);
  const body = await res.json();
  return body.data as TokenResponse;
}

export async function sendMessage(
  apiUrl: string,
  token: string,
  message: string,
): Promise<ChatResponse> {
  const res = await fetch(`${apiUrl}/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Chat error: ${res.status}`);
  }
  const body = await res.json();
  return body.data as ChatResponse;
}

export async function submitLead(
  apiUrl: string,
  token: string,
  sessionId: string,
  data: Record<string, string>,
  gdprConsent: boolean,
): Promise<void> {
  const res = await fetch(`${apiUrl}/v1/sessions/${sessionId}/lead`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ data, gdpr_consent: gdprConsent }),
  });
  if (!res.ok) throw new Error(`Lead submit failed: ${res.status}`);
}
