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
  idle: "#6b7280",
  pre_chat: "#8b5cf6",
  greeting: "#3b82f6",
  discovery: "#06b6d4",
  faq_answer: "#10b981",
  recommending: "#f59e0b",
  product_selected: "#f97316",
  checkout_init: "#ef4444",
  awaiting_payment: "#ec4899",
  payment_failed: "#dc2626",
  confirmed: "#16a34a",
  post_chat: "#64748b",
  handoff_active: "#d97706",
  closed: "#374151",
};

export const ACTION_LABELS: Record<string, string> = {
  faq: "FAQ (RAG)",
  recommend: "Recommend",
  handoff: "Handoff",
  nps: "NPS Survey",
  complaint: "Complaint",
  static_reply: "Static Reply",
  discovery: "Discovery",
  conversational: "Conversational",
};

export const ACTION_COLORS: Record<string, string> = {
  faq: "#10b981",
  recommend: "#f59e0b",
  handoff: "#d97706",
  nps: "#3b82f6",
  complaint: "#ef4444",
  static_reply: "#6b7280",
  discovery: "#8b5cf6",
  conversational: "#ec4899",
};
