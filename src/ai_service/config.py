"""
CrownDesk V2 - AI Service Configuration
Per plan.txt Section 12-13
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "CrownDesk AI Service"
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/crowndesk"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo-preview"
    openai_embedding_model: str = "text-embedding-3-small"  # 1536 dimensions

    # Anthropic
    anthropic_api_key: str = ""

    # Pinecone (new SDK format)
    pinecone_api_key: str = ""
    pinecone_host: str = ""
    pinecone_index_name: str = "crowndesk"

    # AWS
    aws_region: str = "us-east-2"
    aws_s3_bucket: str = "crowndesk-storage"
    aws_s3_bucket_audio: str = "crowndesk-audio"

    # Clerk Auth
    clerk_secret_key: str = ""
    clerk_jwks_url: str = "https://api.clerk.dev/v1/jwks"

    # RAG Settings
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 5

    # Coding Assistant Settings
    coding_confidence_threshold: float = 0.8
    coding_max_suggestions: int = 5

    # Retell AI Settings (Voice AI Receptionist)
    retell_api_key: str = ""  # Also accepts RETELLAI_API_KEY
    retell_webhook_secret: str = ""
    retell_llm_websocket_url: str = ""  # Set to your deployed URL, e.g., wss://your-domain.com/ws/retell
    
    # Backend API (NestJS)
    backend_url: str = "http://localhost:3001"
    backend_api_key: str = ""  # Internal API key for service-to-service auth
    
    # Practice Settings
    practice_name: str = "Your Dental Practice"
    practice_phone: str = ""
    practice_transfer_number: str = ""  # Number to transfer calls to for human handoff
    
    # AI Safety Settings
    ai_confidence_threshold: float = 0.7  # Below this, transfer to human
    max_guardrail_triggers: int = 3  # Max guardrail hits before transfer
    
    # LLM Provider
    llm_provider: str = "openai"  # openai or anthropic

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    @field_validator('retell_api_key', mode='before')
    @classmethod
    def get_retell_api_key(cls, v: str) -> str:
        """Accept either RETELL_API_KEY or RETELLAI_API_KEY from environment."""
        if v:
            return v
        # Check alternative env var name
        return os.environ.get('RETELLAI_API_KEY', '')


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
