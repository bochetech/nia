import { h } from "preact";

interface SuggestedQuestionsProps {
  questions: string[];
  onSelect: (question: string) => void;
}

/**
 * Muestra globos/pills con preguntas sugeridas.
 * Aparece justo después del mensaje de bienvenida, mientras el usuario
 * todavía no ha enviado ningún mensaje. Se oculta automáticamente una vez
 * que el usuario hace su primera pregunta.
 */
export function SuggestedQuestions({ questions, onSelect }: SuggestedQuestionsProps) {
  if (!questions || questions.length === 0) return null;

  return (
    <div class="nia-suggested-questions" aria-label="Preguntas sugeridas">
      {questions.map((q) => (
        <button
          key={q}
          class="nia-suggested-pill"
          type="button"
          onClick={() => onSelect(q)}
        >
          {q}
        </button>
      ))}
    </div>
  );
}
