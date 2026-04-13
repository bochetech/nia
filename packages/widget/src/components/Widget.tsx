import { h, Fragment } from "preact";
import { useState, useEffect, useRef } from "preact/hooks";
import { useChat } from "../hooks/useChat.ts";
import { MessageList } from "./MessageList.tsx";
import { InputBar } from "./InputBar.tsx";
import { LeadForm } from "./LeadForm.tsx";
import { TranscriptOffer } from "./TranscriptOffer.tsx";
import { SuggestedQuestions } from "./SuggestedQuestions.tsx";
import type { LeadConfig } from "./LeadForm.tsx";

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
  leadConfig: LeadConfig | null;
  transcriptUrl: string;
  suggestedQuestions: string[];
}

const DEFAULT_BRANDING: TenantBranding = {
  primaryColor: "#2563eb",
  logoUrl: null,
  chatTitle: "Asistente NIA",
  welcomeMessage: "",
  showWelcomeMessage: false,   // nunca mostrar hasta que llegue la config real
  inputPlaceholder: "Escribe un mensaje…",
  token: "",
  leadConfig: null,
  transcriptUrl: "",
  suggestedQuestions: [],
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

  // Si hay lead form activo, el welcome se inyecta DESPUÉS del submit.
  // Si no hay lead form, se inyecta al recibir la config del tenant.
  const hasLeadForm = branding.leadConfig !== null && branding.leadConfig?.enabled;

  const {
    messages,
    loading,
    send,
    submitLeadForm,
    sendTranscript,
    showLeadForm: hookShowLead,
    leadEmail,
    error: chatError,
    addMessage,
  } = useChat({
    apiUrl,
    token: branding.token,
    sessionId,
    tenantId,
    transcriptUrl: branding.transcriptUrl,
    chatTitle: branding.chatTitle,
    // Cuando hay lead form, pasamos el welcome para que se inyecte post-submit
    postLeadMessage:
      branding.showWelcomeMessage && hasLeadForm
        ? branding.welcomeMessage
        : undefined,
  });

  // Fetch branding + widget token from tenant-manager on mount.
  // Inyectamos el welcome UNA SOLA VEZ aquí (no en useState) para que
  // use el texto real del tenant, no el DEFAULT_BRANDING.
  const welcomeInjectedRef = useRef(false);
  useEffect(() => {
    fetch(`${tenantManagerUrl}/tenants/${tenantId}/widget-config`)
      .then((r) => r.json())
      .then((data) => {
        const leadEnabled = data.lead_config?.enabled ?? false;
        const showWelcome = data.show_welcome_message ?? false;
        const welcomeMsg  = data.welcome_message ?? "";

        setBranding({
          primaryColor:       data.primary_color       ?? DEFAULT_BRANDING.primaryColor,
          logoUrl:            data.logo_url            ?? null,
          chatTitle:          data.chat_title          ?? DEFAULT_BRANDING.chatTitle,
          welcomeMessage:     welcomeMsg,
          showWelcomeMessage: showWelcome,
          inputPlaceholder:   data.input_placeholder   ?? DEFAULT_BRANDING.inputPlaceholder,
          token:              data.widget_token        ?? "",
          leadConfig:         leadEnabled ? data.lead_config : null,
          transcriptUrl:      data.transcript_url      ?? "",
          suggestedQuestions: Array.isArray(data.suggested_questions) ? data.suggested_questions : [],
        });

        // Inyectar welcome inmediatamente solo si NO hay lead form activo
        if (showWelcome && welcomeMsg && !leadEnabled && !welcomeInjectedRef.current) {
          welcomeInjectedRef.current = true;
          addMessage("assistant", welcomeMsg);
        }
      })
      .catch(() => {
        // Sin config: el widget funciona igual, sin mensaje de bienvenida
      });
  }, [tenantId, tenantManagerUrl]);  // addMessage es estable (useCallback)

  // El formulario de lead se muestra si la config lo tiene habilitado Y no hay lead
  // capturado todavía (leadEmail vacío significa que aún no se ha enviado)
  const showPreChatLead =
    branding.leadConfig !== null && branding.leadConfig.enabled && !leadEmail;

  // Estado del offer de transcript (idle | sent | error | dismissed)
  type TranscriptStatus = "idle" | "sent" | "error" | "dismissed";
  const [transcriptStatus, setTranscriptStatus] = useState<TranscriptStatus>("idle");
  const [transcriptLoading, setTranscriptLoading] = useState(false);

  async function handleSendTranscript(email: string) {
    setTranscriptLoading(true);
    try {
      await sendTranscript(email);
      setTranscriptStatus("sent");
    } catch {
      setTranscriptStatus("error");
    } finally {
      setTranscriptLoading(false);
    }
  }

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
      const closing = v; // si era true, estamos cerrando
      if (!v) setUnread(0);
      // Al cerrar: si hay mensajes y email, mostrar oferta de transcript
      if (closing && messages.length > 1 && leadEmail && transcriptStatus === "idle") {
        // No hacer nada especial aquí — el offer se renderiza abajo cuando !open
        // El estado transcriptStatus ya está en "idle" por defecto
      }
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
          {/* ── FORMULARIO PRE-CHAT ── */}
          {showPreChatLead && branding.leadConfig ? (
            <LeadForm
              config={branding.leadConfig}
              chatTitle={branding.chatTitle}
              primaryColor={branding.primaryColor}
              onSubmit={submitLeadForm}
              loading={loading}
            />
          ) : (
            <Fragment>
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
                {/* Preguntas sugeridas: solo mientras el usuario no ha enviado nada */}
                {branding.suggestedQuestions.length > 0 && !messages.some((m) => m.role === "user") && (
                  <SuggestedQuestions
                    questions={branding.suggestedQuestions}
                    onSelect={send}
                  />
                )}
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
            </Fragment>
          )}
        </div>
      )}

      {/* ── OFERTA DE TRANSCRIPT (aparece flotando sobre el launcher al cerrar) ── */}
      {!open && messages.length > 1 && leadEmail && transcriptStatus !== "dismissed" && (
        <TranscriptOffer
          prefillEmail={leadEmail}
          primaryColor={branding.primaryColor}
          onSend={handleSendTranscript}
          onDismiss={() => setTranscriptStatus("dismissed")}
          loading={transcriptLoading}
          status={transcriptStatus as "idle" | "sent" | "error"}
        />
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
