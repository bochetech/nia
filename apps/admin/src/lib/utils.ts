import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return "—";
  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(dateStr));
}

export function formatNumber(n: number | null | undefined) {
  if (n == null) return "—";
  return new Intl.NumberFormat("es-CL").format(n);
}

export function formatCurrency(amount: number | null | undefined, currency = "USD") {
  if (amount == null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 4,
  }).format(amount);
}

export function truncate(str: string, len: number) {
  return str.length > len ? str.slice(0, len) + "…" : str;
}

export const FSM_STATES = [
  "idle",
  "pre_chat",
  "greeting",
  "discovery",
  "faq_answer",
  "recommending",
  "product_selected",
  "checkout_init",
  "awaiting_payment",
  "payment_failed",
  "confirmed",
  "post_chat",
  "handoff_active",
  "closed",
] as const;

export type FSMStateKey = (typeof FSM_STATES)[number];

export const FSM_STATE_LABELS: Record<string, string> = {
  idle:             "Idle",
  pre_chat:         "Pre-Chat",
  greeting:         "Greeting",
  discovery:        "Discovery",
  faq_answer:       "FAQ Answer",
  recommending:     "Recommending",
  product_selected: "Product Selected",
  checkout_init:    "Checkout Init",
  awaiting_payment: "Awaiting Payment",
  payment_failed:   "Payment Failed",
  confirmed:        "Confirmed",
  post_chat:        "Post-Chat",
  handoff_active:   "Handoff Active",
  closed:           "Closed",
};

export const FSM_STATE_COLORS: Record<string, string> = {
  idle: "#8E8E93",          // Apple systemGray
  pre_chat: "#AF52DE",      // Apple purple
  greeting: "#007AFF",      // Apple blue
  discovery: "#5AC8FA",     // Apple tealBlue
  faq_answer: "#34C759",    // Apple green
  recommending: "#FF9500",  // Apple orange
  product_selected: "#FF9500", // Apple orange
  checkout_init: "#FF3B30", // Apple red
  awaiting_payment: "#FF2D55", // Apple pink
  payment_failed: "#FF3B30",// Apple red
  confirmed: "#34C759",     // Apple green
  post_chat: "#8E8E93",     // Apple systemGray
  handoff_active: "#FF9500",// Apple orange
  closed: "#636366",        // Apple systemGray2
};

export const ACTION_LABELS: Record<string, string> = {
  faq: "FAQ — Knowledge Base",
  recommend: "Recommend Products",
  handoff: "Handoff to Human",
  nps: "NPS Survey",
  // Internal FSM behaviors — not shown as configurable skills:
  complaint: "Complaint (internal)",
  static_reply: "Static Reply (internal)",
  discovery: "Discovery (internal)",
  conversational: "Custom Persona",
};

export const ACTION_COLORS: Record<string, string> = {
  faq: "#3b82f6",           // blue
  recommend: "#10b981",     // emerald
  handoff: "#f59e0b",       // amber
  nps: "#06b6d4",           // cyan
  complaint: "#ef4444",     // red  (internal)
  static_reply: "#6b7280",  // gray (internal)
  discovery: "#8b5cf6",     // violet (internal)
  conversational: "#FF2D55",// pink — custom personas
};
