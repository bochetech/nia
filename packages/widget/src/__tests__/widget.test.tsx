/**
 * Widget component tests — Vitest + @testing-library/preact
 * Run: npm test (from packages/widget/)
 */
import { h } from "preact";
import { render, screen, fireEvent, waitFor } from "@testing-library/preact";
import { describe, it, expect, vi, beforeEach } from "vitest";

// ── Mock API client ────────────────────────────────────────────────────────
vi.mock("../api/client", () => ({
  sendMessage: vi.fn(),
  submitLead: vi.fn(),
}));

import { sendMessage } from "../api/client";
import { Widget } from "../components/Widget.tsx";
import { MessageBubble } from "../components/MessageBubble.tsx";
import { TypingIndicator } from "../components/TypingIndicator.tsx";
import { InputBar } from "../components/InputBar.tsx";

// ── Helpers ────────────────────────────────────────────────────────────────
const defaultProps = {
  tenantId: "test-tenant",
  apiUrl: "http://localhost:8001",
  tenantManagerUrl: "http://localhost:8003",
};

function mockFetch(data: object) {
  (globalThis as unknown as { fetch: unknown }).fetch = vi.fn().mockResolvedValue({
    json: vi.fn().mockResolvedValue(data),
    ok: true,
  });
}

// ── TypingIndicator ────────────────────────────────────────────────────────
describe("TypingIndicator", () => {
  it("renders three animated dots", () => {
    const { container } = render(<TypingIndicator />);
    const dots = container.querySelectorAll(".nia-dot");
    expect(dots).toHaveLength(3);
  });

  it("has accessible aria-label", () => {
    render(<TypingIndicator />);
    expect(
      screen.getByLabelText(/escribiendo/i)
    ).toBeInTheDocument();
  });
});

// ── MessageBubble ──────────────────────────────────────────────────────────
describe("MessageBubble", () => {
  it("renders user message with correct class", () => {
    const { container } = render(
      <MessageBubble
        message={{ id: "1", role: "user", content: "Hola!", timestamp: Date.now() }}
      />
    );
    expect(container.querySelector(".nia-bubble-user")).not.toBeNull();
  });

  it("renders assistant message with bot class", () => {
    const { container } = render(
      <MessageBubble
        message={{ id: "2", role: "assistant", content: "¡Hola! Soy NIA.", timestamp: Date.now() }}
      />
    );
    expect(container.querySelector(".nia-bubble-bot")).not.toBeNull();
  });

  it("shows recommendation cards when present", () => {
    const message = {
      id: "3",
      role: "assistant" as const,
      content: "Te recomiendo este tour:",
      timestamp: Date.now(),
      recommendations: [
        {
          product_id: "prod_001",
          name: "Tour Ruta Maya",
          description: "Gran tour",
          category: "cultural",
          base_price: 349,
          currency: "USD",
          duration_minutes: null,
          availability_status: "available",
          available_slots: [],
          score: 0.95,
          rank: 1,
          image_url: null,
        },
      ],
    };
    render(<MessageBubble message={message} />);
    expect(screen.getByText("Tour Ruta Maya")).toBeInTheDocument();
    expect(screen.getByText(/349/)).toBeInTheDocument();
  });
});

// ── InputBar ──────────────────────────────────────────────────────────────
describe("InputBar", () => {
  it("calls onSend with trimmed text on button click", async () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} disabled={false} />);
    const textarea = screen.getByRole("textbox", { name: /mensaje/i });
    const button = screen.getByRole("button", { name: /enviar/i });

    fireEvent.input(textarea, { target: { value: "  Quiero un tour  " } });
    fireEvent.click(button);

    expect(onSend).toHaveBeenCalledWith("Quiero un tour");
  });

  it("submits on Enter key", async () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} disabled={false} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.input(textarea, { target: { value: "Test" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(onSend).toHaveBeenCalledWith("Test");
  });

  it("does not submit on Shift+Enter", () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} disabled={false} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.input(textarea, { target: { value: "Test" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables send button when disabled=true", () => {
    render(<InputBar onSend={vi.fn()} disabled={true} />);
    expect(screen.getByRole("button", { name: /enviar/i })).toBeDisabled();
  });
});

// ── Widget (integration) ───────────────────────────────────────────────────
describe("Widget", () => {
  beforeEach(() => {
    mockFetch({
      primary_color: "#0f766e",
      logo_url: null,
      welcome_message: "¡Hola! Soy NIA.",
      placeholder: "Escribe…",
      widget_token: "tok_test",
    });
  });

  it("renders launcher button", async () => {
    render(<Widget {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /abrir chat/i })).toBeInTheDocument();
    });
  });

  it("opens panel when launcher is clicked", async () => {
    render(<Widget {...defaultProps} />);
    const launcher = await screen.findByRole("button", { name: /abrir chat/i });
    fireEvent.click(launcher);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("closes panel when close button is clicked", async () => {
    render(<Widget {...defaultProps} />);
    const launcher = await screen.findByRole("button", { name: /abrir chat/i });
    fireEvent.click(launcher);

    // Two "Cerrar chat" buttons exist (header X + launcher); use the header one
    const closeBtns = await screen.findAllByRole("button", { name: /cerrar chat/i });
    const headerClose = closeBtns.find(
      (btn) => btn.classList.contains("nia-close-btn"),
    )!;
    fireEvent.click(headerClose);

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  it("sends message and displays response", async () => {
    const mockSendMessage = sendMessage as ReturnType<typeof vi.fn>;
    mockSendMessage.mockResolvedValue({
      response: "El tour cuesta $349.",
      fsm_state: "recommendation",
      show_lead_form: false,
      handoff_triggered: false,
      checkout_url: null,
      recommendations: [],
    });

    render(<Widget {...defaultProps} />);
    const launcher = await screen.findByRole("button", { name: /abrir chat/i });
    fireEvent.click(launcher);

    const textarea = await screen.findByRole("textbox");
    fireEvent.input(textarea, { target: { value: "¿Cuánto cuesta el tour?" } });
    fireEvent.keyDown(textarea, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText("El tour cuesta $349.")).toBeInTheDocument();
    });
  });
});
