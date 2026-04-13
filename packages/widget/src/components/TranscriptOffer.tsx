import { h } from "preact";
import { useState } from "preact/hooks";

interface TranscriptOfferProps {
  /** Email pre-rellenado del lead (puede estar vacío si no hay lead capturado) */
  prefillEmail: string;
  primaryColor: string;
  onSend: (email: string) => void;
  onDismiss: () => void;
  loading: boolean;
  /** "idle" | "sent" | "error" */
  status: "idle" | "sent" | "error";
}

export function TranscriptOffer({
  prefillEmail,
  primaryColor,
  onSend,
  onDismiss,
  loading,
  status,
}: TranscriptOfferProps) {
  const [email, setEmail] = useState(prefillEmail);
  const [emailError, setEmailError] = useState("");

  const cssVars = { "--nia-primary": primaryColor } as Record<string, string>;

  function handleSend(e: Event) {
    e.preventDefault();
    const val = email.trim();
    if (!val || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
      setEmailError("Ingresa un email válido");
      return;
    }
    setEmailError("");
    onSend(val);
  }

  if (status === "sent") {
    return (
      <div class="nia-transcript-offer nia-transcript-offer--sent" style={cssVars}>
        <span class="nia-transcript-icon">✅</span>
        <p class="nia-transcript-msg">
          ¡Listo! Te enviamos la conversación a <strong>{email}</strong>
        </p>
        <button class="nia-transcript-dismiss" type="button" onClick={onDismiss}>
          Cerrar
        </button>
      </div>
    );
  }

  return (
    <div class="nia-transcript-offer" style={cssVars}>
      <div class="nia-transcript-offer-header">
        <span class="nia-transcript-icon">📩</span>
        <p class="nia-transcript-msg">
          ¿Quieres recibir esta conversación por correo?
        </p>
        <button
          class="nia-transcript-dismiss-x"
          type="button"
          aria-label="No gracias"
          onClick={onDismiss}
        >
          ✕
        </button>
      </div>

      {status === "error" && (
        <p class="nia-transcript-error" role="alert">
          No se pudo enviar. Intenta de nuevo.
        </p>
      )}

      <form class="nia-transcript-form" onSubmit={handleSend}>
        <input
          type="email"
          class={`nia-input nia-transcript-email-input${emailError ? " nia-input--error" : ""}`}
          value={email}
          onInput={(e) => setEmail((e.target as HTMLInputElement).value)}
          placeholder="tucorreo@ejemplo.com"
          autocomplete="email"
          aria-label="Tu correo electrónico"
        />
        {emailError && (
          <span class="nia-field-error" role="alert">{emailError}</span>
        )}
        <div class="nia-transcript-actions">
          <button
            type="submit"
            class="nia-submit-btn nia-submit-btn--sm"
            disabled={loading}
          >
            {loading ? "Enviando…" : "Enviar"}
          </button>
          <button
            type="button"
            class="nia-transcript-skip"
            onClick={onDismiss}
          >
            No gracias
          </button>
        </div>
      </form>
    </div>
  );
}
