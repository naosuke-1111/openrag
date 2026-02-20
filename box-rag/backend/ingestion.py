"""
Ingestion pipeline for Box RAG service.

Flow:
1. Download file bytes from Box
2. Extract text via Docling
3. Chunk text with overlap
4. Format chunks: [FILE] ... [TAGS] ...
5. Embed chunks via watsonx.ai
6. Delete old chunks from OpenSearch
7. Index new chunks + update document record
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import box_client as bc
import docling_client as dc
import opensearch_store as os_store
import watsonx_client as wx
import config as cfg

logger = logging.getLogger(__name__)

# ── Job registry (in-memory, suitable for single-process deployment) ────────
# For multi-replica deployments, replace with Redis or DB-backed store.

_jobs: dict = {}   # job_id → JobStatus


class JobStatus:
    def __init__(self, job_id: str, total: int):
        self.job_id = job_id
        self.total = total
        self.done = 0
        self.failed = 0
        self.errors: List[dict] = []
        self.status = "running"  # running | completed | failed
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "total": self.total,
            "done": self.done,
            "failed": self.failed,
            "errors": self.errors,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


def get_job(job_id: str) -> Optional[dict]:
    job = _jobs.get(job_id)
    return job.to_dict() if job else None


# ── Ingestion helpers ────────────────────────────────────────────────────────

async def _ingest_single_file(
    *,
    box_file_id: str,
    file_name: str,
    modified_at: str,
    mime_type: str,
    file_size: int,
    tags: List[str],
    shared_link_url: str,
    shared_link_password: Optional[str],
    force_reingest: bool = False,
) -> dict:
    """
    Ingest one Box file into OpenSearch.
    Returns {"status": "indexed"|"skipped"|"failed", "document_id": "...", "chunks": N}
    """
    # Check dedup
    if not force_reingest:
        needs = await os_store.store.needs_reingestion(box_file_id, modified_at)
        if not needs:
            existing = await os_store.store.get_document_by_box_id(box_file_id)
            doc_id = existing["document_id"] if existing else "unknown"
            logger.info("Skipping already-indexed file: %s (%s)", file_name, box_file_id)
            return {"status": "skipped", "document_id": doc_id, "chunks": 0}

    # Upsert document record with status=pending
    document_id = await os_store.store.upsert_document(
        box_file_id=box_file_id,
        file_name=file_name,
        tags=tags,
        shared_link_url=shared_link_url,
        modified_at=modified_at,
        mime_type=mime_type,
        file_size=file_size,
        status="pending",
    )

    try:
        # 1. Download
        logger.info("Downloading file: %s (id=%s)", file_name, box_file_id)
        content = await bc.box_client.download_file(
            file_id=box_file_id,
            shared_link_url=shared_link_url,
            shared_link_password=shared_link_password,
        )

        # 2. Extract text
        logger.info("Extracting text from: %s", file_name)
        raw_text = await dc.extract_text(content, file_name, mime_type)
        if not raw_text or not raw_text.strip():
            raise ValueError("No text extracted from document")

        # 3. Chunk
        raw_chunks = dc.chunk_text(raw_text)
        if not raw_chunks:
            raise ValueError("Chunking produced no chunks")

        # 4. Format chunks with header
        formatted_chunks = [
            dc.format_chunk_text(c, file_name, tags) for c in raw_chunks
        ]

        # 5. Embed (batch to avoid timeouts)
        EMBED_BATCH = 32
        all_embeddings = []
        for i in range(0, len(formatted_chunks), EMBED_BATCH):
            batch = formatted_chunks[i : i + EMBED_BATCH]
            embeddings = await wx.embed_texts(batch)
            all_embeddings.extend(embeddings)

        # 6. Delete old chunks
        await os_store.store.delete_chunks_for_document(document_id)

        # 7. Build chunk docs
        now = datetime.now(timezone.utc).isoformat()
        chunk_docs = []
        for idx, (text, embedding) in enumerate(zip(formatted_chunks, all_embeddings)):
            chunk_docs.append({
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "box_file_id": box_file_id,
                "file_name": file_name,
                "tags": tags,
                "modified_at": modified_at,
                "chunk_index": idx,
                "text": text,
                "embedding": embedding,
                "page": None,
            })

        # 8. Index chunks
        await os_store.store.index_chunks(chunk_docs)

        # 9. Update document record
        await os_store.store.update_document_status(
            document_id=document_id,
            status="indexed",
            chunk_count=len(chunk_docs),
        )

        logger.info(
            "Indexed file: %s → %d chunks (doc_id=%s)", file_name, len(chunk_docs), document_id
        )
        return {"status": "indexed", "document_id": document_id, "chunks": len(chunk_docs)}

    except Exception as exc:
        logger.exception("Failed to ingest file %s: %s", file_name, exc)
        await os_store.store.update_document_status(
            document_id=document_id,
            status="failed",
            error=str(exc)[:500],
        )
        return {"status": "failed", "document_id": document_id, "error": str(exc)}


# ── Public ingestion API ─────────────────────────────────────────────────────

async def start_ingestion_job(
    *,
    selected_files: List[dict],
    tags: List[str],
    shared_link_url: str,
    shared_link_password: Optional[str] = None,
    force_reingest: bool = False,
) -> str:
    """
    Create and start an async ingestion job.

    selected_files: list of dicts with keys:
      - id:          Box file ID
      - name:        file name
      - modified_at: ISO timestamp
      - mime_type:   MIME type
      - size:        file size in bytes

    Returns job_id.
    """
    job_id = str(uuid.uuid4())
    job = JobStatus(job_id=job_id, total=len(selected_files))
    _jobs[job_id] = job

    asyncio.create_task(
        _run_ingestion_job(
            job=job,
            selected_files=selected_files,
            tags=tags,
            shared_link_url=shared_link_url,
            shared_link_password=shared_link_password,
            force_reingest=force_reingest,
        )
    )

    return job_id


async def _run_ingestion_job(
    *,
    job: JobStatus,
    selected_files: List[dict],
    tags: List[str],
    shared_link_url: str,
    shared_link_password: Optional[str],
    force_reingest: bool,
):
    """Background task that processes all selected files."""
    # Ensure indexes exist
    await os_store.store.ensure_indexes()

    for file_info in selected_files:
        result = await _ingest_single_file(
            box_file_id=file_info["id"],
            file_name=file_info["name"],
            modified_at=file_info.get("modified_at", ""),
            mime_type=file_info.get("mime_type", "application/octet-stream"),
            file_size=file_info.get("size", 0),
            tags=tags,
            shared_link_url=shared_link_url,
            shared_link_password=shared_link_password,
            force_reingest=force_reingest,
        )

        if result["status"] in ("indexed", "skipped"):
            job.done += 1
        else:
            job.failed += 1
            job.errors.append({
                "file": file_info.get("name"),
                "error": result.get("error", "unknown"),
            })

    # Mark job complete
    job.status = "completed" if job.failed == 0 else "completed_with_errors"
    job.finished_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Job %s finished: done=%d, failed=%d",
        job.job_id, job.done, job.failed,
    )
