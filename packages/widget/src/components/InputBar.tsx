import { h } from "preact";
import { useState, useRef, useEffect } from "preact/hooks";

interface InputBarProps {
  onSend: (text: string) => void;
  disabled: boolean;
  placeholder?: string;
}

export function InputBar({ onSend, disabled, placeholder = "Escribe un mensaje…" }: InputBarProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    
    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = "auto";
    
    // Calculate new height based on content
    const newHeight = Math.min(textarea.scrollHeight, 120); // max-height of 120px
    textarea.style.height = `${newHeight}px`;
  }, [value]);

  function handleInput(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    setValue(target.value);
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <div class="nia-input-bar" role="form" aria-label="Enviar mensaje">
      <textarea
        ref={textareaRef}
        class="nia-input"
        rows={1}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        aria-label="Mensaje"
        onInput={handleInput}
        onKeyDown={handleKey}
      />
      <button
        class="nia-send-btn"
        type="button"
        onClick={submit}
        disabled={disabled || !value.trim()}
        aria-label="Enviar"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </div>
  );
}
