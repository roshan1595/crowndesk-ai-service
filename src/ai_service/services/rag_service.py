"""
CrownDesk V2 - RAG Service
Per plan.txt Section 13: RAG Pipeline

Handles:
- Document ingestion and chunking
- Embedding generation with OpenAI
- Vector storage in pgvector
- Semantic search and retrieval
- Answer generation with LLM
"""

import asyncio
import io
import logging
import time
from typing import Any, Dict, List, Optional

import asyncpg
import boto3
from openai import AsyncOpenAI
from pgvector.asyncpg import register_vector
from pypdf import PdfReader
from docx import Document as DocxDocument
from unstructured.partition.auto import partition

from ai_service.config import get_settings

logger = logging.getLogger(__name__)


class RAGService:
    """RAG pipeline service for document Q&A."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._pool: Optional[asyncpg.Pool] = None
        self._openai_client: Optional[AsyncOpenAI] = None
        self._s3_client = boto3.client(
            "s3",
            region_name=self.settings.aws_region,
        )

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            async def _init(conn: asyncpg.Connection) -> None:
                await register_vector(conn)

            self._pool = await asyncpg.create_pool(
                dsn=self.settings.database_url,
                min_size=1,
                max_size=5,
                init=_init,
            )
        return self._pool

    @property
    def openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            if not self.settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            self._openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._openai_client

    async def _fetch_document_metadata(self, tenant_id: str, document_id: str) -> Dict[str, Any]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, tenant_id, patient_id, mime_type, file_name, storage_key
                FROM documents
                WHERE id = $1 AND tenant_id = $2
                """,
                document_id,
                tenant_id,
            )
        if row is None:
            raise ValueError("Document not found for tenant")
        return dict(row)

    async def _download_from_s3(self, storage_key: str) -> Dict[str, Any]:
        def _download() -> Dict[str, Any]:
            response = self._s3_client.get_object(
                Bucket=self.settings.aws_s3_bucket,
                Key=storage_key,
            )
            return {
                "content": response["Body"].read(),
                "content_type": response.get("ContentType"),
            }

        return await asyncio.to_thread(_download)

    def _extract_text(self, data: bytes, mime_type: Optional[str], file_name: str) -> str:
        mime_type = (mime_type or "").lower()

        if mime_type == "application/pdf" or file_name.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()

        if mime_type in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        } or file_name.lower().endswith((".docx", ".doc")):
            doc = DocxDocument(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs).strip()

        if mime_type.startswith("text/"):
            return data.decode("utf-8", errors="ignore").strip()

        elements = partition(
            file=io.BytesIO(data),
            content_type=mime_type or None,
            file_name=file_name,
        )
        text = "\n".join([el.text for el in elements if el.text])
        return text.strip()

    def _chunk_text(self, text: str) -> List[str]:
        chunk_size = self.settings.rag_chunk_size
        overlap = self.settings.rag_chunk_overlap

        if overlap >= chunk_size:
            raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")

        chunks: List[str] = []
        start = 0
        length = len(text)

        while start < length:
            end = min(start + chunk_size, length)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == length:
                break
            start = end - overlap

        return chunks

    async def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        batch_size = 50

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.openai_client.embeddings.create(
                model=self.settings.openai_embedding_model,
                input=batch,
            )
            embeddings.extend([item.embedding for item in response.data])

        return embeddings

    async def ingest_document(
        self,
        tenant_id: str,
        document_id: str,
        s3_key: str,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingest a document into the RAG pipeline.

        Steps:
        1. Download from S3
        2. Extract text based on mime type
        3. Split into chunks
        4. Generate embeddings
        5. Store in pgvector
        """
        metadata = await self._fetch_document_metadata(tenant_id, document_id)

        if metadata["storage_key"] != s3_key:
            raise ValueError("S3 key mismatch for document")

        s3_result = await self._download_from_s3(s3_key)
        raw_text = self._extract_text(
            s3_result["content"],
            s3_result.get("content_type") or metadata["mime_type"],
            metadata["file_name"],
        )

        if not raw_text:
            raise ValueError("No extractable text found in document")

        chunks = self._chunk_text(raw_text)
        embeddings = await self._embed_texts(chunks)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM rag_chunks WHERE document_id = $1",
                    document_id,
                )

                rows = []
                for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
                    rows.append(
                        (
                            document_id,
                            index,
                            content,
                            embedding,
                            {
                                "tenant_id": tenant_id,
                                "patient_id": patient_id or metadata.get("patient_id"),
                                "file_name": metadata["file_name"],
                                "mime_type": metadata["mime_type"],
                            },
                        )
                    )

                await conn.executemany(
                    """
                    INSERT INTO rag_chunks (document_id, chunk_index, content, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    rows,
                )

        return {
            "document_id": document_id,
            "chunk_count": len(chunks),
            "status": "processed",
        }

    async def query(
        self,
        tenant_id: str,
        query: str,
        patient_id: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Query the knowledge base using semantic search.

        Steps:
        1. Embed the query
        2. Vector similarity search with tenant filter
        3. Build context from retrieved chunks
        4. Generate answer with LLM
        """
        start_time = time.time()

        query_embedding = await self._embed_texts([query])
        embedding = query_embedding[0]

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    rc.id,
                    rc.document_id,
                    rc.chunk_index,
                    rc.content,
                    rc.metadata,
                    d.patient_id,
                    d.file_name,
                    d.type,
                    (rc.embedding <-> $3) AS distance
                FROM rag_chunks rc
                JOIN documents d ON d.id = rc.document_id
                WHERE d.tenant_id = $1
                  AND ($2::uuid IS NULL OR d.patient_id = $2::uuid)
                ORDER BY rc.embedding <-> $3
                LIMIT $4
                """,
                tenant_id,
                patient_id,
                embedding,
                top_k,
            )

        sources = []
        context_parts = []
        for row in rows:
            distance = float(row["distance"]) if row["distance"] is not None else 0.0
            relevance = 1 / (1 + distance)
            sources.append(
                {
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                    "relevance_score": round(relevance, 4),
                    "file_name": row["file_name"],
                    "document_type": row["type"],
                }
            )
            context_parts.append(row["content"])

        context = "\n\n".join(context_parts)

        if not context:
            answer = "No relevant document content found for this query."
            confidence = 0.0
        else:
            response = await self.openai_client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0.2,
                max_tokens=600,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a clinical assistant for a dental practice. "
                            "Answer the question using only the provided context. "
                            "If the context is insufficient, say so."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Context:\n{context}\n\nQuestion: {query}",
                    },
                ],
            )
            answer = response.choices[0].message.content or ""
            confidence = min(0.95, max(0.2, len(sources) / max(top_k, 1)))

        processing_time = int((time.time() - start_time) * 1000)

        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "processing_time_ms": processing_time,
        }

    async def get_chunks(
        self,
        tenant_id: str,
        document_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT rc.id, rc.content, rc.chunk_index, rc.metadata
                FROM rag_chunks rc
                JOIN documents d ON d.id = rc.document_id
                WHERE rc.document_id = $1 AND d.tenant_id = $2
                ORDER BY rc.chunk_index ASC
                """,
                document_id,
                tenant_id,
            )
        return [
            {
                "id": row["id"],
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "metadata": row["metadata"],
            }
            for row in rows
        ]

    async def delete_document(
        self,
        tenant_id: str,
        document_id: str,
    ) -> bool:
        """Delete a document and its chunks from the knowledge base."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM rag_chunks
                WHERE document_id = $1
                  AND EXISTS (
                    SELECT 1 FROM documents d
                    WHERE d.id = $1 AND d.tenant_id = $2
                  )
                """,
                document_id,
                tenant_id,
            )
        return result.startswith("DELETE")


def get_rag_service() -> RAGService:
    """Dependency injection for RAG service."""
    return RAGService()
