"""
POST /search  → RAG search with watsonx.ai
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import opensearch_store as os_store
import watsonx_client as wx
import config as cfg

logger = logging.getLogger(__name__)
router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    tags: Optional[List[str]] = None
    top_k: int = cfg.RAG_TOP_K
    generate_answer: bool = True


@router.post("/search")
async def search(req: SearchRequest):
    """
    Semantic search + optional RAG answer generation.

    1. Embed the query with watsonx.ai
    2. kNN search in OpenSearch chunks
    3. Optionally generate an answer with watsonx.ai LLM
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query is empty")

    # 1. Embed query
    try:
        query_embedding = await wx.embed_single(req.query)
    except Exception as exc:
        logger.exception("Embedding failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Embedding error: {exc}")

    # 2. Vector search
    try:
        chunks = await os_store.store.vector_search(
            query_embedding=query_embedding,
            tags=req.tags if req.tags else None,
            top_k=req.top_k,
        )
    except Exception as exc:
        logger.exception("Vector search failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Search error: {exc}")

    # 3. Generate answer (optional)
    answer = None
    if req.generate_answer and chunks:
        try:
            answer = await wx.rag_answer(req.query, chunks)
        except Exception as exc:
            logger.warning("Answer generation failed: %s", exc)
            answer = None

    return {
        "query": req.query,
        "answer": answer,
        "chunks": [
            {
                "chunk_id": c.get("chunk_id"),
                "document_id": c.get("document_id"),
                "file_name": c.get("file_name"),
                "tags": c.get("tags", []),
                "chunk_index": c.get("chunk_index"),
                "text": c.get("text", ""),
                "score": c.get("_score"),
            }
            for c in chunks
        ],
    }
