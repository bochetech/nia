import { h } from "preact";

export function TypingIndicator() {
  return (
    <div class="nia-bubble-wrapper nia-bubble-bot" aria-label="El asistente está escribiendo">
      <div class="nia-avatar" aria-hidden="true">🤖</div>
      <div class="nia-bubble nia-typing">
        <span class="nia-dot" />
        <span class="nia-dot" />
        <span class="nia-dot" />
      </div>
    </div>
  );
}
