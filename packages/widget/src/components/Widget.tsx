import { h, Fragment } from "preact";
import { useState, useEffect, useRef } from "preact/hooks";
import { useChat } from "../hooks/useChat.ts";
import { MessageList } from "./MessageList.tsx";
import { InputBar } from "./InputBar.tsx";

/** Props passed from embed.tsx */
export interface WidgetProps {
  tenantId: string;
  apiUrl: string;
  tenantManagerUrl: string;
  position?: "bottom-right" | "bottom-left";
}

/** Runtime config fetched from tenant-manager */
interface TenantBranding {
  primaryColor: string;
  logoUrl: string | null;
  chatTitle: string;
  welcomeMessage: string;
  showWelcomeMessage: boolean;
  inputPlaceholder: string;
  token: string;
}

const DEFAULT_BRANDING: TenantBranding = {
  primaryColor: "#2563eb",
  logoUrl: null,
  chatTitle: "Asistente NIA",
  welcomeMessage: "¡Hola! Soy NIA, tu asistente de viajes. ¿En qué te puedo ayudar?",
  showWelcomeMessage: true,
  inputPlaceholder: "Escribe un mensaje…",
  token: "",
};

/** Generate a stable session ID for this browser tab */
function getOrCreateSessionId(): string {
  const key = "nia_session_id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = `s_${Math.random().toString(36).slice(2)}_${Date.now()}`;
    sessionStorage.setItem(key, id);
  }
  return id;
}

export function Widget({ tenantId, apiUrl, tenantManagerUrl, position = "bottom-right" }: WidgetProps) {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [branding, setBranding] = useState<TenantBranding>(DEFAULT_BRANDING);
  const [sessionId] = useState(() => getOrCreateSessionId());
  const launcherRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Fetch branding + widget token from tenant-manager on mount
  useEffect(() => {
    fetch(`${tenantManagerUrl}/tenants/${tenantId}/widget-config`)
      .then((r) => r.json())
      .then((data) => {
        setBranding({
          primaryColor: data.primary_color ?? DEFAULT_BRANDING.primaryColor,
          logoUrl: data.logo_url ?? null,
          chatTitle: data.chat_title ?? DEFAULT_BRANDING.chatTitle,
          welcomeMessage: data.welcome_message ?? DEFAULT_BRANDING.welcomeMessage,
          showWelcomeMessage: data.show_welcome_message ?? DEFAULT_BRANDING.showWelcomeMessage,
          inputPlaceholder: data.input_placeholder ?? DEFAULT_BRANDING.inputPlaceholder,
          token: data.widget_token ?? "",
        });
      })
      .catch(() => {
        // Fall back to defaults — widget still functional with anonymous token
      });
  }, [tenantId, tenantManagerUrl]);

  const {
    messages,
    loading,
    send,
  } = useChat({
    apiUrl,
    token: branding.token,
    sessionId,
    // Solo pasar el mensaje inicial si show_welcome_message está activado
    initialMessage: branding.showWelcomeMessage ? branding.welcomeMessage : undefined,
  });

  // Track unread when panel is closed
  useEffect(() => {
    if (!open && messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role === "assistant") {
        setUnread((n) => n + 1);
      }
    }
  }, [messages]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleOpen() {
    setOpen((v) => {
      if (!v) setUnread(0);
      return !v;
    });
  }

  // Trap focus inside panel when open
  useEffect(() => {
    if (open && panelRef.current) {
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'button, textarea, [tabindex]:not([tabindex="-1"])'
      );
      focusable[0]?.focus();
    } else if (!open) {
      launcherRef.current?.focus();
    }
  }, [open]);

  const positionClass =
    position === "bottom-left" ? "nia-pos-left" : "nia-pos-right";

  const cssVars = {
    "--nia-primary": branding.primaryColor,
  } as Record<string, string>;

  return (
    <Fragment>
      {/* Chat panel */}
      {open && (
        <div
          class={`nia-panel ${positionClass}`}
          role="dialog"
          aria-label="Chat con NIA"
          aria-modal="true"
          ref={panelRef}
          style={cssVars}
        >
          {/* Header */}
          <header class="nia-header">
            {branding.logoUrl ? (
              <img class="nia-logo" src={branding.logoUrl} alt="Logo" aria-hidden="true" />
            ) : (
              <span class="nia-logo-text" aria-hidden="true">🤖</span>
            )}
            <span class="nia-header-title">{branding.chatTitle}</span>
            <button
              class="nia-close-btn"
              type="button"
              aria-label="Cerrar chat"
              onClick={toggleOpen}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" width="16" height="16" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </header>

          {/* Message area */}
          <div class="nia-body">
            <MessageList messages={messages} loading={loading} />
          </div>

          {/* Input area */}
          <footer class="nia-footer">
            <InputBar
              onSend={send}
              disabled={loading}
              placeholder={branding.inputPlaceholder}
            />
            <p class="nia-branding" aria-label="Powered by NIA">
              Powered by <strong>NIA</strong>
            </p>
          </footer>
        </div>
      )}

      {/* Launcher FAB */}
      <button
        ref={launcherRef}
        class={`nia-launcher ${positionClass}`}
        type="button"
        aria-label={open ? "Cerrar chat" : "Abrir chat"}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={toggleOpen}
        style={cssVars}
      >
        {open ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" width="24" height="24" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        )}
        {!open && unread > 0 && (
          <span class="nia-badge" aria-label={`${unread} mensajes sin leer`}>
            {unread > 9 ? "9+" : String(unread)}
          </span>
        )}
      </button>
    </Fragment>
  );
}
