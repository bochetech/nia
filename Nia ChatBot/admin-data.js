/* ── NIA Admin Console — Sample Data ── */
const NIA = {
  tenants: [
    {
      id: "demo_turismo", name: "Centro del Vino · Concha y Toro",
      plan: "professional", status: "active",
      contactEmail: "admin@conchaytoro.com",
      configVersion: 14, createdAt: "2024-11-10T09:00:00Z",
      channels: ["widget", "telegram"],
      ui: { primaryColor: "#7a2020", secondaryColor: "#c9a84c", chatTitle: "Asistente Enoturismo", welcomeMessage: "¡Hola! Soy NIA 🍷 ¿En qué te puedo ayudar?", inputPlaceholder: "Ej: ¿Qué tours tienen disponibles?", position: "bottom-right", showWelcome: true },
      ai: { primaryProvider: "vertex_ai", primaryModel: "gemini-2.0-flash", temperature: 0.3, maxTokens: 800, systemPrompt: "Eres NIA, asistente virtual del Centro del Vino Concha y Toro. Ayudas a visitantes con información sobre tours, horarios, precios y reservas de enoturismo. Responde siempre en español, con tono amable y profesional.", enableCaching: true, costOptimization: true, inputCostPerM: 0.075, outputCostPerM: 0.30, fallbackProvider: "openai", fallbackModel: "gpt-4o-mini" },
      limits: { maxTokensPerConv: 8000, maxConvsPerMonth: 5000, maxLlmCostUsd: 150, maxRagDocs: 200, handoffEnabled: true, responseTimeout: 15 },
      rag: { confidenceThreshold: 0.68, maxTokensResponse: 500, fallbackMessage: "No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?", topKRetrieval: 10, topKRerank: 3 },
      analytics: {
        totalConvs: 2847, totalMsgs: 18432, avgNps: 4.3, npsResponses: 412,
        totalTokens: 4820000, estimatedCostUsd: 0.72,
        daily: [120,98,145,167,203,189,211,178,224,198,215,230,245,189,167,201,234,267,289,312,298,276,301,323,298,312,287,334,310,298],
        topIntents: [
          { intent: "faq_query", count: 6821 },
          { intent: "booking_intent", count: 4203 },
          { intent: "product_inquiry", count: 2918 },
          { intent: "human_request", count: 1247 },
          { intent: "complaint", count: 654 },
        ]
      }
    },
    {
      id: "moda_imagen", name: "StyleSense Fashion Advisor",
      plan: "starter", status: "active",
      contactEmail: "tech@stylesense.cl",
      configVersion: 7, createdAt: "2025-01-15T14:00:00Z",
      channels: ["widget"],
      ui: { primaryColor: "#1a1a5c", secondaryColor: "#f59e0b", chatTitle: "StyleSense AI", welcomeMessage: "¡Hola! Soy tu asesor de moda personal 👗", inputPlaceholder: "¿Qué estilo buscas?", position: "bottom-right", showWelcome: true },
      ai: { primaryProvider: "openai", primaryModel: "gpt-4o-mini", temperature: 0.5, maxTokens: 600, systemPrompt: "Eres StyleSense, asesor de moda virtual. Ayudas a clientes a encontrar outfits, recomendar combinaciones de ropa y acceder al catálogo de productos.", enableCaching: true, costOptimization: true, inputCostPerM: 0.15, outputCostPerM: 0.60, fallbackProvider: "lmstudio", fallbackModel: "" },
      limits: { maxTokensPerConv: 5000, maxConvsPerMonth: 1000, maxLlmCostUsd: 50, maxRagDocs: 100, handoffEnabled: false, responseTimeout: 10 },
      rag: { confidenceThreshold: 0.65, maxTokensResponse: 400, fallbackMessage: "No tengo ese producto en catálogo. ¿Te puedo ayudar con otra cosa?", topKRetrieval: 8, topKRerank: 3 },
      analytics: {
        totalConvs: 654, totalMsgs: 3210, avgNps: 4.7, npsResponses: 89,
        totalTokens: 980000, estimatedCostUsd: 0.15,
        daily: [18,22,31,27,19,34,41,38,29,44,52,47,39,55,62,58,43,67,71,65,59,74,82,78,68,85,91,87,79,93],
        topIntents: [
          { intent: "product_inquiry", count: 1823 },
          { intent: "faq_query", count: 892 },
          { intent: "booking_intent", count: 312 },
          { intent: "complaint", count: 89 },
        ]
      }
    },
    {
      id: "hotel_vista", name: "Hotel Vista Cordillera",
      plan: "enterprise", status: "provisioning",
      contactEmail: "tech@hotelvista.com",
      configVersion: 1, createdAt: "2025-04-15T11:00:00Z",
      channels: [], ui: {}, ai: {}, limits: {}, rag: {}, analytics: { totalConvs: 0, totalMsgs: 0, avgNps: null, npsResponses: 0, totalTokens: 0, estimatedCostUsd: 0, daily: [], topIntents: [] }
    },
    {
      id: "spa_serenity", name: "Spa & Wellness Serenity",
      plan: "starter", status: "suspended",
      contactEmail: "ops@spaserenity.cl",
      configVersion: 3, createdAt: "2024-09-20T08:00:00Z",
      channels: ["widget"], ui: {}, ai: {}, limits: {}, rag: {}, analytics: { totalConvs: 187, totalMsgs: 892, avgNps: 3.8, npsResponses: 34, totalTokens: 210000, estimatedCostUsd: 0.03, daily: [], topIntents: [] }
    }
  ],

  fsm: {
    demo_turismo: {
      intents: [
        { key: "faq_query", name: "Consulta FAQ", description: "El usuario hace una pregunta general sobre el centro del vino, precios, horarios o servicios incluidos.", examples: ["¿Qué incluye el tour?", "¿Tienen estacionamiento?", "¿Dónde queda la viña?", "¿Qué días abren?"], enabled: true, priority: 1 },
        { key: "booking_intent", name: "Intención de reserva", description: "El usuario quiere reservar una experiencia, indica fecha, número de personas o pregunta por disponibilidad.", examples: ["Quiero reservar para el sábado", "¿Tienen disponibilidad para 4 personas?", "Me gustaría ir la próxima semana"], enabled: true, priority: 2 },
        { key: "product_inquiry", name: "Consulta de producto", description: "El usuario pregunta por una experiencia o tour específico: precio, duración, qué incluye.", examples: ["¿Cuánto cuesta la nocturna?", "¿Qué incluye el tasting?", "¿La visita premium incluye degustación?"], enabled: true, priority: 1 },
        { key: "human_request", name: "Solicitud de asesor", description: "El usuario pide explícitamente hablar con una persona o asesor humano.", examples: ["Quiero hablar con alguien", "¿Me pueden llamar?", "Necesito hablar con un asesor"], enabled: true, priority: 3 },
        { key: "complaint", name: "Queja o problema", description: "El usuario expresa insatisfacción, reclama o reporta un problema con el servicio.", examples: ["Tuve un problema con mi reserva", "El tour no fue lo que esperaba", "Quiero hacer una reclamación"], enabled: true, priority: 3 },
        { key: "out_of_scope", name: "Fuera de alcance", description: "El usuario pregunta algo completamente ajeno al negocio del centro del vino.", examples: ["¿Cómo se hace el vino?", "¿Qué es la vendimia?"], enabled: true, priority: 0 },
        { key: "nps_response", name: "Respuesta NPS", description: "El usuario responde a la encuesta de satisfacción post-chat con una puntuación del 1 al 5.", examples: ["5", "Le doy un 4", "Muy bueno, 5 estrellas"], enabled: true, priority: 0 },
        { key: "unclear", name: "Mensaje ambiguo", description: "El mensaje del usuario no permite determinar claramente su intención.", examples: ["Hola", "Mm", "No sé"], enabled: true, priority: 0 },
      ],
      transitions: [
        { intent: "faq_query", from_states: [], to_state: "faq_answer", action: "faq", enabled: true, botPrompt: "" },
        { intent: "product_inquiry", from_states: [], to_state: "faq_answer", action: "faq", enabled: true, botPrompt: "" },
        { intent: "booking_intent", from_states: ["discovery", "faq_answer", "greeting"], to_state: "recommending", action: "recommend", enabled: true, botPrompt: "Déjame buscar las mejores opciones para ti..." },
        { intent: "booking_intent", from_states: ["idle", "pre_chat"], to_state: "discovery", action: "discovery", enabled: true, botPrompt: "¡Perfecto! Para encontrar la experiencia ideal, cuéntame:" },
        { intent: "human_request", from_states: [], to_state: "handoff_active", action: "handoff", enabled: true, botPrompt: "" },
        { intent: "complaint", from_states: [], to_state: "handoff_active", action: "handoff", enabled: true, botPrompt: "Lamentamos que hayas tenido un problema. Te voy a conectar con un asesor." },
        { intent: "out_of_scope", from_states: [], to_state: "discovery", action: "static_reply", enabled: true, botPrompt: "", staticMessage: "Solo puedo ayudarte con información sobre el Centro del Vino Concha y Toro. ¿Te cuento sobre nuestras experiencias?" },
        { intent: "nps_response", from_states: ["post_chat"], to_state: "closed", action: "nps", enabled: true, botPrompt: "" },
      ],
      skills: [
        { action: "faq", name: "Base de Conocimiento RAG", description: "Responde preguntas usando documentos indexados sobre tours, precios y políticas.", entitySchema: [], preparationPrompt: "El usuario hace una consulta de información. Busca en la base de conocimiento y proporciona una respuesta precisa y concisa.", responseTemplates: { success: "Aquí tienes la información que encontré:", empty: "No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?", error: "En este momento no puedo responder esa consulta. ¿Puedo ayudarte con otra cosa?" }, enabled: true },
        { action: "recommend", name: "Recomendador de Experiencias", description: "Recomienda tours y experiencias basándose en preferencias del usuario.", entitySchema: [{ name: "activity_type", type: "string", description: "Tipo de experiencia (nocturna, maridaje, standard)", required: false }, { name: "date", type: "date", description: "Fecha deseada YYYY-MM-DD", required: false }, { name: "pax_count", type: "integer", description: "Número de personas", required: false }], preparationPrompt: "Extrae preferencias del usuario: tipo de experiencia, fecha deseada y número de personas.", responseTemplates: { success: "Te recomiendo estas experiencias:", empty: "No encontré experiencias disponibles para tus criterios. ¿Quieres ajustar la búsqueda?", error: "Estoy teniendo dificultades para buscar disponibilidad. ¿Puedes intentarlo en un momento?" }, enabled: true },
        { action: "handoff", name: "Escalación a Asesor", description: "Transfiere la conversación a un asesor humano vía Teams.", entitySchema: [], preparationPrompt: "", responseTemplates: { success: "Te estoy conectando con un asesor. En breve alguien te atenderá.", error: "No hay asesores disponibles en este momento. ¿Puedo tomar tus datos para que te contacten?" }, enabled: true },
        { action: "discovery", name: "Descubrimiento", description: "Hace preguntas para entender mejor las necesidades del usuario.", entitySchema: [{ name: "group_size", type: "integer", description: "Número de personas en el grupo", required: false }, { name: "occasion", type: "string", description: "Ocasión o motivo de la visita", required: false }], preparationPrompt: "Haz 1-2 preguntas concretas para entender qué tipo de experiencia busca el usuario.", responseTemplates: { followup: "Para ayudarte mejor, ¿me puedes contar más sobre tu visita?" }, enabled: true },
      ],
      states: ["idle","pre_chat","greeting","discovery","faq_answer","recommending","product_selected","checkout_init","awaiting_payment","confirmed","post_chat","handoff_active","closed"]
    }
  }
};
