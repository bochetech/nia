import { h } from "preact";
import type { ChatMessage, RecommendationItem } from "../api/client";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div class={`nia-bubble-wrapper ${isUser ? "nia-bubble-user" : "nia-bubble-bot"}`}>
      {!isUser && (
        <div class="nia-avatar" aria-hidden="true">
          <span class="nia-avatar-text">N</span>
        </div>
      )}
      <div class="nia-bubble">
        <p class="nia-bubble-text">{message.content}</p>
        {message.recommendations && message.recommendations.length > 0 && (
          <RecommendationCards items={message.recommendations} />
        )}
        <span class="nia-timestamp">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}

function RecommendationCards({ items }: { items: RecommendationItem[] }) {
  return (
    <div class="nia-reco-cards">
      {items.map((item) => (
        <div key={item.product_id} class="nia-reco-card">
          {item.image_url && (
            <img
              class="nia-reco-img"
              src={item.image_url}
              alt={item.name}
              loading="lazy"
            />
          )}
          <div class="nia-reco-body">
            <div class="nia-reco-name">{item.name}</div>
            <div class="nia-reco-desc">
              {item.duration_minutes && `⏱ ${item.duration_minutes} min`}
            </div>
            <div class="nia-reco-footer">
              <span class="nia-reco-price">
                ${item.base_price.toLocaleString()} {item.currency}
              </span>
              <span
                class={`nia-reco-score ${
                  item.availability_status === "available" ? "nia-available" : "nia-check"
                }`}
              >
                {item.availability_status === "available" ? "✅ Disponible" : "📅 Consultar"}
              </span>
            </div>
            <button class="nia-reco-btn" type="button">
              Ver detalles
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
