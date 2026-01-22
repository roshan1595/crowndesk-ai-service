"""
CrownDesk V2 - Intent Classification Service
Per plan.txt Section 16: Voice Receptionist

Handles:
- Patient intent classification from text/voice
- Entity extraction (dates, procedures, etc.)
- Response suggestion for voice/chat bots
"""

import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from ai_service.config import get_settings

# Intent definitions with example phrases
INTENT_DEFINITIONS = {
    "schedule_appointment": {
        "description": "Patient wants to schedule a new appointment",
        "examples": [
            "I'd like to schedule a cleaning",
            "Can I make an appointment for next week",
            "I need to see the dentist",
        ],
    },
    "reschedule_appointment": {
        "description": "Patient wants to change existing appointment",
        "examples": [
            "I need to reschedule my appointment",
            "Can we move my appointment to a different day",
            "I can't make it on Tuesday, can we change it",
        ],
    },
    "cancel_appointment": {
        "description": "Patient wants to cancel appointment",
        "examples": [
            "I need to cancel my appointment",
            "Please cancel my visit",
            "I won't be able to come in",
        ],
    },
    "check_insurance": {
        "description": "Patient has insurance questions",
        "examples": [
            "Do you accept my insurance",
            "What's my coverage",
            "Is this procedure covered",
        ],
    },
    "billing_inquiry": {
        "description": "Patient has billing questions",
        "examples": [
            "I have a question about my bill",
            "How much do I owe",
            "Can I set up a payment plan",
        ],
    },
    "emergency": {
        "description": "Patient has a dental emergency",
        "examples": [
            "I'm in severe pain",
            "My tooth broke",
            "It's an emergency",
        ],
    },
    "speak_to_human": {
        "description": "Patient wants to speak to a person",
        "examples": [
            "Can I speak to someone",
            "Transfer me to a person",
            "I want to talk to a human",
        ],
    },
}


class IntentEntity(BaseModel):
    """Entity extracted from patient message."""
    type: str = Field(description="Entity type: date_reference, procedure_type, insurance_provider, etc.")
    value: str = Field(description="Extracted value")
    confidence: float = Field(description="Confidence score 0-1")


class IntentClassification(BaseModel):
    """Structured intent classification result."""
    intent: str = Field(description="Primary intent from INTENT_DEFINITIONS keys")
    confidence: float = Field(description="Confidence score 0-1")
    entities: List[IntentEntity] = Field(default_factory=list, description="Extracted entities")
    reasoning: str = Field(description="Brief explanation of classification")


class IntentService:
    """Intent classification service for voice/chat."""

    def __init__(self):
        self.settings = get_settings()
        self.openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def classify(
        self,
        tenant_id: str,
        message: str,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Classify patient intent from message using LLM.

        Uses OpenAI structured outputs for reliable intent classification.
        """
        # Build intent definitions for prompt
        intent_list = []
        for key, definition in INTENT_DEFINITIONS.items():
            examples_str = "\n    - ".join(definition["examples"])
            intent_list.append(f"  - {key}: {definition['description']}\n    Examples:\n    - {examples_str}")
        
        intent_descriptions = "\n".join(intent_list)
        
        # Build prompt with context
        context_str = ""
        if context:
            context_str = f"\n\nPrevious context:\n{json.dumps(context, indent=2)}"
        
        prompt = f"""You are analyzing a patient message to a dental practice.

Available intents:
{intent_descriptions}

Classify the following patient message into ONE of the above intents.
Extract any relevant entities like dates, times, procedure types, insurance providers.

Patient message: "{message}"{context_str}

Provide your classification with confidence score and reasoning."""

        try:
            # Use structured outputs for reliable parsing
            response = await self.openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a dental practice AI assistant that classifies patient intents."},
                    {"role": "user", "content": prompt}
                ],
                response_format=IntentClassification,
                temperature=0.1,
            )
            
            classification = response.choices[0].message.parsed
            
            # Convert entities to dict format
            entities = {
                entity.type: entity.value 
                for entity in classification.entities
            }
            
            return {
                "primary_intent": {
                    "intent": classification.intent,
                    "confidence": classification.confidence,
                    "entities": entities,
                    "reasoning": classification.reasoning,
                },
                "secondary_intents": [],
                "suggested_response": self._generate_response(classification.intent),
                "requires_human": classification.intent in ["emergency", "speak_to_human"],
            }
            
        except Exception as e:
            # Fallback to simple classification on error
            print(f"LLM classification error: {e}, falling back to keyword-based")
            primary_intent = self._simple_classify(message)
            
            return {
                "primary_intent": {
                    "intent": primary_intent,
                    "confidence": 0.75,
                    "entities": self._extract_entities_simple(message),
                    "reasoning": "Fallback keyword-based classification",
                },
                "secondary_intents": [],
                "suggested_response": self._generate_response(primary_intent),
                "requires_human": primary_intent in ["emergency", "speak_to_human"],
            }

    async def extract_entities(
        self,
        tenant_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """Extract entities from patient message using LLM."""
        prompt = f"""Extract entities from this patient message to a dental practice.

Look for:
- date_reference (e.g., "next week", "tomorrow", "Monday")
- time_preference (e.g., "morning", "2pm", "afternoon")
- procedure_type (e.g., "cleaning", "filling", "root canal")
- insurance_provider (e.g., "Delta Dental", "Cigna")
- urgency (e.g., "emergency", "urgent", "as soon as possible")

Patient message: "{message}"

Return only the entities you find with confidence scores."""

        try:
            response = await self.openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a dental practice AI assistant that extracts entities from patient messages."},
                    {"role": "user", "content": prompt}
                ],
                response_format=IntentClassification,
                temperature=0.1,
            )
            
            classification = response.choices[0].message.parsed
            
            # Convert to dict format
            entities = {
                entity.type: entity.value 
                for entity in classification.entities
            }
            
            # Calculate average confidence
            avg_confidence = (
                sum(e.confidence for e in classification.entities) / len(classification.entities)
                if classification.entities else 0.0
            )
            
            return {
                "entities": entities,
                "confidence": avg_confidence,
            }
            
        except Exception as e:
            print(f"Entity extraction error: {e}, falling back to simple extraction")
            entities = self._extract_entities_simple(message)
            return {
                "entities": entities,
                "confidence": 0.70,
            }

    def _simple_classify(self, message: str) -> str:
        """Simple keyword-based classification (fallback when LLM fails)."""
        message_lower = message.lower()

        if any(word in message_lower for word in ["emergency", "pain", "broken", "urgent"]):
            return "emergency"
        if any(word in message_lower for word in ["cancel"]):
            return "cancel_appointment"
        if any(word in message_lower for word in ["reschedule", "change", "move"]):
            return "reschedule_appointment"
        if any(word in message_lower for word in ["schedule", "appointment", "book"]):
            return "schedule_appointment"
        if any(word in message_lower for word in ["insurance", "coverage", "accept"]):
            return "check_insurance"
        if any(word in message_lower for word in ["bill", "payment", "owe", "cost"]):
            return "billing_inquiry"
        if any(word in message_lower for word in ["human", "person", "someone", "transfer"]):
            return "speak_to_human"

        return "general_inquiry"

    def _extract_entities_simple(self, message: str) -> Dict[str, str]:
        """Simple entity extraction (fallback when LLM fails)."""
        entities: Dict[str, str] = {}

        # Basic keyword detection for common entities
        message_lower = message.lower()

        if "next week" in message_lower:
            entities["date_reference"] = "next_week"
        elif "tomorrow" in message_lower:
            entities["date_reference"] = "tomorrow"
        elif "today" in message_lower:
            entities["date_reference"] = "today"
        
        if "cleaning" in message_lower or "prophy" in message_lower:
            entities["procedure_type"] = "cleaning"
        elif "filling" in message_lower:
            entities["procedure_type"] = "filling"
        elif "root canal" in message_lower:
            entities["procedure_type"] = "root_canal"
        elif "crown" in message_lower:
            entities["procedure_type"] = "crown"
        
        if "morning" in message_lower:
            entities["time_preference"] = "morning"
        elif "afternoon" in message_lower:
            entities["time_preference"] = "afternoon"
        elif "evening" in message_lower:
            entities["time_preference"] = "evening"

        return entities

    def _generate_response(self, intent: str) -> str:
        """Generate suggested response for intent."""
        responses = {
            "schedule_appointment": "I'd be happy to help you schedule an appointment. What day works best for you?",
            "reschedule_appointment": "Of course, I can help you reschedule. When would you like to move your appointment to?",
            "cancel_appointment": "I can help you cancel your appointment. Can you confirm the date of the appointment you'd like to cancel?",
            "check_insurance": "I can look into your insurance coverage. What is your insurance provider?",
            "billing_inquiry": "I can help with billing questions. Can you provide your patient ID or date of birth?",
            "emergency": "I'm transferring you to our emergency line right away. Please hold.",
            "speak_to_human": "Let me connect you with one of our team members. Please hold.",
            "general_inquiry": "I'd be happy to help. Could you provide more details about your question?",
        }
        return responses.get(intent, responses["general_inquiry"])

    async def generate_chat_response(
        self,
        tenant_id: str,
        messages: List[Dict[str, str]],
        intent: str,
        entities: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a conversational response for the AI chat sidebar.
        
        Args:
            tenant_id: The tenant/organization ID
            messages: List of chat messages with 'role' and 'content'
            intent: The classified intent
            entities: Extracted entities from the user message
            
        Returns:
            Dict with 'response', 'tool_calls', and 'requires_human' keys
        """
        # Get the latest user message
        user_message = messages[-1]["content"] if messages else ""
        
        # Build conversation history for context
        conversation_context = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in messages[-5:]  # Last 5 messages for context
        ])
        
        # Check if this requires human handoff
        requires_human = intent in ["emergency", "speak_to_human"]
        
        # Tool calls that might be needed based on intent
        tool_calls = []
        
        # Generate intent-specific responses with potential tool calls
        if intent == "schedule_appointment":
            if "date_reference" in entities:
                tool_calls.append({
                    "tool": "check_availability",
                    "arguments": {"date_reference": entities.get("date_reference")},
                    "status": "pending"
                })
            response = self._get_scheduling_response(entities, conversation_context)
            
        elif intent == "reschedule_appointment":
            tool_calls.append({
                "tool": "get_patient_appointments",
                "arguments": {},
                "status": "pending"
            })
            response = "I can help you reschedule your appointment. Let me look up your upcoming appointments. Can you confirm your name or date of birth?"
            
        elif intent == "cancel_appointment":
            tool_calls.append({
                "tool": "get_patient_appointments",
                "arguments": {},
                "status": "pending"
            })
            response = "I can help you cancel your appointment. To find your appointment, could you please provide your name or the date of the appointment?"
            
        elif intent == "check_insurance":
            if "insurance_provider" in entities:
                tool_calls.append({
                    "tool": "verify_insurance",
                    "arguments": {"provider": entities.get("insurance_provider")},
                    "status": "pending"
                })
            response = self._get_insurance_response(entities)
            
        elif intent == "billing_inquiry":
            tool_calls.append({
                "tool": "get_patient_balance",
                "arguments": {},
                "status": "pending"
            })
            response = "I can help with your billing question. To look up your account, could you please provide your name or date of birth?"
            
        elif intent == "emergency":
            response = (
                "🚨 **This sounds like a dental emergency.** I'm immediately flagging this for our team.\n\n"
                "**If you're experiencing:**\n"
                "- Severe pain\n"
                "- Heavy bleeding\n"
                "- Swelling affecting breathing\n\n"
                "**Please call our emergency line directly or go to the nearest emergency room.**\n\n"
                "A team member will be with you shortly."
            )
            tool_calls.append({
                "tool": "transfer_to_human",
                "arguments": {"priority": "emergency", "reason": user_message},
                "status": "executing"
            })
            
        elif intent == "speak_to_human":
            response = (
                "I understand you'd like to speak with a team member. "
                "I'm connecting you now. Please hold for a moment."
            )
            tool_calls.append({
                "tool": "transfer_to_human",
                "arguments": {"priority": "normal", "reason": "Patient requested human assistance"},
                "status": "executing"
            })
            
        else:
            # General inquiry
            response = self._get_general_response(user_message, conversation_context)
        
        return {
            "response": response,
            "tool_calls": tool_calls,
            "requires_human": requires_human,
            "intent": intent,
            "entities": entities,
        }
    
    def _get_scheduling_response(self, entities: Dict, context: str) -> str:
        """Generate scheduling-specific response."""
        procedure = entities.get("procedure_type", "")
        date_ref = entities.get("date_reference", "")
        
        if procedure and date_ref:
            return f"I'd be happy to help you schedule a {procedure} appointment for {date_ref}. Let me check our availability. What time of day works best for you - morning, afternoon, or evening?"
        elif procedure:
            return f"I can help you schedule a {procedure} appointment. When would be a good time for you?"
        elif date_ref:
            return f"I can check our availability for {date_ref}. What type of appointment do you need - a cleaning, exam, or something else?"
        else:
            return "I'd be happy to help you schedule an appointment. What type of visit do you need, and when would be convenient for you?"
    
    def _get_insurance_response(self, entities: Dict) -> str:
        """Generate insurance-specific response."""
        if "insurance_provider" in entities:
            return f"Let me check if we accept {entities['insurance_provider']}. One moment please..."
        return "I can help with insurance questions. What's your insurance provider, and what would you like to know about your coverage?"
    
    def _get_general_response(self, message: str, context: str) -> str:
        """Generate general inquiry response."""
        # Common questions patterns
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["hour", "open", "close", "when"]):
            return "Our office hours are Monday through Friday, 8 AM to 5 PM, and Saturday 9 AM to 2 PM. Is there a specific day you'd like to schedule?"
        
        if any(word in message_lower for word in ["location", "address", "where", "directions"]):
            return "I can provide our office location. However, I don't have the specific address loaded right now. Let me connect you with someone who can help with directions."
        
        if any(word in message_lower for word in ["service", "offer", "do you"]):
            return "We offer a full range of dental services including cleanings, exams, fillings, crowns, root canals, extractions, and cosmetic dentistry. What specific service are you interested in?"
        
        return "I'm here to help! I can assist with scheduling appointments, answering insurance questions, and billing inquiries. What can I help you with today?"


def get_intent_service() -> IntentService:
    """Dependency injection for intent service."""
    return IntentService()
