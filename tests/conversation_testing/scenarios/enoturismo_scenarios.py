"""
Comprehensive test scenarios for Concha y Toro wine tourism
Complete conversation flows with expected behaviors and success criteria
"""
from typing import Dict, List
from ..models import ScenarioDefinition, ConversationOutcome, HandoffType


class EnoturismoTestScenarios:
    """Complete test scenarios for wine tourism conversations"""
    
    @staticmethod
    def get_all_scenarios() -> Dict[str, ScenarioDefinition]:
        """Returns all test scenarios for enoturismo"""
        return {
            "tour_booking_basic": EnoturismoTestScenarios.tour_booking_basic(),
            "tour_booking_specific_time": EnoturismoTestScenarios.tour_booking_specific_time(),
            "large_group_booking": EnoturismoTestScenarios.large_group_booking(),
            "price_inquiry_general": EnoturismoTestScenarios.price_inquiry_general(),
            "price_inquiry_specific": EnoturismoTestScenarios.price_inquiry_specific(),
            "schedule_availability": EnoturismoTestScenarios.schedule_availability(),
            "complaint_service": EnoturismoTestScenarios.complaint_service(),
            "complaint_severe": EnoturismoTestScenarios.complaint_severe(),
            "weather_cancellation": EnoturismoTestScenarios.weather_cancellation(),
            "gift_experience": EnoturismoTestScenarios.gift_experience(),
            "accessibility_needs": EnoturismoTestScenarios.accessibility_needs(),
            "wine_education": EnoturismoTestScenarios.wine_education(),
            "corporate_event": EnoturismoTestScenarios.corporate_event(),
            "last_minute_booking": EnoturismoTestScenarios.last_minute_booking(),
            "modification_request": EnoturismoTestScenarios.modification_request(),
        }
    
    @staticmethod
    def tour_booking_basic() -> ScenarioDefinition:
        """Basic tour booking scenario - should complete successfully"""
        return ScenarioDefinition(
            name="tour_booking_basic",
            description="User wants to book a basic wine tour",
            category="booking",
            priority="critical",
            user_inputs=[
                "Hola, quiero reservar un tour de vinos",
                "Para 2 personas",
                "Mañana por la tarde si es posible",
                "carlos@ejemplo.com",
                "Perfecto, confirmo la reserva"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_mention": ["tour disponibles", "horarios", "experiencias"],
                    "should_ask_for": ["número de personas", "fecha preferida"],
                    "tone": "welcoming"
                },
                {
                    "turn": 2, 
                    "should_mention": ["horarios disponibles", "mañana"],
                    "should_extract": {"personas": 2},
                    "should_ask_for": ["hora específica", "contacto"]
                },
                {
                    "turn": 3,
                    "should_verify": ["disponibilidad", "2 personas", "mañana tarde"],
                    "should_ask_for": ["email", "teléfono"]
                },
                {
                    "turn": 4,
                    "should_capture": {"email": "carlos@ejemplo.com"},
                    "should_provide": ["resumen reserva", "detalles confirmación"]
                },
                {
                    "turn": 5,
                    "should_provide": ["booking_id", "instrucciones llegada", "contacto"],
                    "should_confirm": "reserva completada"
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "personas": 2,
                "fecha": "mañana",
                "periodo": "tarde", 
                "email": "carlos@ejemplo.com",
                "tour_type": "básico"
            },
            success_indicators=[
                "booking_id_provided",
                "contact_information_collected", 
                "tour_details_confirmed",
                "no_handoff_required"
            ],
            min_relevance_score=0.85,
            min_accuracy_score=0.9,
            tags=["booking", "basic_flow", "success_path"]
        )
    
    @staticmethod 
    def tour_booking_specific_time() -> ScenarioDefinition:
        """Booking with specific time requirements"""
        return ScenarioDefinition(
            name="tour_booking_specific_time",
            description="User requests specific tour and time",
            category="booking",
            priority="critical",
            user_inputs=[
                "Quiero hacer la Experiencia Nocturna Casillero del Diablo",
                "Para 4 personas el sábado",
                "A las 19:00 hrs",
                "¿Incluye la cena?",
                "Perfecto, reservo para Ana García, +56912345678"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_mention": ["Experiencia Nocturna", "Casillero del Diablo", "disponibilidad"],
                    "should_ask_for": ["número personas", "fecha específica"]
                },
                {
                    "turn": 2,
                    "should_extract": {"personas": 4, "tour": "nocturna_casillero"},
                    "should_check": "disponibilidad sábado",
                    "should_ask_for": ["hora específica"]
                },
                {
                    "turn": 3,
                    "should_verify": "disponibilidad 19:00",
                    "should_mention": ["duración 3 horas", "hasta 22:00"]
                },
                {
                    "turn": 4,
                    "should_confirm": "cena incluida",
                    "should_mention": ["maridaje", "menú"]
                },
                {
                    "turn": 5,
                    "should_extract": {"nombre": "Ana García", "telefono": "+56912345678"},
                    "should_provide": ["booking_id", "confirmación"]
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "personas": 4,
                "tour_type": "experiencia_nocturna_casillero",
                "fecha": "sábado", 
                "hora": "19:00",
                "nombre": "Ana García",
                "telefono": "+56912345678",
                "incluye_cena": True
            },
            success_indicators=[
                "specific_tour_confirmed",
                "time_availability_checked",
                "inclusions_clarified",
                "complete_contact_info"
            ],
            tags=["booking", "nocturna", "specific_requirements"]
        )
    
    @staticmethod
    def large_group_booking() -> ScenarioDefinition:
        """Large group booking - should trigger handoff to sales"""
        return ScenarioDefinition(
            name="large_group_booking", 
            description="Corporate/large group needs specialized attention",
            category="booking",
            priority="critical",
            user_inputs=[
                "Necesito cotizar una experiencia para un grupo de 45 personas",
                "Es para un evento corporativo",
                "Queremos algo exclusivo con almuerzo incluido",
                "Somos de la empresa TechCorp y tenemos presupuesto flexible"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_detect": "large_group",
                    "should_mention": ["grupo corporativo", "experiencias exclusivas"],
                    "should_ask_for": ["tipo evento", "fecha", "requerimientos especiales"]
                },
                {
                    "turn": 2,
                    "should_extract": {"tipo": "corporativo", "personas": 45},
                    "should_recognize": "specialized_attention_needed"
                },
                {
                    "turn": 3,
                    "should_mention": ["experiencias personalizadas", "capacidad especial"],
                    "should_prepare": "handoff_to_sales"
                },
                {
                    "turn": 4,
                    "should_trigger": "sales_handoff",
                    "should_provide": ["contacto especialista", "timeline respuesta"]
                }
            ],
            expected_outcome=ConversationOutcome.HANDOFF,
            expected_handoff_type=HandoffType.SALES,
            handoff_trigger_keywords=["45 personas", "corporativo", "evento", "presupuesto"],
            expected_entities={
                "personas": 45,
                "tipo_evento": "corporativo",
                "empresa": "TechCorp",
                "requerimientos": ["exclusivo", "almuerzo"],
                "presupuesto": "flexible"
            },
            success_indicators=[
                "large_group_detected",
                "appropriate_handoff_triggered",
                "context_preserved_for_sales",
                "timeline_provided"
            ],
            tags=["handoff", "sales", "corporate", "large_group"]
        )
    
    @staticmethod
    def price_inquiry_general() -> ScenarioDefinition:
        """General price inquiry - should ask for specifics"""
        return ScenarioDefinition(
            name="price_inquiry_general",
            description="User asks for prices without specifying tour",
            category="inquiry",
            priority="high",
            user_inputs=[
                "¿Cuánto cuestan los tours?",
                "Para 3 personas",
                "El básico está bien"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_ask_for": ["tipo de tour", "número personas", "fecha"],
                    "should_mention": ["diferentes experiencias", "precios varían"],
                    "should_not": "give_generic_price"
                },
                {
                    "turn": 2,
                    "should_extract": {"personas": 3},
                    "should_ask_for": "tour_type_specification"
                },
                {
                    "turn": 3,
                    "should_provide": ["precio tour básico", "duración", "incluye"],
                    "should_mention": ["otras opciones disponibles"]
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "personas": 3,
                "tour_type": "básico",
                "price_interest": True
            },
            success_indicators=[
                "avoided_generic_price_response",
                "asked_for_specifics",
                "provided_detailed_pricing",
                "mentioned_alternatives"
            ],
            tags=["inquiry", "pricing", "context_gathering"]
        )
    
    @staticmethod
    def complaint_service() -> ScenarioDefinition:
        """Service complaint - moderate issue"""
        return ScenarioDefinition(
            name="complaint_service",
            description="User has complaint about recent experience",
            category="complaint",
            priority="critical",
            user_inputs=[
                "Tengo una queja sobre mi tour de ayer",
                "El guía llegó 15 minutos tarde y fue muy apresurado",
                "Esperaba una experiencia más personalizada",
                "Quiero que me devuelvan parte del dinero"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_express": "empathy",
                    "should_ask_for": ["detalles específicos", "número reserva"],
                    "tone": "apologetic"
                },
                {
                    "turn": 2,
                    "should_acknowledge": "problema válido",
                    "should_ask_for": ["más detalles", "booking_id"],
                    "should_express": "desire_to_resolve"
                },
                {
                    "turn": 3,
                    "should_validate": "concerns",
                    "should_mention": ["estándares calidad", "no típico"]
                },
                {
                    "turn": 4,
                    "should_mention": ["opciones resolución", "supervisor"],
                    "should_prepare": "handoff_to_service"
                }
            ],
            expected_outcome=ConversationOutcome.HANDOFF,
            expected_handoff_type=HandoffType.CUSTOMER_SERVICE,
            handoff_trigger_keywords=["queja", "devuelvan dinero", "mal servicio"],
            expected_entities={
                "tipo_problema": "servicio_guía",
                "severidad": "moderada",
                "fecha_tour": "ayer",
                "compensación_solicitada": "reembolso_parcial"
            },
            success_indicators=[
                "empathy_expressed",
                "details_gathered",
                "appropriate_handoff",
                "resolution_pathway_provided"
            ],
            tags=["complaint", "service_quality", "handoff"]
        )
    
    @staticmethod
    def complaint_severe() -> ScenarioDefinition:
        """Severe complaint requiring immediate escalation"""
        return ScenarioDefinition(
            name="complaint_severe",
            description="Serious safety or discrimination complaint",
            category="complaint", 
            priority="critical",
            user_inputs=[
                "Quiero presentar una queja formal muy seria",
                "Durante el tour el guía hizo comentarios inapropiados hacia mi esposa",
                "Fue completamente inaceptable y nos sentimos muy incómodos",
                "Esto es discriminación y quiero hablar con el gerente ahora"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_express": "serious_concern",
                    "should_ask_for": "brief_details",
                    "tone": "professional_serious"
                },
                {
                    "turn": 2,
                    "should_recognize": "severe_complaint",
                    "should_express": "unacceptable_behavior",
                    "should_prioritize": "immediate_escalation"
                },
                {
                    "turn": 3,
                    "should_validate": "seriousness",
                    "should_express": "commitment_to_action"
                },
                {
                    "turn": 4,
                    "should_trigger": "urgent_escalation",
                    "should_provide": "immediate_contact_path"
                }
            ],
            expected_outcome=ConversationOutcome.HANDOFF,
            expected_handoff_type=HandoffType.ESCALATION,
            handoff_trigger_keywords=["formal", "inapropiados", "discriminación", "gerente"],
            expected_entities={
                "tipo_problema": "conducta_inapropiada",
                "severidad": "alta",
                "urgencia": "inmediata",
                "escalation_level": "management"
            },
            success_indicators=[
                "severity_recognized",
                "immediate_escalation_triggered",
                "urgent_priority_assigned",
                "management_contact_provided"
            ],
            tags=["complaint", "severe", "escalation", "urgent"]
        )
    
    @staticmethod
    def accessibility_needs() -> ScenarioDefinition:
        """Accessibility requirements inquiry"""
        return ScenarioDefinition(
            name="accessibility_needs",
            description="User asking about accessibility accommodations",
            category="inquiry",
            priority="high",
            user_inputs=[
                "Mi padre usa silla de ruedas, ¿pueden acomodarlo en los tours?",
                "¿Qué experiencias son accesibles para él?",
                "¿El área de degustación es accesible?"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_acknowledge": "accessibility_importance",
                    "should_mention": ["accommodations_available", "specific_tours"],
                    "tone": "helpful_inclusive"
                },
                {
                    "turn": 2,
                    "should_provide": ["accessible_tour_options", "specific_details"],
                    "should_mention": ["rampas", "facilidades"]
                },
                {
                    "turn": 3,
                    "should_confirm": "degustación_accesible",
                    "should_offer": ["advance_coordination", "special_arrangements"]
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "accessibility_need": "silla_de_ruedas",
                "person_affected": "padre",
                "areas_of_concern": ["tours", "degustación"]
            },
            success_indicators=[
                "accessibility_addressed_positively",
                "specific_options_provided",
                "inclusive_tone_maintained",
                "special_arrangements_offered"
            ],
            tags=["accessibility", "inclusion", "special_needs"]
        )
    
    @staticmethod
    def corporate_event() -> ScenarioDefinition:
        """Corporate event planning"""
        return ScenarioDefinition(
            name="corporate_event",
            description="Planning corporate team building event",
            category="booking",
            priority="critical",
            user_inputs=[
                "Estamos planeando un evento de team building",
                "Somos 28 personas del área de tecnología",
                "Queremos algo que combine tour, almuerzo y actividades de integración",
                "El presupuesto es de aproximadamente $1,500,000 pesos"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_recognize": "corporate_event",
                    "should_ask_for": ["fecha", "duración", "objetivos específicos"]
                },
                {
                    "turn": 2,
                    "should_extract": {"personas": 28, "tipo": "team_building", "área": "tecnología"},
                    "should_mention": ["experiencias grupales", "customización"]
                },
                {
                    "turn": 3,
                    "should_identify": "complex_requirements",
                    "should_mention": ["propuesta personalizada", "coordinación especializada"]
                },
                {
                    "turn": 4,
                    "should_recognize": "specific_budget",
                    "should_trigger": "sales_handoff"
                }
            ],
            expected_outcome=ConversationOutcome.HANDOFF,
            expected_handoff_type=HandoffType.SALES,
            expected_entities={
                "tipo_evento": "team_building",
                "personas": 28,
                "área": "tecnología", 
                "presupuesto": 1500000,
                "requerimientos": ["tour", "almuerzo", "actividades"]
            },
            success_indicators=[
                "corporate_nature_recognized",
                "budget_acknowledged",
                "complexity_identified",
                "appropriate_specialist_handoff"
            ],
            tags=["corporate", "team_building", "sales_handoff"]
        )
    
    @staticmethod
    def weather_cancellation() -> ScenarioDefinition:
        """Weather-related cancellation request"""
        return ScenarioDefinition(
            name="weather_cancellation",
            description="User wants to cancel due to weather",
            category="modification",
            priority="medium",
            user_inputs=[
                "Tengo una reserva para hoy pero está lloviendo mucho",
                "¿Puedo reprogramar sin costo?", 
                "Mi booking es #CYT-12345"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_acknowledge": "weather_concern",
                    "should_ask_for": "booking_details"
                },
                {
                    "turn": 2,
                    "should_mention": ["política flexibilidad", "weather_policy"],
                    "should_ask_for": "preferred_new_date"
                },
                {
                    "turn": 3,
                    "should_extract": "booking_id",
                    "should_provide": ["reprogramming_options", "no_cost_policy"]
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "booking_id": "CYT-12345",
                "cancellation_reason": "weather",
                "reschedule_request": True
            },
            success_indicators=[
                "weather_policy_explained",
                "booking_identified",
                "flexible_options_provided"
            ],
            tags=["cancellation", "weather", "flexibility"]
        )
    
    @staticmethod
    def gift_experience() -> ScenarioDefinition:
        """Gift certificate purchase"""
        return ScenarioDefinition(
            name="gift_experience",
            description="User wants to buy experience as gift",
            category="booking",
            priority="medium",
            user_inputs=[
                "Quiero regalar una experiencia de vinos para mi jefe",
                "¿Tienen gift cards o algo así?",
                "Algo elegante para impresionar"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_mention": ["gift certificates", "experiencias regalo"],
                    "should_ask_for": ["tipo experiencia", "presupuesto aproximado"]
                },
                {
                    "turn": 2,
                    "should_provide": ["gift_options", "certificates_available"],
                    "should_mention": ["presentación elegante"]
                },
                {
                    "turn": 3,
                    "should_recommend": "premium_experiences",
                    "should_mention": ["packaging", "validez"]
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "gift_purpose": True,
                "recipient": "jefe",
                "preference": "elegante",
                "gift_type": "experience"
            },
            success_indicators=[
                "gift_nature_recognized",
                "appropriate_options_suggested",
                "premium_positioning"
            ],
            tags=["gift", "premium", "corporate_gift"]
        )
    
    @staticmethod
    def wine_education() -> ScenarioDefinition:
        """Educational wine inquiry"""
        return ScenarioDefinition(
            name="wine_education",
            description="User asking about learning wine knowledge",
            category="inquiry", 
            priority="medium",
            user_inputs=[
                "Soy nuevo en el mundo del vino",
                "¿Tienen tours educativos para principiantes?",
                "Quiero aprender sobre cepas y maridajes"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_acknowledge": "beginner_friendly",
                    "should_mention": ["tours educativos", "nivel principiante"]
                },
                {
                    "turn": 2,
                    "should_provide": ["educational_options", "beginner_tours"],
                    "should_mention": ["guías especializados"]
                },
                {
                    "turn": 3,
                    "should_highlight": ["cepas", "maridajes", "degustación guiada"],
                    "should_recommend": "specific_educational_tour"
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "experience_level": "principiante",
                "learning_interests": ["cepas", "maridajes"],
                "tour_type": "educativo"
            },
            success_indicators=[
                "beginner_level_recognized",
                "educational_focus_maintained",
                "specific_recommendations_provided"
            ],
            tags=["education", "beginner", "learning"]
        )
    
    @staticmethod
    def last_minute_booking() -> ScenarioDefinition:
        """Last minute booking request"""
        return ScenarioDefinition(
            name="last_minute_booking",
            description="User wants to book for today/tomorrow",
            category="booking",
            priority="medium",
            user_inputs=[
                "¿Tienen disponibilidad para hoy en la tarde?",
                "Somos 2 personas y acabamos de decidir venir",
                "¿Qué horarios quedan libres?"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_check": "today_availability",
                    "should_ask_for": "número_personas"
                },
                {
                    "turn": 2,
                    "should_extract": {"personas": 2, "urgencia": "hoy"},
                    "should_mention": "checking_real_time_availability"
                },
                {
                    "turn": 3,
                    "should_provide": ["available_times_today", "last_minute_options"],
                    "should_mention": ["confirmación inmediata"]
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "personas": 2,
                "fecha": "hoy",
                "periodo": "tarde",
                "booking_type": "last_minute"
            },
            success_indicators=[
                "urgency_recognized",
                "real_time_availability_checked",
                "immediate_options_provided"
            ],
            tags=["last_minute", "availability", "urgent"]
        )
    
    @staticmethod
    def modification_request() -> ScenarioDefinition:
        """Existing booking modification"""
        return ScenarioDefinition(
            name="modification_request",
            description="User wants to modify existing reservation",
            category="modification",
            priority="medium", 
            user_inputs=[
                "Necesito cambiar mi reserva del sábado",
                "Quiero cambiarla para el domingo en la mañana",
                "Mi booking es CYT-67890"
            ],
            expected_assistant_behaviors=[
                {
                    "turn": 1,
                    "should_ask_for": ["booking_id", "new_preferences"],
                    "should_mention": "modification_policy"
                },
                {
                    "turn": 2,
                    "should_extract": {"new_date": "domingo", "new_time": "mañana"},
                    "should_mention": "checking_new_availability"
                },
                {
                    "turn": 3,
                    "should_verify": "booking_CYT-67890",
                    "should_check": "sunday_morning_availability",
                    "should_provide": "modification_options"
                }
            ],
            expected_outcome=ConversationOutcome.SUCCESS,
            expected_entities={
                "booking_id": "CYT-67890",
                "original_date": "sábado",
                "new_date": "domingo", 
                "new_time": "mañana",
                "modification_type": "date_change"
            },
            success_indicators=[
                "booking_identified",
                "new_availability_checked", 
                "modification_completed"
            ],
            tags=["modification", "reschedule", "booking_management"]
        )