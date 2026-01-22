"""
Vercel FastAPI Entrypoint
"""

from src.ai_service.main import app

# Export for Vercel
__all__ = ["app"]
