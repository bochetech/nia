/**
 * NIA Widget — embed script.
 * Insertado en el sitio del cliente como:
 *   <script src="nia-widget.js" data-tenant="tenant_id" data-api-url="https://api.nia.io"></script>
 *
 * Monta el widget en un Shadow DOM para aislamiento total de CSS.
 */
import { render } from "preact";
import { Widget } from "./components/Widget.tsx";
import widgetCss from "./styles/widget.css?inline";

// Capturar currentScript INMEDIATAMENTE al ejecutarse el módulo,
// antes de cualquier callback asíncrono (DOMContentLoaded lo pierde).
// Fallbacks en orden: currentScript → id canónico → cualquier script con data-tenant
const _scriptEl: HTMLScriptElement | null =
  (document.currentScript as HTMLScriptElement | null) ??
  document.querySelector<HTMLScriptElement>("#nia-script") ??
  document.querySelector<HTMLScriptElement>("script[data-tenant]");

function bootstrap() {
  // Prioridad: window.NIA_CONFIG (inyectado inline antes del script)
  // luego los data-* del script tag
  const cfg = (window as any).NIA_CONFIG ?? {};
  const script = _scriptEl;

  const tenantId: string =
    cfg.tenant ??
    script?.dataset.tenant ??
    "";
  const apiUrl: string =
    cfg.apiUrl ??
    script?.dataset.apiUrl ??
    "http://localhost:8001";
  const tenantManagerUrl: string =
    cfg.tenantManagerUrl ??
    script?.dataset.tenantManagerUrl ??
    "http://localhost:8003";
  const position: "bottom-right" | "bottom-left" =
    cfg.position ??
    (script?.dataset.position as "bottom-right" | "bottom-left") ??
    "bottom-right";

  if (!tenantId) {
    console.warn("[NIA] Missing data-tenant attribute");
    return;
  }

  // Contenedor host (fuera del Shadow DOM)
  const host = document.createElement("div");
  host.id = "nia-widget-host";
  host.style.cssText =
    "position:fixed;z-index:2147483647;pointer-events:none;inset:0;";
  document.body.appendChild(host);

  // Shadow DOM para aislamiento de estilos
  const shadow = host.attachShadow({ mode: "open" });

  // Inyectar estilos en el shadow
  const styleEl = document.createElement("style");
  styleEl.textContent = widgetCss;
  shadow.appendChild(styleEl);

  // Contenedor para Preact
  const mountPoint = document.createElement("div");
  mountPoint.id = "nia-root";
  shadow.appendChild(mountPoint);

  render(
    <Widget
      tenantId={tenantId}
      apiUrl={apiUrl}
      tenantManagerUrl={tenantManagerUrl}
      position={position}
    />,
    mountPoint
  );
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
