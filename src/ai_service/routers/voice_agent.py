"""
Self-Hosted Voice Agent for Twilio Integration
Handles media streams from Twilio, processes audio with STT, LLM, and ElevenLabs TTS
"""

import asyncio
import base64
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
import httpx
import openai
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice-agent", tags=["voice-agent"])


class TwilioConfig(BaseModel):
    """Twilio configuration"""
    account_sid: str
    auth_token: str
    phone_number: str


class ConversationState:
    """Maintains state for an active voice conversation"""
    
    def __init__(self, call_sid: str, stream_sid: str):
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        self.audio_buffer = bytearray()
        self.conversation_history = []
        self.collected_data = {
            "firstName": None,
            "lastName": None,
            "dateOfBirth": None,
            "phone": None,
            "email": None,
            "reasonForVisit": None
        }
        self.current_field = "firstName"
        self.is_processing = False
        
    def add_to_buffer(self, audio_chunk: bytes):
        """Add audio chunk to buffer"""
        self.audio_buffer.extend(audio_chunk)
        
    def get_and_clear_buffer(self) -> bytes:
        """Get audio buffer and clear it"""
        audio = bytes(self.audio_buffer)
        self.audio_buffer.clear()
        return audio
        
    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({"role": role, "content": content})
        
    def is_complete(self) -> bool:
        """Check if all data is collected"""
        return all(self.collected_data.values())


# Store active conversations
active_conversations: Dict[str, ConversationState] = {}


class VoiceAgentService:
    """Service for handling voice agent logic"""
    
    def __init__(self):
        self.openai_client = openai.AsyncOpenAI()
        self.elevenlabs_api_key = None  # Will be set from env
        self.elevenlabs_voice_id = "EXAVITQu4vr4xnSDxMaL"  # Sarah voice
        
    async def transcribe_audio(self, audio_data: bytes, format: str = "mulaw") -> str:
        """Transcribe audio using OpenAI Whisper"""
        try:
            # Convert mulaw to wav if needed
            # For now, assume direct transcription
            logger.info(f"Transcribing audio: {len(audio_data)} bytes")
            
            # Create a temporary file-like object
            import io
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"
            
            # Use OpenAI Whisper
            transcript = await self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"
            )
            
            logger.info(f"Transcription: {transcript.text}")
            return transcript.text
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
            
    async def process_with_llm(
        self, 
        user_input: str, 
        state: ConversationState
    ) -> str:
        """Process user input with LLM to extract information and generate response"""
        
        # System prompt for dental receptionist
        system_prompt = """You are a friendly dental office receptionist helping a new patient register over the phone.

Your goal is to collect the following information:
1. First name
2. Last name  
3. Date of birth (format: MM/DD/YYYY)
4. Phone number
5. Email address
6. Reason for visit

Guidelines:
- Be warm and conversational
- Ask for one piece of information at a time
- Confirm what you heard before moving to the next field
- If you can't understand something, politely ask them to repeat
- After collecting all info, thank them and tell them they'll receive a text shortly

Current collected data: {collected_data}
Currently asking for: {current_field}
""".format(
            collected_data=json.dumps(state.collected_data, indent=2),
            current_field=state.current_field
        )
        
        # Add user input to history
        state.add_message("user", user_input)
        
        # Build messages for LLM
        messages = [
            {"role": "system", "content": system_prompt}
        ] + state.conversation_history
        
        try:
            # Call OpenAI
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                temperature=0.7,
                max_tokens=150
            )
            
            assistant_response = response.choices[0].message.content
            state.add_message("assistant", assistant_response)
            
            # Extract data from user input
            await self._extract_data(user_input, state)
            
            logger.info(f"LLM Response: {assistant_response}")
            logger.info(f"Collected data: {state.collected_data}")
            
            return assistant_response
            
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            return "I'm sorry, I didn't catch that. Could you please repeat?"
            
    async def _extract_data(self, user_input: str, state: ConversationState):
        """Extract structured data from user input"""
        
        # Use function calling to extract data
        extraction_prompt = f"""Extract the {state.current_field} from this user response: "{user_input}"
        
Return ONLY the extracted value, or null if not found.
Examples:
- If current_field is "firstName" and user says "My name is John Smith", return "John"
- If current_field is "dateOfBirth" and user says "March 15th 1985", return "03/15/1985"
- If current_field is "phone" and user says "555-1234", return "5551234"
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0
            )
            
            extracted_value = response.choices[0].message.content.strip()
            
            if extracted_value and extracted_value.lower() != "null":
                state.collected_data[state.current_field] = extracted_value
                
                # Move to next field
                fields = ["firstName", "lastName", "dateOfBirth", "phone", "email", "reasonForVisit"]
                current_idx = fields.index(state.current_field)
                if current_idx < len(fields) - 1:
                    state.current_field = fields[current_idx + 1]
                    
        except Exception as e:
            logger.error(f"Data extraction error: {e}")
            
    async def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech using ElevenLabs"""
        
        if not self.elevenlabs_api_key:
            logger.error("ElevenLabs API key not configured")
            return b""
            
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.elevenlabs_api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=headers, timeout=30.0)
                
                if response.status_code == 200:
                    logger.info(f"Generated {len(response.content)} bytes of audio")
                    return response.content
                else:
                    logger.error(f"ElevenLabs error: {response.status_code} - {response.text}")
                    return b""
                    
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return b""
            
    async def create_registration_and_send_sms(self, state: ConversationState):
        """Create registration token and send SMS via backend"""
        
        try:
            # Call backend to create registration
            backend_url = "http://localhost:4000/api/registration/voice-intake"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    backend_url,
                    json={
                        "firstName": state.collected_data["firstName"],
                        "lastName": state.collected_data["lastName"],
                        "dateOfBirth": state.collected_data["dateOfBirth"],
                        "phone": state.collected_data["phone"],
                        "email": state.collected_data["email"],
                        "reasonForVisit": state.collected_data["reasonForVisit"],
                        "callSid": state.call_sid
                    },
                    timeout=10.0
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Registration created: {response.json()}")
                else:
                    logger.error(f"Backend error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Registration creation error: {e}")


# Global service instance
voice_service = VoiceAgentService()


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams
    Receives audio from Twilio, processes it, and returns audio responses
    """
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None
    conversation: Optional[ConversationState] = None
    
    try:
        while True:
            # Receive message from Twilio
            message = await websocket.receive_text()
            data = json.loads(message)
            
            event_type = data.get("event")
            
            if event_type == "start":
                # Stream started
                call_sid = data["start"]["callSid"]
                stream_sid = data["start"]["streamSid"]
                
                conversation = ConversationState(call_sid, stream_sid)
                active_conversations[stream_sid] = conversation
                
                logger.info(f"Stream started: {stream_sid} for call {call_sid}")
                
                # Send initial greeting
                greeting = "Hi! Thank you for calling our dental office. I'm here to help you register as a new patient. May I have your first name, please?"
                
                # Generate audio
                audio_data = await voice_service.text_to_speech(greeting)
                
                if audio_data:
                    # Convert to mulaw and send to Twilio
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": audio_base64
                        }
                    })
                    
            elif event_type == "media":
                # Audio data received
                if conversation and not conversation.is_processing:
                    payload = data["media"]["payload"]
                    audio_chunk = base64.b64decode(payload)
                    
                    conversation.add_to_buffer(audio_chunk)
                    
                    # Process when buffer reaches threshold (e.g., 3 seconds)
                    if len(conversation.audio_buffer) > 48000:  # ~3 seconds at 16kHz
                        conversation.is_processing = True
                        
                        # Get audio from buffer
                        audio_to_process = conversation.get_and_clear_buffer()
                        
                        # Transcribe
                        transcript = await voice_service.transcribe_audio(audio_to_process)
                        
                        if transcript:
                            # Process with LLM
                            response_text = await voice_service.process_with_llm(
                                transcript, 
                                conversation
                            )
                            
                            # Convert to speech
                            audio_data = await voice_service.text_to_speech(response_text)
                            
                            if audio_data:
                                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                                
                                await websocket.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": audio_base64
                                    }
                                })
                                
                            # Check if registration is complete
                            if conversation.is_complete():
                                # Create registration and send SMS
                                await voice_service.create_registration_and_send_sms(conversation)
                                
                                # Send completion message
                                completion_text = "Perfect! I have all your information. You'll receive a text message shortly with a link to complete your registration. Thank you for calling!"
                                
                                audio_data = await voice_service.text_to_speech(completion_text)
                                
                                if audio_data:
                                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                                    
                                    await websocket.send_json({
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {
                                            "payload": audio_base64
                                        }
                                    })
                                    
                        conversation.is_processing = False
                        
            elif event_type == "stop":
                # Stream stopped
                logger.info(f"Stream stopped: {stream_sid}")
                
                if stream_sid in active_conversations:
                    del active_conversations[stream_sid]
                    
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
        
        if stream_sid and stream_sid in active_conversations:
            del active_conversations[stream_sid]
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        
        if stream_sid and stream_sid in active_conversations:
            del active_conversations[stream_sid]


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_conversations": len(active_conversations),
        "elevenlabs_configured": bool(voice_service.elevenlabs_api_key)
    }


@router.post("/configure")
async def configure_service(config: dict):
    """Configure service with API keys"""
    
    if "elevenlabs_api_key" in config:
        voice_service.elevenlabs_api_key = config["elevenlabs_api_key"]
        
    if "elevenlabs_voice_id" in config:
        voice_service.elevenlabs_voice_id = config["elevenlabs_voice_id"]
        
    return {"status": "configured"}
