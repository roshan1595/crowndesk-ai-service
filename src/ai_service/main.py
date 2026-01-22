"""
CrownDesk V2 - AI Service Main Entry Point
Per plan.txt Section 12-13: RAG Pipeline & Dental Coding
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_service.config import get_settings
from ai_service.routers import coding, health, intent, rag, retell, voice_agent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    settings = get_settings()
    print(f"Starting {settings.app_name}...")

    # Initialize database connection pool
    # await init_db()

    yield

    # Shutdown
    print("Shutting down AI service...")
    # await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-powered dental operations service for CrownDesk V2",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, tags=["health"])
    app.include_router(rag.router, prefix="/rag", tags=["rag"])
    app.include_router(coding.router, prefix="/coding", tags=["coding"])
    app.include_router(intent.router, prefix="/intent", tags=["intent"])
    app.include_router(retell.router, prefix="/retell", tags=["retell"])
    app.include_router(voice_agent.router, tags=["voice-agent"])

    return app


app = create_app()
