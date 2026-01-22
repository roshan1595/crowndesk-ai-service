"""
CrownDesk V2 - AI Orchestrator Service
Per plan.txt Section 12: AI Architecture

Unified AI orchestrator for:
- Multi-model routing (OpenAI, Anthropic)
- Tool/Function calling
- Context management
- Response generation with streaming
"""

import json
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from ai_service.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """
    Unified AI Orchestrator for CrownDesk.
    
    Similar to NeuraNote's UnifiedAIOrchestrator pattern:
    - Routes to appropriate LLM (OpenAI, Anthropic)
    - Handles function/tool calling
    - Manages conversation context
    - Applies guardrails and safety checks
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        
        # Initialize LLM clients
        self._openai_client = None
        self._anthropic_client = None
        
        # Default models
        self.default_model = "gpt-4-turbo-preview"
        self.fast_model = "gpt-4o-mini"
        self.voice_model = "gpt-4o-mini"  # Low latency for voice
        
        # Context settings
        self.max_context_tokens = 8000
        self.max_response_tokens = 1000
    
    @property
    def openai_client(self) -> AsyncOpenAI:
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            if not self.settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            self._openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._openai_client
    
    @property
    def anthropic_client(self) -> AsyncAnthropic:
        """Lazy initialization of Anthropic client."""
        if self._anthropic_client is None:
            if not self.settings.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            self._anthropic_client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        return self._anthropic_client
    
    # =========================================================================
    # Voice Response Generation (for Retell AI)
    # =========================================================================
    
    async def generate_voice_response(
        self,
        messages: List[Dict[str, Any]],
        functions: Optional[List[Dict]] = None,
        tenant_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a response for voice interactions.
        
        Optimized for:
        - Low latency (uses fast model)
        - Conversational style
        - Function calling support
        
        Returns:
            Dict with 'content' and optionally 'function_call'
        """
        model = model or self.voice_model
        
        try:
            # Build request
            request_params = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 200,  # Keep responses short for voice
                "frequency_penalty": 0.3,
            }
            
            # Add function calling if provided
            if functions:
                request_params["tools"] = functions
                request_params["tool_choice"] = "auto"
            
            # Call OpenAI
            response = await self.openai_client.chat.completions.create(**request_params)
            
            # Extract response
            message = response.choices[0].message
            
            result = {
                "content": message.content or "",
                "model": model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens
                }
            }
            
            # Check for function call
            if message.tool_calls and len(message.tool_calls) > 0:
                tool_call = message.tool_calls[0]
                result["function_call"] = {
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating voice response: {e}", exc_info=True)
            # Return fallback response
            return {
                "content": "I apologize, I'm having a moment of difficulty. Could you please repeat that?",
                "error": str(e)
            }
    
    # =========================================================================
    # Streaming Response Generation (for Chat UI)
    # =========================================================================
    
    async def generate_streaming_response(
        self,
        messages: List[Dict[str, Any]],
        functions: Optional[List[Dict]] = None,
        tenant_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response for chat UI.
        
        Yields content chunks as they're generated.
        """
        model = model or self.default_model
        
        try:
            request_params = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": self.max_response_tokens,
                "stream": True
            }
            
            if functions:
                request_params["tools"] = functions
                request_params["tool_choice"] = "auto"
            
            stream = await self.openai_client.chat.completions.create(**request_params)
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield f"I apologize, I encountered an error: {str(e)}"
    
    # =========================================================================
    # Intent Classification
    # =========================================================================
    
    async def classify_intent(
        self,
        message: str,
        intents: List[Dict[str, Any]],
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Classify the intent of a message.
        
        Args:
            message: The user message to classify
            intents: List of possible intents with descriptions
            context: Optional conversation context
            
        Returns:
            Dict with 'intent', 'confidence', and 'entities'
        """
        intent_descriptions = "\n".join([
            f"- {i['name']}: {i['description']}"
            for i in intents
        ])
        
        system_prompt = f"""You are an intent classifier for a dental practice. 
Classify the user's message into one of these intents:

{intent_descriptions}

Respond with JSON containing:
- intent: the classified intent name
- confidence: confidence score 0-1
- entities: extracted entities (dates, names, procedures, etc.)
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.fast_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "entities": {},
                "error": str(e)
            }
    
    # =========================================================================
    # Summary Generation
    # =========================================================================
    
    async def generate_summary(
        self,
        content: str,
        summary_type: str = "general",
        max_length: int = 200
    ) -> Dict[str, Any]:
        """
        Generate a summary of content.
        
        Args:
            content: Text to summarize
            summary_type: Type of summary (general, clinical, billing)
            max_length: Maximum length of summary
        """
        prompts = {
            "general": "Summarize the following content concisely:",
            "clinical": "Provide a clinical summary of the following notes, focusing on key findings and recommendations:",
            "billing": "Summarize the billing-relevant information from the following:"
        }
        
        prompt = prompts.get(summary_type, prompts["general"])
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.fast_model,
                messages=[
                    {"role": "system", "content": f"{prompt} Keep the summary under {max_length} words."},
                    {"role": "user", "content": content}
                ],
                temperature=0.3,
                max_tokens=max_length * 2  # Rough token estimate
            )
            
            return {
                "summary": response.choices[0].message.content,
                "summary_type": summary_type,
                "original_length": len(content),
                "summary_length": len(response.choices[0].message.content)
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {
                "summary": "",
                "error": str(e)
            }
    
    # =========================================================================
    # Chat Completion (for dashboard AI assistant)
    # =========================================================================
    
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        General chat completion for the AI assistant.
        
        Supports:
        - Custom system prompts
        - Tool/function calling
        - Streaming responses
        """
        # Build messages with system prompt
        full_messages = []
        
        if system_prompt:
            full_messages.append({
                "role": "system",
                "content": system_prompt
            })
        else:
            full_messages.append({
                "role": "system",
                "content": self._get_default_system_prompt()
            })
        
        full_messages.extend(messages)
        
        try:
            request_params = {
                "model": self.default_model,
                "messages": full_messages,
                "temperature": 0.7,
                "max_tokens": self.max_response_tokens
            }
            
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"
            
            if stream:
                request_params["stream"] = True
                return {"stream": self._stream_chat(request_params)}
            
            response = await self.openai_client.chat.completions.create(**request_params)
            
            message = response.choices[0].message
            
            result = {
                "content": message.content,
                "role": "assistant",
                "model": self.default_model
            }
            
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            return result
            
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            return {
                "content": f"I apologize, I encountered an error: {str(e)}",
                "role": "assistant",
                "error": str(e)
            }
    
    async def _stream_chat(self, request_params: Dict) -> AsyncGenerator[Dict, None]:
        """Internal streaming chat generator."""
        try:
            stream = await self.openai_client.chat.completions.create(**request_params)
            
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield {"type": "content", "content": delta.content}
                    if delta.tool_calls:
                        yield {"type": "tool_call", "tool_calls": delta.tool_calls}
                        
        except Exception as e:
            yield {"type": "error", "error": str(e)}
    
    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for the AI assistant."""
        return """You are CrownDesk AI Assistant, a helpful assistant for dental practice staff.

You can help with:
- Looking up patient information
- Checking appointment schedules
- Answering questions about procedures and billing
- Providing insights about practice performance
- Explaining insurance and coverage questions

Guidelines:
- Be helpful and professional
- Provide accurate information based on the data available
- If you're unsure, say so and suggest contacting appropriate staff
- Respect patient privacy - only discuss information when appropriate
- Be concise but thorough in your responses

You have access to the practice's patient records, appointments, and billing information through function calls.
"""
    
    # =========================================================================
    # Embeddings Generation (for RAG)
    # =========================================================================
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> List[List[float]]:
        """Generate embeddings for texts using OpenAI."""
        model = model or self.settings.openai_embedding_model
        
        try:
            response = await self.openai_client.embeddings.create(
                model=model,
                input=texts
            )
            
            return [item.embedding for item in response.data]
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of AI services."""
        result = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {}
        }
        
        # Check OpenAI
        try:
            if self.settings.openai_api_key:
                # Simple test call
                await self.openai_client.models.list()
                result["services"]["openai"] = "connected"
            else:
                result["services"]["openai"] = "not_configured"
        except Exception as e:
            result["services"]["openai"] = f"error: {str(e)}"
            result["status"] = "degraded"
        
        # Check Anthropic
        try:
            if self.settings.anthropic_api_key:
                result["services"]["anthropic"] = "configured"
            else:
                result["services"]["anthropic"] = "not_configured"
        except Exception as e:
            result["services"]["anthropic"] = f"error: {str(e)}"
        
        return result
