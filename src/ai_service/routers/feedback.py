"""
CrownDesk V2 - AI Feedback & Retraining Router
Phase 4.2: RAG Enhancement with Feedback-Based Learning

Endpoints:
- POST /feedback/retrain - Process feedback batch for retraining
- POST /feedback/training-example - Create manual training example
- GET /feedback/stats - Get retraining statistics

This router receives feedback from the NestJS backend's retraining job
and uses it to improve the RAG embeddings.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai_service.services.rag_service import RAGService, get_rag_service
from ai_service.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class TrainingExample(BaseModel):
    """Single training example from feedback."""
    
    id: str
    agentType: str = Field(..., description="Type of AI agent: CDT_CODER, PA_GENERATOR, etc.")
    suggestionType: str = Field(..., description="Type of suggestion: code, narrative, appeal")
    originalSuggestion: Any = Field(..., description="What AI originally suggested")
    finalValue: Optional[Any] = Field(None, description="What user actually used (if modified)")
    outcomeAction: str = Field(..., description="approved, rejected, or modified")
    modificationReason: Optional[str] = Field(None, description="Why user modified the suggestion")
    externalSuccess: Optional[bool] = Field(None, description="External outcome (claim approved, etc.)")
    retrainingWeight: float = Field(1.0, description="Importance weight for retraining")
    retrievedContextIds: Optional[List[str]] = Field(None, description="Context chunk IDs that influenced suggestion")


class RetrainRequest(BaseModel):
    """Request to process feedback batch for retraining."""
    
    tenant_id: str
    agent_type: str
    training_examples: List[TrainingExample]


class RetrainResponse(BaseModel):
    """Response from retraining operation."""
    
    success: bool
    processed_count: int
    embedded_count: int
    skipped_count: int
    errors: List[str] = []
    processing_time_ms: int


class TrainingExampleRequest(BaseModel):
    """Request to create a manual training example."""
    
    tenant_id: str
    agent_type: str
    content: str
    metadata: Dict[str, Any] = {}
    weight: float = 1.0


class TrainingExampleResponse(BaseModel):
    """Response from creating training example."""
    
    id: str
    success: bool
    chunk_id: Optional[str] = None


class RetrainStatsResponse(BaseModel):
    """Statistics about retraining for a tenant."""
    
    tenant_id: str
    total_training_examples: int
    examples_by_agent: Dict[str, int]
    last_retrain_at: Optional[str] = None
    avg_confidence_improvement: Optional[float] = None


# =============================================================================
# Feedback Service (in-module for now, can be extracted later)
# =============================================================================

class FeedbackService:
    """Service for processing feedback and updating RAG embeddings."""
    
    def __init__(self, rag_service: RAGService):
        self.rag_service = rag_service
        self._pool = None
    
    async def _get_pool(self):
        """Get database connection pool from RAG service."""
        return await self.rag_service._get_pool()
    
    async def process_feedback_batch(
        self,
        tenant_id: str,
        agent_type: str,
        examples: List[TrainingExample],
    ) -> Dict[str, Any]:
        """
        Process a batch of feedback examples for retraining.
        
        Strategy:
        1. Filter for examples with positive outcomes or high weight
        2. Generate training content from feedback
        3. Create embeddings
        4. Store in RAG chunks with special metadata
        """
        import time
        start_time = time.time()
        
        errors = []
        embedded_count = 0
        skipped_count = 0
        
        for example in examples:
            try:
                # Determine if we should create a training embedding
                should_embed = self._should_create_embedding(example)
                
                if not should_embed:
                    skipped_count += 1
                    continue
                
                # Create training content from feedback
                training_content = self._create_training_content(agent_type, example)
                
                if not training_content:
                    skipped_count += 1
                    continue
                
                # Generate embedding and store
                await self._store_training_embedding(
                    tenant_id=tenant_id,
                    agent_type=agent_type,
                    example_id=example.id,
                    content=training_content,
                    weight=example.retrainingWeight,
                    metadata={
                        "source": "feedback",
                        "outcome_action": example.outcomeAction,
                        "suggestion_type": example.suggestionType,
                        "external_success": example.externalSuccess,
                    },
                )
                embedded_count += 1
                
            except Exception as e:
                logger.error(f"Failed to process feedback {example.id}: {str(e)}")
                errors.append(f"{example.id}: {str(e)}")
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return {
            "success": len(errors) == 0,
            "processed_count": len(examples),
            "embedded_count": embedded_count,
            "skipped_count": skipped_count,
            "errors": errors,
            "processing_time_ms": processing_time,
        }
    
    def _should_create_embedding(self, example: TrainingExample) -> bool:
        """
        Determine if feedback should result in a new training embedding.
        
        Create embeddings for:
        - Approved suggestions (confirmed good)
        - Modified suggestions with high weight (user corrections are valuable)
        - Examples with external success (real-world validation)
        """
        # Always embed approved suggestions
        if example.outcomeAction == "approved":
            return True
        
        # Modified suggestions are valuable - user showed us the right answer
        if example.outcomeAction == "modified" and example.finalValue:
            return True
        
        # External success is strong signal
        if example.externalSuccess is True:
            return True
        
        # High weight means important for learning
        if example.retrainingWeight >= 1.5:
            return True
        
        # Skip rejected without corrections - negative signal, harder to learn from
        if example.outcomeAction == "rejected" and not example.finalValue:
            return False
        
        return False
    
    def _create_training_content(
        self,
        agent_type: str,
        example: TrainingExample,
    ) -> Optional[str]:
        """
        Create training content from feedback example.
        
        The content varies based on agent type:
        - CDT_CODER: procedure description -> code mapping
        - PA_GENERATOR: procedure + payer -> narrative
        - APPEAL_GENERATOR: denial reason -> appeal text
        """
        try:
            # Use final value if modified, otherwise original suggestion
            value = example.finalValue if example.finalValue else example.originalSuggestion
            
            if not value:
                return None
            
            if agent_type == "CDT_CODER":
                # Format: clinical description + CDT code
                if isinstance(value, dict):
                    code = value.get("code", "")
                    description = value.get("description", "")
                    return f"Procedure: {description}\nCDT Code: {code}"
                return str(value)
            
            elif agent_type == "PA_GENERATOR":
                # Format: medical necessity narrative
                if isinstance(value, dict):
                    narrative = value.get("narrative", value.get("text", ""))
                    return f"Pre-Authorization Narrative:\n{narrative}"
                return f"Pre-Authorization Narrative:\n{value}"
            
            elif agent_type == "APPEAL_GENERATOR":
                # Format: appeal letter content
                if isinstance(value, dict):
                    letter = value.get("letter", value.get("content", ""))
                    return f"Appeal Letter:\n{letter}"
                return f"Appeal Letter:\n{value}"
            
            elif agent_type == "DENIAL_ANALYZER":
                # Format: denial analysis and resolution
                if isinstance(value, dict):
                    reason = value.get("reason", "")
                    resolution = value.get("resolution", "")
                    return f"Denial Reason: {reason}\nResolution: {resolution}"
                return str(value)
            
            elif agent_type == "CODE_VALIDATOR":
                # Format: code validation rule
                if isinstance(value, dict):
                    code = value.get("code", "")
                    rule = value.get("rule", value.get("validation", ""))
                    return f"Code: {code}\nValidation Rule: {rule}"
                return str(value)
            
            else:
                # Generic format for unknown agent types
                if isinstance(value, dict):
                    return str(value)
                return str(value)
                
        except Exception as e:
            logger.warning(f"Failed to create training content: {e}")
            return None
    
    async def _store_training_embedding(
        self,
        tenant_id: str,
        agent_type: str,
        example_id: str,
        content: str,
        weight: float,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Generate embedding and store as a training chunk.
        
        Training chunks are stored in the same rag_chunks table but with
        special metadata to distinguish them from document chunks.
        """
        # Generate embedding
        embeddings = await self.rag_service._embed_texts([content])
        embedding = embeddings[0]
        
        # Store in database
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Check if we already have this training example
            existing = await conn.fetchrow(
                """
                SELECT id FROM training_examples 
                WHERE tenant_id = $1 AND feedback_id = $2
                """,
                tenant_id,
                example_id,
            )
            
            if existing:
                # Update existing embedding
                chunk_id = await conn.fetchval(
                    """
                    UPDATE training_examples
                    SET content = $1, embedding = $2, weight = $3, 
                        metadata = $4, updated_at = NOW()
                    WHERE tenant_id = $5 AND feedback_id = $6
                    RETURNING id
                    """,
                    content,
                    embedding,
                    weight,
                    {**metadata, "agent_type": agent_type, "tenant_id": tenant_id},
                    tenant_id,
                    example_id,
                )
            else:
                # Insert new training example
                chunk_id = await conn.fetchval(
                    """
                    INSERT INTO training_examples 
                    (tenant_id, feedback_id, agent_type, content, embedding, weight, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    tenant_id,
                    example_id,
                    agent_type,
                    content,
                    embedding,
                    weight,
                    {**metadata, "agent_type": agent_type, "tenant_id": tenant_id},
                )
        
        return str(chunk_id)
    
    async def get_training_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get retraining statistics for a tenant."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Total count
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM training_examples WHERE tenant_id = $1",
                tenant_id,
            )
            
            # Count by agent type
            rows = await conn.fetch(
                """
                SELECT agent_type, COUNT(*) as count 
                FROM training_examples 
                WHERE tenant_id = $1 
                GROUP BY agent_type
                """,
                tenant_id,
            )
            by_agent = {row["agent_type"]: row["count"] for row in rows}
            
            # Last retrain timestamp (most recent example)
            last_at = await conn.fetchval(
                "SELECT MAX(updated_at) FROM training_examples WHERE tenant_id = $1",
                tenant_id,
            )
        
        return {
            "tenant_id": tenant_id,
            "total_training_examples": total or 0,
            "examples_by_agent": by_agent,
            "last_retrain_at": last_at.isoformat() if last_at else None,
            "avg_confidence_improvement": None,  # Would require tracking over time
        }


def get_feedback_service(
    rag_service: RAGService = Depends(get_rag_service),
) -> FeedbackService:
    """Dependency injection for feedback service."""
    return FeedbackService(rag_service)


# =============================================================================
# Router Endpoints
# =============================================================================

@router.post("/retrain", response_model=RetrainResponse)
async def process_retrain_batch(
    request: RetrainRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Process a batch of feedback examples for RAG retraining.
    
    Called by the NestJS backend's scheduled retraining job.
    
    Steps:
    1. Filter examples based on outcome quality
    2. Generate training content from feedback
    3. Create embeddings
    4. Store in training_examples table
    
    The stored embeddings will be used in future similarity searches
    to improve AI suggestions based on organization-specific patterns.
    """
    try:
        result = await feedback_service.process_feedback_batch(
            tenant_id=request.tenant_id,
            agent_type=request.agent_type,
            examples=request.training_examples,
        )
        return RetrainResponse(**result)
    except Exception as e:
        logger.error(f"Retraining failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training-example", response_model=TrainingExampleResponse)
async def create_training_example(
    request: TrainingExampleRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Create a manual training example.
    
    Used for:
    - Adding organization-specific knowledge
    - Correcting AI behavior
    - Seeding initial training data
    """
    try:
        import uuid
        example_id = str(uuid.uuid4())
        
        chunk_id = await feedback_service._store_training_embedding(
            tenant_id=request.tenant_id,
            agent_type=request.agent_type,
            example_id=example_id,
            content=request.content,
            weight=request.weight,
            metadata=request.metadata,
        )
        
        return TrainingExampleResponse(
            id=example_id,
            success=True,
            chunk_id=chunk_id,
        )
    except Exception as e:
        logger.error(f"Failed to create training example: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{tenant_id}", response_model=RetrainStatsResponse)
async def get_retraining_stats(
    tenant_id: str,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Get retraining statistics for a tenant.
    
    Returns:
    - Total training examples
    - Examples by agent type
    - Last retraining timestamp
    """
    try:
        stats = await feedback_service.get_training_stats(tenant_id)
        return RetrainStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
