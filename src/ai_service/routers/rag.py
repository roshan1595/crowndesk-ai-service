"""
CrownDesk V2 - RAG Pipeline Router
Per plan.txt Section 13: RAG Pipeline

Endpoints:
- POST /rag/ingest - Process uploaded document
- POST /rag/query - Query knowledge base
- GET /rag/chunks/{document_id} - Get chunks for a document
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_service.services.rag_service import RAGService, get_rag_service

router = APIRouter()


class IngestRequest(BaseModel):
    """Request to ingest a document into the RAG pipeline."""

    tenant_id: str
    document_id: str
    s3_key: str
    patient_id: Optional[str] = None


class IngestResponse(BaseModel):
    """Response from document ingestion."""

    document_id: str
    chunk_count: int
    status: str


class QueryRequest(BaseModel):
    """Request to query the RAG knowledge base."""

    tenant_id: str
    query: str
    patient_id: Optional[str] = None
    top_k: int = 5


class QueryResponse(BaseModel):
    """Response from RAG query."""

    query: str
    answer: str
    sources: List[dict]
    confidence: float


class ChunkResponse(BaseModel):
    """Single chunk from a document."""

    id: str
    content: str
    chunk_index: int
    metadata: dict


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: IngestRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    """
    Ingest a document into the RAG pipeline.

    Per plan.txt Section 13:
    1. Download document from S3
    2. Extract text based on mime type
    3. Chunk text with overlap
    4. Generate embeddings
    5. Store in pgvector
    """
    try:
        result = await rag_service.ingest_document(
            tenant_id=request.tenant_id,
            document_id=request.document_id,
            s3_key=request.s3_key,
            patient_id=request.patient_id,
        )
        return IngestResponse(
            document_id=result["document_id"],
            chunk_count=result["chunk_count"],
            status="processed",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    """
    Query the RAG knowledge base.

    Per plan.txt Section 13:
    1. Embed the query
    2. Vector similarity search in pgvector
    3. Filter by tenant_id (and optionally patient_id)
    4. Generate answer with LLM using retrieved context
    """
    try:
        result = await rag_service.query(
            tenant_id=request.tenant_id,
            query=request.query,
            patient_id=request.patient_id,
            top_k=request.top_k,
        )
        return QueryResponse(
            query=request.query,
            answer=result["answer"],
            sources=result["sources"],
            confidence=result["confidence"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunks/{document_id}", response_model=List[ChunkResponse])
async def get_document_chunks(
    document_id: str,
    tenant_id: str,
    rag_service: RAGService = Depends(get_rag_service),
):
    """Get all chunks for a specific document."""
    try:
        chunks = await rag_service.get_chunks(
            tenant_id=tenant_id,
            document_id=document_id,
        )
        return [
            ChunkResponse(
                id=chunk["id"],
                content=chunk["content"],
                chunk_index=chunk["chunk_index"],
                metadata=chunk["metadata"],
            )
            for chunk in chunks
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
