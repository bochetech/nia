import { h } from "preact";
import { useState } from "preact/hooks";

export interface LeadField {
  name: string;
  type: "text" | "email" | "tel" | "select" | "textarea";
  label: string;
  required: boolean;
  options?: string[] | null;
  validation?: string | null;
}

export interface LeadConfig {
  enabled: boolean;
  fields: LeadField[];
  submit_label?: string;
  gdpr_consent_text?: string | null;
}

interface LeadFormProps {
  config: LeadConfig;
  chatTitle: string;
  primaryColor: string;
  onSubmit: (data: Record<string, string>, gdprConsent: boolean) => void;
  loading: boolean;
}

export function LeadForm({ config, chatTitle, primaryColor, onSubmit, loading }: LeadFormProps) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(config.fields.map((f) => [f.name, ""]))
  );
  const [gdpr, setGdpr] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function validate(): boolean {
    const next: Record<string, string> = {};
    for (const field of config.fields) {
      const val = (values[field.name] ?? "").trim();
      if (field.required && !val) {
        next[field.name] = "Este campo es obligatorio";
      } else if (field.type === "email" && val && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
        next[field.name] = "Ingresa un email válido";
      } else if (field.type === "tel" && val && !/^\+?[\d\s\-().]{6,20}$/.test(val)) {
        next[field.name] = "Ingresa un teléfono válido";
      }
    }
    if (config.gdpr_consent_text && !gdpr) {
      next["_gdpr"] = "Debes aceptar para continuar";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: Event) {
    e.preventDefault();
    if (!validate()) return;
    onSubmit(values, gdpr);
  }

  const cssVars = { "--nia-primary": primaryColor } as Record<string, string>;

  return (
    <div class="nia-lead-form" style={cssVars}>
      <div class="nia-lead-header">
        <span class="nia-logo-text" aria-hidden="true">🤖</span>
        <span class="nia-header-title">{chatTitle}</span>
      </div>

      <div class="nia-lead-body">
        <p class="nia-lead-intro">
          Para comenzar, completa tu información:
        </p>

        <form onSubmit={handleSubmit} noValidate>
          {config.fields.map((field) => (
            <div key={field.name} class="nia-field">
              <label class="nia-field-label" for={`nia-f-${field.name}`}>
                {field.label}
                {field.required && <span class="nia-required" aria-hidden="true"> *</span>}
              </label>

              {field.type === "select" && field.options ? (
                <select
                  id={`nia-f-${field.name}`}
                  class={`nia-input${errors[field.name] ? " nia-input--error" : ""}`}
                  value={values[field.name]}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [field.name]: (e.target as HTMLSelectElement).value }))
                  }
                  required={field.required}
                >
                  <option value="">— Selecciona —</option>
                  {field.options.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : field.type === "textarea" ? (
                <textarea
                  id={`nia-f-${field.name}`}
                  class={`nia-input nia-textarea${errors[field.name] ? " nia-input--error" : ""}`}
                  value={values[field.name]}
                  onInput={(e) =>
                    setValues((v) => ({ ...v, [field.name]: (e.target as HTMLTextAreaElement).value }))
                  }
                  required={field.required}
                  rows={3}
                />
              ) : (
                <input
                  id={`nia-f-${field.name}`}
                  type={field.type}
                  class={`nia-input${errors[field.name] ? " nia-input--error" : ""}`}
                  value={values[field.name]}
                  onInput={(e) =>
                    setValues((v) => ({ ...v, [field.name]: (e.target as HTMLInputElement).value }))
                  }
                  required={field.required}
                  autocomplete={field.type === "email" ? "email" : field.type === "tel" ? "tel" : "name"}
                />
              )}

              {errors[field.name] && (
                <span class="nia-field-error" role="alert">{errors[field.name]}</span>
              )}
            </div>
          ))}

          {config.gdpr_consent_text && (
            <div class="nia-field nia-field--gdpr">
              <label class="nia-gdpr-label">
                <input
                  type="checkbox"
                  checked={gdpr}
                  onChange={(e) => setGdpr((e.target as HTMLInputElement).checked)}
                />
                <span>{config.gdpr_consent_text}</span>
              </label>
              {errors["_gdpr"] && (
                <span class="nia-field-error" role="alert">{errors["_gdpr"]}</span>
              )}
            </div>
          )}

          <button
            type="submit"
            class="nia-submit-btn"
            disabled={loading}
          >
            {loading ? "Enviando…" : (config.submit_label ?? "Comenzar chat")}
          </button>
        </form>
      </div>
    </div>
  );
}
