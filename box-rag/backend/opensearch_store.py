"""
OpenSearch store for Box RAG service.

Manages two indexes:
- box_documents: Document metadata (file info, tags, status)
- box_chunks:    Text chunks with vector embeddings

Deduplication key: box_file_id + modified_at
Update strategy: delete old chunks → ingest new chunks
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from opensearchpy import AsyncOpenSearch
from opensearchpy.exceptions import NotFoundError

import config as cfg

logger = logging.getLogger(__name__)


def _make_client() -> AsyncOpenSearch:
    """Create and return an AsyncOpenSearch client."""
    return AsyncOpenSearch(
        hosts=[{"host": cfg.OPENSEARCH_HOST, "port": cfg.OPENSEARCH_PORT}],
        http_auth=(cfg.OPENSEARCH_USERNAME, cfg.OPENSEARCH_PASSWORD),
        use_ssl=cfg.OPENSEARCH_USE_SSL,
        verify_certs=cfg.OPENSEARCH_VERIFY_CERTS,
        ssl_show_warn=False,
    )


# ── Index mapping definitions ──────────────────────────────────────────────

def _documents_index_body() -> dict:
    return {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "document_id":      {"type": "keyword"},
                "box_file_id":      {"type": "keyword"},
                "file_name":        {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "tags":             {"type": "keyword"},
                "shared_link_url":  {"type": "keyword"},
                "shared_link_hash": {"type": "keyword"},
                "modified_at":      {"type": "keyword"},
                "ingested_at":      {"type": "date"},
                "updated_at":       {"type": "date"},
                "status":           {"type": "keyword"},  # pending | indexed | failed
                "file_size":        {"type": "long"},
                "mime_type":        {"type": "keyword"},
                "chunk_count":      {"type": "integer"},
                "error":            {"type": "text"},
            }
        },
    }


def _chunks_index_body(embed_dim: int) -> dict:
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "index.knn": True,
        },
        "mappings": {
            "properties": {
                "chunk_id":     {"type": "keyword"},
                "document_id":  {"type": "keyword"},
                "box_file_id":  {"type": "keyword"},
                "file_name":    {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "tags":         {"type": "keyword"},
                "modified_at":  {"type": "keyword"},
                "chunk_index":  {"type": "integer"},
                "text":         {"type": "text"},
                "page":         {"type": "integer"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": embed_dim,
                    "method": {
                        "name": "hnsw",
                        "space_type": "l2",
                        "engine": "nmslib",
                        "parameters": {"ef_construction": 100, "m": 16},
                    },
                },
            }
        },
    }


# ── OpenSearchStore ────────────────────────────────────────────────────────

class OpenSearchStore:
    """Async OpenSearch store for Box documents and chunks."""

    def __init__(self):
        self._client: Optional[AsyncOpenSearch] = None

    @property
    def client(self) -> AsyncOpenSearch:
        if self._client is None:
            self._client = _make_client()
        return self._client

    async def ensure_indexes(self):
        """Create indexes if they don't exist."""
        cl = self.client
        for idx_name, idx_body in [
            (cfg.BOX_DOCUMENTS_INDEX, _documents_index_body()),
            (cfg.BOX_CHUNKS_INDEX, _chunks_index_body(cfg.EMBED_DIM)),
        ]:
            exists = await cl.indices.exists(index=idx_name)
            if not exists:
                await cl.indices.create(index=idx_name, body=idx_body)
                logger.info("Created OpenSearch index: %s", idx_name)

    # ── Documents ──────────────────────────────────────────────────────────

    async def get_document_by_box_id(self, box_file_id: str) -> Optional[dict]:
        """Fetch document metadata by Box file ID."""
        cl = self.client
        result = await cl.search(
            index=cfg.BOX_DOCUMENTS_INDEX,
            body={"query": {"term": {"box_file_id": box_file_id}}, "size": 1},
        )
        hits = result["hits"]["hits"]
        return hits[0]["_source"] if hits else None

    async def upsert_document(
        self,
        box_file_id: str,
        file_name: str,
        tags: List[str],
        shared_link_url: str,
        modified_at: str,
        mime_type: str,
        file_size: int,
        status: str = "pending",
    ) -> str:
        """
        Insert or update a document record.
        Returns document_id (stable, created once).
        """
        cl = self.client
        existing = await self.get_document_by_box_id(box_file_id)
        now = datetime.now(timezone.utc).isoformat()

        import hashlib
        link_hash = hashlib.sha256(shared_link_url.encode()).hexdigest()[:16]

        if existing:
            document_id = existing["document_id"]
            # Update fields
            await cl.update(
                index=cfg.BOX_DOCUMENTS_INDEX,
                id=document_id,
                body={
                    "doc": {
                        "file_name": file_name,
                        "tags": tags,
                        "shared_link_url": shared_link_url,
                        "shared_link_hash": link_hash,
                        "modified_at": modified_at,
                        "updated_at": now,
                        "status": status,
                        "file_size": file_size,
                        "mime_type": mime_type,
                        "error": None,
                    }
                },
                refresh=True,
            )
        else:
            document_id = str(uuid.uuid4())
            doc = {
                "document_id": document_id,
                "box_file_id": box_file_id,
                "file_name": file_name,
                "tags": tags,
                "shared_link_url": shared_link_url,
                "shared_link_hash": link_hash,
                "modified_at": modified_at,
                "ingested_at": now,
                "updated_at": now,
                "status": status,
                "file_size": file_size,
                "mime_type": mime_type,
                "chunk_count": 0,
                "error": None,
            }
            await cl.index(
                index=cfg.BOX_DOCUMENTS_INDEX,
                id=document_id,
                body=doc,
                refresh=True,
            )

        return document_id

    async def update_document_status(
        self,
        document_id: str,
        status: str,
        chunk_count: int = None,
        error: str = None,
    ):
        """Update document status fields."""
        now = datetime.now(timezone.utc).isoformat()
        update_body: dict = {"status": status, "updated_at": now}
        if chunk_count is not None:
            update_body["chunk_count"] = chunk_count
        if error is not None:
            update_body["error"] = error

        await self.client.update(
            index=cfg.BOX_DOCUMENTS_INDEX,
            id=document_id,
            body={"doc": update_body},
            refresh=True,
        )

    async def needs_reingestion(self, box_file_id: str, modified_at: str) -> bool:
        """
        Return True if file needs (re)ingestion.
        False if already indexed with same modified_at.
        """
        existing = await self.get_document_by_box_id(box_file_id)
        if not existing:
            return True
        if existing.get("status") != "indexed":
            return True
        return existing.get("modified_at") != modified_at

    async def list_documents(
        self,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        size: int = 100,
        from_: int = 0,
    ) -> dict:
        """List documents with optional filters."""
        filters = []
        if tags:
            filters.append({"terms": {"tags": tags}})
        if status:
            filters.append({"term": {"status": status}})

        query = {"bool": {"filter": filters}} if filters else {"match_all": {}}
        result = await self.client.search(
            index=cfg.BOX_DOCUMENTS_INDEX,
            body={
                "query": query,
                "sort": [{"updated_at": {"order": "desc"}}],
                "size": size,
                "from": from_,
            },
        )
        total = result["hits"]["total"]["value"]
        docs = [h["_source"] for h in result["hits"]["hits"]]
        return {"total": total, "documents": docs}

    async def delete_document(self, document_id: str):
        """Delete document and all its chunks."""
        await self.delete_chunks_for_document(document_id)
        try:
            await self.client.delete(
                index=cfg.BOX_DOCUMENTS_INDEX, id=document_id, refresh=True
            )
        except NotFoundError:
            pass

    # ── Chunks ─────────────────────────────────────────────────────────────

    async def delete_chunks_for_document(self, document_id: str):
        """Delete all chunks belonging to a document."""
        await self.client.delete_by_query(
            index=cfg.BOX_CHUNKS_INDEX,
            body={"query": {"term": {"document_id": document_id}}},
            refresh=True,
        )
        logger.debug("Deleted chunks for document_id=%s", document_id)

    async def index_chunks(self, chunks: List[dict]):
        """
        Bulk-index a list of chunk dicts.
        Each chunk must have: chunk_id, document_id, box_file_id, file_name,
        tags, modified_at, chunk_index, text, embedding, page (optional).
        """
        if not chunks:
            return

        body = []
        for chunk in chunks:
            body.append({"index": {"_index": cfg.BOX_CHUNKS_INDEX, "_id": chunk["chunk_id"]}})
            body.append(chunk)

        response = await self.client.bulk(body=body, refresh=True)
        if response.get("errors"):
            # Log but don't raise — partial success is acceptable
            failed = [
                item["index"]["error"]
                for item in response["items"]
                if "error" in item.get("index", {})
            ]
            logger.warning("Bulk indexing had errors: %s", failed[:3])

    # ── Vector Search ──────────────────────────────────────────────────────

    async def vector_search(
        self,
        query_embedding: List[float],
        tags: Optional[List[str]] = None,
        top_k: int = None,
    ) -> List[dict]:
        """
        kNN vector search in chunks index.
        Optional tag filter narrows results.
        Returns list of chunk source dicts with _score.
        """
        k = top_k or cfg.RAG_TOP_K

        knn_query: dict = {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": k,
                }
            }
        }

        if tags:
            # Post-filter by tags
            query = {
                "bool": {
                    "must": [knn_query],
                    "filter": [{"terms": {"tags": tags}}],
                }
            }
        else:
            query = knn_query

        result = await self.client.search(
            index=cfg.BOX_CHUNKS_INDEX,
            body={"query": query, "size": k},
        )

        hits = result["hits"]["hits"]
        chunks = []
        for h in hits:
            src = h["_source"].copy()
            src["_score"] = h["_score"]
            chunks.append(src)

        return chunks

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None


# Singleton
store = OpenSearchStore()
