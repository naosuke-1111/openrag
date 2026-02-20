"""
POST /ingest/selection  → start ingestion job
GET  /ingest/jobs/{job_id} → get job status
GET  /documents         → list ingested documents
DELETE /documents/{document_id} → delete document + chunks
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import ingestion
import opensearch_store as os_store

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILES_PER_JOB = 20


class FileSelection(BaseModel):
    id: str
    name: str
    modified_at: str = ""
    mime_type: str = "application/octet-stream"
    size: int = 0


class IngestSelectionRequest(BaseModel):
    shared_link_url: str
    shared_link_password: Optional[str] = None
    tags: List[str] = []
    files: List[FileSelection]
    force_reingest: bool = False


@router.post("/ingest/selection", status_code=202)
async def ingest_selection(req: IngestSelectionRequest):
    """
    Start an async ingestion job for selected Box files.

    Returns job_id for polling.
    Limits to MAX_FILES_PER_JOB files per request.
    """
    if not req.files:
        raise HTTPException(status_code=400, detail="No files selected")

    if len(req.files) > MAX_FILES_PER_JOB:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES_PER_JOB} files per ingestion job",
        )

    # Ensure indexes exist before starting
    try:
        await os_store.store.ensure_indexes()
    except Exception as exc:
        logger.exception("OpenSearch index creation failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"OpenSearch unavailable: {exc}")

    selected = [f.model_dump() for f in req.files]

    job_id = await ingestion.start_ingestion_job(
        selected_files=selected,
        tags=req.tags,
        shared_link_url=req.shared_link_url,
        shared_link_password=req.shared_link_password,
        force_reingest=req.force_reingest,
    )

    return {
        "job_id": job_id,
        "status": "accepted",
        "total": len(selected),
        "message": f"Ingestion job started for {len(selected)} file(s)",
    }


@router.get("/ingest/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of an ingestion job."""
    job = ingestion.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/documents")
async def list_documents(
    tags: Optional[str] = None,
    status: Optional[str] = None,
    size: int = 50,
    from_: int = 0,
):
    """
    List ingested Box documents.

    Query params:
    - tags:   comma-separated tag filter
    - status: filter by status (pending|indexed|failed)
    - size:   page size (default 50)
    - from_:  offset
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    try:
        result = await os_store.store.list_documents(
            tags=tag_list,
            status=status,
            size=size,
            from_=from_,
        )
    except Exception as exc:
        logger.exception("Failed to list documents: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    return result


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """Delete a document and all its chunks."""
    try:
        await os_store.store.delete_document(document_id)
    except Exception as exc:
        logger.exception("Failed to delete document %s: %s", document_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
