"""
CrownDesk V2 - Retell AI Voice Agent Router
Per plan.txt Section 13: AI Receptionist

WebSocket server for Retell AI Custom LLM integration.
Handles voice conversations, function calling, and human handoff.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from pydantic import BaseModel

from ai_service.config import get_settings
from ai_service.services.retell_service import RetellService
from ai_service.services.ai_orchestrator import AIOrchestrator
from ai_service.services.guardrails import HIPAAGuardrails

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Pydantic Models for Retell Protocol
# ============================================================================

class Utterance(BaseModel):
    """A single utterance in the conversation."""
    role: str  # "agent" or "user"
    content: str


class RetellRequest(BaseModel):
    """Request from Retell AI to our server."""
    interaction_type: str  # "update_only", "response_required", "reminder_required", "ping_pong", "call_details"
    response_id: Optional[int] = None
    transcript: Optional[List[Utterance]] = None
    transcript_with_tool_calls: Optional[List[Dict]] = None
    turntaking: Optional[str] = None  # "agent_turn" or "user_turn"
    call: Optional[Dict] = None  # For call_details event
    timestamp: Optional[int] = None  # For ping_pong event


class RetellResponse(BaseModel):
    """Response from our server to Retell AI."""
    response_type: str  # "response", "config", "ping_pong", "agent_interrupt", "tool_call_invocation", "tool_call_result"
    response_id: Optional[int] = None
    content: Optional[str] = None
    content_complete: Optional[bool] = None
    end_call: Optional[bool] = None
    transfer_number: Optional[str] = None
    no_interruption_allowed: Optional[bool] = None
    config: Optional[Dict] = None
    timestamp: Optional[int] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    arguments: Optional[str] = None


class RetellConfig(BaseModel):
    """Initial config sent to Retell on connection."""
    auto_reconnect: bool = True
    call_details: bool = True
    transcript_with_tool_calls: bool = True


# ============================================================================
# Dental Practice Voice Agent Prompts
# ============================================================================

SYSTEM_PROMPT = """You are a friendly and professional AI receptionist for a dental practice. Your name is "CrownDesk Assistant".

## Your Capabilities:
- Schedule, reschedule, and cancel appointments
- Answer questions about office hours, location, and services
- Look up patient information (after identity verification)
- Check insurance information
- Provide general information about dental procedures
- Transfer to a human receptionist when needed

## Important Rules:
1. NEVER provide medical diagnoses or treatment recommendations
2. NEVER guarantee insurance coverage amounts
3. ALWAYS verify patient identity before disclosing personal information (ask for name and date of birth)
4. If unsure or the patient requests, offer to transfer to a human receptionist
5. Be concise - aim for responses under 2-3 sentences when possible
6. Speak naturally and conversationally
7. If there's an emergency, advise them to call 911 or go to the nearest emergency room

## Conversation Style:
- Warm and welcoming
- Professional but not robotic
- Patient and understanding
- Clear and easy to understand

## Opening Greeting:
When the call starts, greet the patient warmly and ask how you can help them today.
"""

BEGIN_MESSAGE = "Hello! Thank you for calling. This is the CrownDesk dental practice assistant. How can I help you today?"


# ============================================================================
# Function Definitions for Tool Calling
# ============================================================================

AVAILABLE_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new appointment for a patient. Use this when the patient wants to schedule a visit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "The patient's full name"
                    },
                    "patient_dob": {
                        "type": "string",
                        "description": "The patient's date of birth (MM/DD/YYYY format)"
                    },
                    "appointment_type": {
                        "type": "string",
                        "enum": ["cleaning", "checkup", "emergency", "consultation", "follow_up", "other"],
                        "description": "The type of appointment"
                    },
                    "preferred_date": {
                        "type": "string",
                        "description": "Preferred appointment date"
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Preferred appointment time (morning, afternoon, or specific time)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any additional notes or concerns"
                    }
                },
                "required": ["patient_name", "appointment_type", "preferred_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date to check availability for"
                    },
                    "appointment_type": {
                        "type": "string",
                        "description": "The type of appointment to check slots for"
                    }
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "The patient's full name"
                    },
                    "patient_dob": {
                        "type": "string",
                        "description": "The patient's date of birth for verification"
                    },
                    "current_appointment_date": {
                        "type": "string",
                        "description": "The current appointment date to reschedule"
                    },
                    "new_preferred_date": {
                        "type": "string",
                        "description": "The new preferred date"
                    },
                    "new_preferred_time": {
                        "type": "string",
                        "description": "The new preferred time"
                    }
                },
                "required": ["patient_name", "patient_dob", "new_preferred_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "The patient's full name"
                    },
                    "patient_dob": {
                        "type": "string",
                        "description": "The patient's date of birth for verification"
                    },
                    "appointment_date": {
                        "type": "string",
                        "description": "The appointment date to cancel"
                    },
                    "cancellation_reason": {
                        "type": "string",
                        "description": "Reason for cancellation"
                    }
                },
                "required": ["patient_name", "patient_dob"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_patient",
            "description": "Look up a patient's information. Requires identity verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "The patient's full name"
                    },
                    "patient_dob": {
                        "type": "string",
                        "description": "The patient's date of birth for verification"
                    }
                },
                "required": ["patient_name", "patient_dob"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_insurance_info",
            "description": "Get insurance coverage information for a verified patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "The patient's full name"
                    },
                    "patient_dob": {
                        "type": "string",
                        "description": "The patient's date of birth for verification"
                    },
                    "procedure_type": {
                        "type": "string",
                        "description": "Optional: specific procedure to check coverage for"
                    }
                },
                "required": ["patient_name", "patient_dob"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "Transfer the call to a human receptionist. Use when patient explicitly requests it or when you cannot help.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for the transfer"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message to say before transferring"
                    }
                },
                "required": ["reason", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": "End the call politely when the conversation is complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The farewell message to say before ending the call"
                    }
                },
                "required": ["message"]
            }
        }
    }
]


# ============================================================================
# WebSocket Endpoint for Retell AI Custom LLM
# ============================================================================

@router.websocket("/ws/retell/{call_id}")
async def retell_websocket(
    websocket: WebSocket,
    call_id: str,
    tenant_id: Optional[str] = Query(None, alias="tenant_id")
):
    """
    WebSocket endpoint for Retell AI Custom LLM integration.
    
    This endpoint handles:
    - Connection lifecycle management
    - Real-time transcript processing
    - LLM response generation with streaming
    - Function calling for appointment management
    - Human handoff when needed
    
    Protocol: https://docs.retellai.com/api-references/llm-websocket
    """
    await websocket.accept()
    logger.info(f"Retell WebSocket connected: call_id={call_id}, tenant_id={tenant_id}")
    
    # Initialize services
    settings = get_settings()
    retell_service = RetellService(settings)
    ai_orchestrator = AIOrchestrator(settings)
    guardrails = HIPAAGuardrails()
    
    # Call state
    call_state = {
        "call_id": call_id,
        "tenant_id": tenant_id,
        "started_at": datetime.utcnow().isoformat(),
        "patient_verified": False,
        "patient_id": None,
        "conversation_history": [],
        "function_calls": [],
        "last_response_id": 0
    }
    
    try:
        # Send initial config
        config_event = {
            "response_type": "config",
            "config": {
                "auto_reconnect": True,
                "call_details": True,
                "transcript_with_tool_calls": True
            }
        }
        await websocket.send_json(config_event)
        
        # Send begin message
        begin_response = {
            "response_type": "response",
            "response_id": 0,
            "content": BEGIN_MESSAGE,
            "content_complete": True,
            "end_call": False
        }
        await websocket.send_json(begin_response)
        
        # Main message loop
        while True:
            try:
                data = await websocket.receive_text()
                request_data = json.loads(data)
                
                interaction_type = request_data.get("interaction_type")
                
                # Handle different event types
                if interaction_type == "ping_pong":
                    # Respond to keep-alive ping
                    pong_response = {
                        "response_type": "ping_pong",
                        "timestamp": int(datetime.utcnow().timestamp() * 1000)
                    }
                    await websocket.send_json(pong_response)
                    
                elif interaction_type == "call_details":
                    # Store call details
                    call_state["call_details"] = request_data.get("call", {})
                    logger.info(f"Call details received for {call_id}")
                    
                elif interaction_type == "update_only":
                    # Process transcript update (no response needed)
                    transcript = request_data.get("transcript", [])
                    call_state["conversation_history"] = transcript
                    
                    # Check for turntaking
                    turntaking = request_data.get("turntaking")
                    if turntaking:
                        logger.debug(f"Turn taking: {turntaking}")
                    
                elif interaction_type in ["response_required", "reminder_required"]:
                    # Need to generate a response
                    response_id = request_data.get("response_id", 0)
                    transcript = request_data.get("transcript", [])
                    call_state["conversation_history"] = transcript
                    call_state["last_response_id"] = response_id
                    
                    # Generate response using AI orchestrator
                    response = await generate_llm_response(
                        ai_orchestrator=ai_orchestrator,
                        guardrails=guardrails,
                        retell_service=retell_service,
                        websocket=websocket,
                        call_state=call_state,
                        transcript=transcript,
                        response_id=response_id,
                        is_reminder=(interaction_type == "reminder_required")
                    )
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                continue
                
    except WebSocketDisconnect:
        logger.info(f"Retell WebSocket disconnected: call_id={call_id}")
    except Exception as e:
        logger.error(f"Error in Retell WebSocket: {e}", exc_info=True)
    finally:
        # Log call completion
        call_state["ended_at"] = datetime.utcnow().isoformat()
        logger.info(f"Call ended: {call_id}, duration: {call_state.get('ended_at')}")
        
        # Store call transcript (will be implemented in call storage service)
        # await store_call_transcript(call_state)


async def generate_llm_response(
    ai_orchestrator: AIOrchestrator,
    guardrails: HIPAAGuardrails,
    retell_service: RetellService,
    websocket: WebSocket,
    call_state: Dict,
    transcript: List[Dict],
    response_id: int,
    is_reminder: bool = False
) -> None:
    """
    Generate LLM response for Retell AI.
    
    Handles:
    - Converting transcript to LLM messages
    - Applying HIPAA guardrails
    - Function calling
    - Streaming response back to Retell
    """
    try:
        # Convert transcript to messages
        messages = []
        
        # System prompt
        messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT
        })
        
        # Add conversation history
        for utterance in transcript:
            role = "assistant" if utterance.get("role") == "agent" else "user"
            content = utterance.get("content", "")
            if content:
                messages.append({
                    "role": role,
                    "content": content
                })
        
        # Add reminder prompt if needed
        if is_reminder:
            messages.append({
                "role": "user",
                "content": "(The user has been silent for a while. Check if they need any help or are still there.)"
            })
        
        # Check guardrails on the last user message
        if transcript:
            last_user_message = None
            for utterance in reversed(transcript):
                if utterance.get("role") == "user":
                    last_user_message = utterance.get("content", "")
                    break
            
            if last_user_message:
                guardrail_check = guardrails.check_message(last_user_message)
                if guardrail_check.get("blocked"):
                    # Send guardrail response
                    response = {
                        "response_type": "response",
                        "response_id": response_id,
                        "content": guardrail_check.get("message", "I apologize, but I'm not able to help with that. Would you like to speak with our staff?"),
                        "content_complete": True,
                        "end_call": False
                    }
                    await websocket.send_json(response)
                    return
        
        # Generate LLM response with function calling
        llm_response = await ai_orchestrator.generate_voice_response(
            messages=messages,
            functions=AVAILABLE_FUNCTIONS,
            tenant_id=call_state.get("tenant_id")
        )
        
        # Handle function calls
        if llm_response.get("function_call"):
            func_call = llm_response["function_call"]
            func_name = func_call.get("name")
            func_args = func_call.get("arguments", {})
            
            # Send tool call invocation event
            tool_call_id = str(uuid4())
            invocation_event = {
                "response_type": "tool_call_invocation",
                "tool_call_id": tool_call_id,
                "name": func_name,
                "arguments": json.dumps(func_args) if isinstance(func_args, dict) else func_args
            }
            await websocket.send_json(invocation_event)
            
            # Execute function
            func_result = await execute_function(
                func_name=func_name,
                func_args=func_args,
                call_state=call_state,
                retell_service=retell_service
            )
            
            # Send tool call result event
            result_event = {
                "response_type": "tool_call_result",
                "tool_call_id": tool_call_id,
                "content": json.dumps(func_result) if isinstance(func_result, dict) else str(func_result)
            }
            await websocket.send_json(result_event)
            
            # Handle special functions
            if func_name == "end_call":
                response = {
                    "response_type": "response",
                    "response_id": response_id,
                    "content": func_args.get("message", "Thank you for calling. Goodbye!"),
                    "content_complete": True,
                    "end_call": True
                }
                await websocket.send_json(response)
                return
                
            elif func_name == "transfer_to_human":
                # Get transfer number from settings or call state
                transfer_number = call_state.get("transfer_number", "+1234567890")  # Default for testing
                response = {
                    "response_type": "response",
                    "response_id": response_id,
                    "content": func_args.get("message", "I'll transfer you to our staff now. Please hold."),
                    "content_complete": True,
                    "end_call": False,
                    "transfer_number": transfer_number
                }
                await websocket.send_json(response)
                return
            
            # For other functions, generate follow-up response
            messages.append({
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": func_name,
                    "arguments": json.dumps(func_args)
                }
            })
            messages.append({
                "role": "function",
                "name": func_name,
                "content": json.dumps(func_result)
            })
            
            # Generate response based on function result
            follow_up_response = await ai_orchestrator.generate_voice_response(
                messages=messages,
                functions=AVAILABLE_FUNCTIONS,
                tenant_id=call_state.get("tenant_id")
            )
            
            content = follow_up_response.get("content", "")
        else:
            content = llm_response.get("content", "")
        
        # Send response (streaming if content is long)
        if len(content) > 100:
            # Stream in chunks
            chunks = [content[i:i+50] for i in range(0, len(content), 50)]
            for i, chunk in enumerate(chunks):
                is_last = (i == len(chunks) - 1)
                response = {
                    "response_type": "response",
                    "response_id": response_id,
                    "content": chunk,
                    "content_complete": is_last,
                    "end_call": False
                }
                await websocket.send_json(response)
        else:
            # Send complete response
            response = {
                "response_type": "response",
                "response_id": response_id,
                "content": content,
                "content_complete": True,
                "end_call": False
            }
            await websocket.send_json(response)
            
    except Exception as e:
        logger.error(f"Error generating LLM response: {e}", exc_info=True)
        # Send error fallback response
        error_response = {
            "response_type": "response",
            "response_id": response_id,
            "content": "I apologize, I'm having a bit of trouble. Would you like me to transfer you to our staff?",
            "content_complete": True,
            "end_call": False
        }
        await websocket.send_json(error_response)


async def execute_function(
    func_name: str,
    func_args: Dict,
    call_state: Dict,
    retell_service: RetellService
) -> Dict[str, Any]:
    """
    Execute a function call from the LLM.
    
    Connects to backend services for real operations.
    """
    tenant_id = call_state.get("tenant_id")
    
    try:
        if func_name == "book_appointment":
            # Call backend to create appointment (via approval system)
            result = await retell_service.book_appointment(
                tenant_id=tenant_id,
                patient_name=func_args.get("patient_name"),
                patient_dob=func_args.get("patient_dob"),
                appointment_type=func_args.get("appointment_type"),
                preferred_date=func_args.get("preferred_date"),
                preferred_time=func_args.get("preferred_time"),
                notes=func_args.get("notes")
            )
            return result
            
        elif func_name == "check_availability":
            result = await retell_service.check_availability(
                tenant_id=tenant_id,
                date=func_args.get("date"),
                appointment_type=func_args.get("appointment_type")
            )
            return result
            
        elif func_name == "reschedule_appointment":
            result = await retell_service.reschedule_appointment(
                tenant_id=tenant_id,
                patient_name=func_args.get("patient_name"),
                patient_dob=func_args.get("patient_dob"),
                current_date=func_args.get("current_appointment_date"),
                new_date=func_args.get("new_preferred_date"),
                new_time=func_args.get("new_preferred_time")
            )
            return result
            
        elif func_name == "cancel_appointment":
            result = await retell_service.cancel_appointment(
                tenant_id=tenant_id,
                patient_name=func_args.get("patient_name"),
                patient_dob=func_args.get("patient_dob"),
                appointment_date=func_args.get("appointment_date"),
                reason=func_args.get("cancellation_reason")
            )
            return result
            
        elif func_name == "lookup_patient":
            result = await retell_service.lookup_patient(
                tenant_id=tenant_id,
                patient_name=func_args.get("patient_name"),
                patient_dob=func_args.get("patient_dob")
            )
            # Mark patient as verified in call state
            if result.get("found"):
                call_state["patient_verified"] = True
                call_state["patient_id"] = result.get("patient_id")
            return result
            
        elif func_name == "get_insurance_info":
            if not call_state.get("patient_verified"):
                return {"error": "Patient identity not verified. Please verify the patient first."}
            result = await retell_service.get_insurance_info(
                tenant_id=tenant_id,
                patient_name=func_args.get("patient_name"),
                patient_dob=func_args.get("patient_dob"),
                procedure_type=func_args.get("procedure_type")
            )
            return result
            
        elif func_name == "transfer_to_human":
            # Log transfer request
            call_state["transfer_requested"] = True
            call_state["transfer_reason"] = func_args.get("reason")
            return {"success": True, "message": "Transfer initiated"}
            
        elif func_name == "end_call":
            call_state["ended_by_agent"] = True
            return {"success": True, "message": "Call ended"}
            
        else:
            logger.warning(f"Unknown function called: {func_name}")
            return {"error": f"Unknown function: {func_name}"}
            
    except Exception as e:
        logger.error(f"Error executing function {func_name}: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# REST API Endpoints for Retell Configuration
# ============================================================================

class CreateAgentRequest(BaseModel):
    """Request to create a new Retell agent."""
    tenant_id: str
    agent_name: str
    voice_id: Optional[str] = None
    language: str = "en-US"
    transfer_number: Optional[str] = None


class AgentResponse(BaseModel):
    """Response with agent details."""
    agent_id: str
    agent_name: str
    llm_websocket_url: str
    voice_id: str
    language: str


@router.post("/agents", response_model=AgentResponse)
async def create_retell_agent(request: CreateAgentRequest):
    """
    Create a new Retell AI agent for a tenant.
    
    This creates an agent in Retell with our custom LLM WebSocket URL.
    """
    settings = get_settings()
    retell_service = RetellService(settings)
    
    try:
        agent = await retell_service.create_agent(
            tenant_id=request.tenant_id,
            agent_name=request.agent_name,
            voice_id=request.voice_id,
            language=request.language,
            transfer_number=request.transfer_number
        )
        return AgentResponse(**agent)
    except Exception as e:
        logger.error(f"Error creating Retell agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{tenant_id}")
async def get_tenant_agents(tenant_id: str):
    """Get all Retell agents for a tenant."""
    settings = get_settings()
    retell_service = RetellService(settings)
    
    try:
        agents = await retell_service.get_agents(tenant_id)
        return {"agents": agents}
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Webhook Endpoint for Retell Events
# ============================================================================

class RetellWebhookEvent(BaseModel):
    """Webhook event from Retell AI."""
    event: str  # "call_started", "call_ended", "call_analyzed"
    call: Dict


@router.post("/webhook")
async def retell_webhook(event: RetellWebhookEvent):
    """
    Handle webhook events from Retell AI.
    
    Events:
    - call_started: Call has begun
    - call_ended: Call has ended
    - call_analyzed: Post-call analysis complete
    """
    settings = get_settings()
    retell_service = RetellService(settings)
    
    try:
        if event.event == "call_started":
            logger.info(f"Call started: {event.call.get('call_id')}")
            # Could create a call record here
            
        elif event.event == "call_ended":
            logger.info(f"Call ended: {event.call.get('call_id')}")
            # Store call transcript and metadata
            await retell_service.store_call_record(event.call)
            
        elif event.event == "call_analyzed":
            logger.info(f"Call analyzed: {event.call.get('call_id')}")
            # Store analysis results, trigger follow-up workflows
            await retell_service.process_call_analysis(event.call)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
