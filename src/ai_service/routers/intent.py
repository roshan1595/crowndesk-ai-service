"""
CrownDesk V2 - Intent Classification Router
Per plan.txt Section 16: Voice Receptionist (Intent Classification)

Endpoints:
- POST /intent/classify - Classify patient intent from text/voice
- POST /intent/extract-entities - Extract entities from patient message
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_service.services.intent_service import IntentService, get_intent_service

router = APIRouter()


class ClassifyIntentRequest(BaseModel):
    """Request to classify patient intent."""

    tenant_id: str
    message: str
    context: Optional[Dict] = None  # Previous conversation context


class IntentResult(BaseModel):
    """Classification result for an intent."""

    intent: str
    confidence: float
    entities: Dict[str, str]


class ClassifyIntentResponse(BaseModel):
    """Response from intent classification."""

    primary_intent: IntentResult
    secondary_intents: List[IntentResult]
    suggested_response: str
    requires_human: bool


class ExtractEntitiesRequest(BaseModel):
    """Request to extract entities from text."""

    tenant_id: str
    message: str


class ExtractEntitiesResponse(BaseModel):
    """Response with extracted entities."""

    entities: Dict[str, str]
    confidence: float


# Supported intents per plan.txt Section 16
SUPPORTED_INTENTS = [
    "schedule_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "check_insurance",
    "billing_inquiry",
    "request_records",
    "emergency",
    "general_inquiry",
    "prescription_refill",
    "speak_to_human",
]


@router.post("/classify", response_model=ClassifyIntentResponse)
async def classify_intent(
    request: ClassifyIntentRequest,
    intent_service: IntentService = Depends(get_intent_service),
):
    """
    Classify patient intent from text/voice input.

    Per plan.txt Section 16:
    - Uses LLM to classify intent
    - Extracts relevant entities (dates, times, procedures)
    - Returns suggested response for voice/chat bot
    """
    try:
        result = await intent_service.classify(
            tenant_id=request.tenant_id,
            message=request.message,
            context=request.context,
        )
        return ClassifyIntentResponse(
            primary_intent=IntentResult(
                intent=result["primary_intent"]["intent"],
                confidence=result["primary_intent"]["confidence"],
                entities=result["primary_intent"]["entities"],
            ),
            secondary_intents=[
                IntentResult(
                    intent=i["intent"],
                    confidence=i["confidence"],
                    entities=i["entities"],
                )
                for i in result.get("secondary_intents", [])
            ],
            suggested_response=result["suggested_response"],
            requires_human=result["requires_human"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-entities", response_model=ExtractEntitiesResponse)
async def extract_entities(
    request: ExtractEntitiesRequest,
    intent_service: IntentService = Depends(get_intent_service),
):
    """
    Extract entities from patient message.

    Extracts:
    - Dates and times
    - Procedure types
    - Insurance information
    - Patient identifiers
    """
    try:
        result = await intent_service.extract_entities(
            tenant_id=request.tenant_id,
            message=request.message,
        )
        return ExtractEntitiesResponse(
            entities=result["entities"],
            confidence=result["confidence"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported-intents")
async def get_supported_intents():
    """Get list of supported intents."""
    return {"intents": SUPPORTED_INTENTS}


# ===========================================
# Chat Endpoint for Frontend AI Sidebar
# ===========================================

class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request for chat completion."""
    messages: List[ChatMessage]
    tenant_id: Optional[str] = None
    stream: bool = False


class ToolCallResult(BaseModel):
    """Result of a tool call."""
    id: str
    name: str
    arguments: Dict
    result: Optional[Dict] = None
    error: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    response: str
    tool_calls: Optional[List[ToolCallResult]] = None
    requires_human: bool = False


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    intent_service: IntentService = Depends(get_intent_service),
):
    """
    Chat endpoint for the AI sidebar.
    
    Handles conversational interactions with the AI assistant.
    Supports basic Q&A and appointment-related queries.
    """
    try:
        # Get the last user message
        user_messages = [m for m in request.messages if m.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found")
        
        last_message = user_messages[-1].content
        
        # Build conversation context
        context = {
            "conversation_history": [
                {"role": m.role, "content": m.content}
                for m in request.messages[-10:]  # Last 10 messages
            ]
        }
        
        # Classify intent first
        intent_result = await intent_service.classify(
            tenant_id=request.tenant_id or "default",
            message=last_message,
            context=context,
        )
        
        # Generate response based on intent
        response_text = intent_result.get("suggested_response", "")
        
        # If no good response, generate a generic one
        if not response_text or len(response_text) < 10:
            response_text = await intent_service.generate_chat_response(
                tenant_id=request.tenant_id or "default",
                message=last_message,
                context=context,
            )
        
        return ChatResponse(
            response=response_text,
            tool_calls=None,  # Tool calls would be populated if we invoke functions
            requires_human=intent_result.get("requires_human", False),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Return a friendly error message
        return ChatResponse(
            response="I apologize, but I'm having trouble processing your request right now. Please try again or contact our office directly for assistance.",
            requires_human=True,
        )

