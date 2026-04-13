/**
 * useChat hook — gestiona el estado de la conversación.
 */
import { useCallback, useState } from "preact/hooks";
import { sendMessage, submitLead, requestTranscriptEmail } from "../api/client";
import type { ChatMessage, ChatResponse } from "../api/client";

let _msgCounter = 0;
const newId = () => `msg_${++_msgCounter}_${Date.now()}`;

export interface UseChatOptions {
  apiUrl: string;
  token: string;
  sessionId: string;
  tenantId: string;
  transcriptUrl?: string;
  chatTitle?: string;
  /** Se añade como primer mensaje de tipo 'assistant' al montar (sin lead form). */
  initialMessage?: string;
  /**
   * Mensaje de bienvenida que se inyecta DESPUÉS de que el usuario envía el
   * formulario de lead. Si está definido, reemplaza el "¡Gracias!" hardcoded.
   */
  postLeadMessage?: string;
}

export function useChat({ apiUrl, token, sessionId, tenantId, transcriptUrl, chatTitle, initialMessage, postLeadMessage }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    initialMessage
      ? [{ id: newId(), role: "assistant" as const, content: initialMessage, timestamp: Date.now() }]
      : []
  );
  const [loading, setLoading] = useState(false);
  const [fsmState, setFsmState] = useState("idle");
  const [showLeadForm, setShowLeadForm] = useState(false);
  const [handoffActive, setHandoffActive] = useState(false);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** Email del lead capturado — disponible para pre-rellenar la oferta de transcript */
  const [leadEmail, setLeadEmail] = useState<string>("");

  const addMessage = useCallback(
    (role: "user" | "assistant", content: string, extra: Partial<ChatMessage> = {}) => {
      setMessages((prev) => [
        ...prev,
        { id: newId(), role, content, timestamp: Date.now(), ...extra },
      ]);
    },
    [],
  );

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;
      setError(null);
      addMessage("user", text);
      setLoading(true);

      try {
        const resp: ChatResponse = await sendMessage(apiUrl, token, text);
        setFsmState(resp.fsm_state);
        setShowLeadForm(resp.show_lead_form);
        setHandoffActive(resp.handoff_triggered);
        setCheckoutUrl(resp.checkout_url);

        addMessage("assistant", resp.response, {
          recommendations: resp.recommendations ?? undefined,
        });
      } catch (err: any) {
        setError(err.message || "Error al conectar con el servidor.");
        addMessage("assistant", "Lo siento, ocurrió un error. Por favor intenta de nuevo.");
      } finally {
        setLoading(false);
      }
    },
    [apiUrl, token, loading, addMessage],
  );

  const submitLeadForm = useCallback(
    async (data: Record<string, string>, gdprConsent: boolean) => {
      setLoading(true);
      try {
        await submitLead(apiUrl, token, sessionId, data, gdprConsent);
        const email = data["email"] ?? data["correo"] ?? "";
        if (email) setLeadEmail(email);
        setShowLeadForm(false);
        setFsmState("greeting");
        // Mostrar el mensaje de bienvenida configurado, o el saludo genérico
        addMessage("assistant", postLeadMessage ?? "¡Gracias! ¿En qué puedo ayudarte hoy?");
      } catch {
        setError("Error al enviar tus datos. Por favor intenta de nuevo.");
      } finally {
        setLoading(false);
      }
    },
    [apiUrl, token, sessionId, addMessage, postLeadMessage],
  );

  const sendTranscript = useCallback(
    async (toEmail: string) => {
      if (!transcriptUrl) throw new Error("transcriptUrl not configured");
      await requestTranscriptEmail(
        transcriptUrl,
        tenantId,
        sessionId,
        toEmail,
        chatTitle ?? "NIA",
      );
    },
    [transcriptUrl, tenantId, sessionId, chatTitle],
  );

  return {
    messages,
    loading,
    fsmState,
    showLeadForm,
    handoffActive,
    checkoutUrl,
    error,
    leadEmail,
    send,
    submitLeadForm,
    sendTranscript,
    addMessage,
  };
}
