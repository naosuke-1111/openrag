"""
Text extraction via Docling.

Strategy:
1. If DOCLING_SERVE_URL is configured → call Docling serve API
2. Otherwise → use docling Python library directly
3. Final fallback → basic text extraction (pdfminer / plain text)
"""
import asyncio
import io
import logging
import tempfile
from pathlib import Path
from typing import List

import httpx

import config as cfg

logger = logging.getLogger(__name__)


async def extract_text(
    content: bytes,
    filename: str,
    mime_type: str = "",
) -> str:
    """
    Extract text from file content.

    Returns plain text string suitable for chunking.
    """
    if cfg.DOCLING_SERVE_URL:
        return await _extract_via_serve(content, filename, mime_type)
    return await _extract_via_library(content, filename, mime_type)


async def _extract_via_serve(content: bytes, filename: str, mime_type: str) -> str:
    """Call Docling serve API (POST /convert/file)."""
    url = cfg.DOCLING_SERVE_URL.rstrip("/") + "/v1alpha/convert/file"

    files = {
        "files": (filename, io.BytesIO(content), mime_type or "application/octet-stream"),
    }
    data = {"output_format": "text"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files, data=data, timeout=120.0)
            response.raise_for_status()
            result = response.json()

        # Docling serve returns {"documents": [{"output": "..."}]}
        docs = result.get("documents", [])
        if docs:
            return docs[0].get("output", "") or docs[0].get("text", "")
        return ""
    except Exception as exc:
        logger.warning("Docling serve failed (%s), falling back to library: %s", url, exc)
        return await _extract_via_library(content, filename, mime_type)


async def _extract_via_library(content: bytes, filename: str, mime_type: str) -> str:
    """Extract text using the docling Python library."""
    try:
        from docling.document_converter import DocumentConverter

        def _convert(data: bytes, name: str) -> str:
            with tempfile.NamedTemporaryFile(
                suffix=Path(name).suffix or ".bin", delete=False
            ) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            try:
                converter = DocumentConverter()
                result = converter.convert(tmp_path)
                return result.document.export_to_text()
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _convert, content, filename)
        return text or ""

    except ImportError:
        logger.warning("docling library not installed; using basic text extraction")
        return _basic_extract(content, filename, mime_type)
    except Exception as exc:
        logger.warning("docling library failed: %s; using basic extraction", exc)
        return _basic_extract(content, filename, mime_type)


def _basic_extract(content: bytes, filename: str, mime_type: str) -> str:
    """
    Minimal fallback extractor:
    - .txt / .md / .csv → decode as UTF-8
    - .pdf → pdfminer
    - others → attempt UTF-8 decode
    """
    ext = Path(filename).suffix.lower()

    if ext in (".txt", ".md", ".csv", ".html", ".htm"):
        return content.decode("utf-8", errors="replace")

    if ext == ".pdf":
        try:
            from pdfminer.high_level import extract_text as pdf_extract
            return pdf_extract(io.BytesIO(content)) or ""
        except ImportError:
            logger.warning("pdfminer not installed; returning empty text for PDF")
            return ""
        except Exception as exc:
            logger.warning("pdfminer extraction failed: %s", exc)
            return ""

    # Last resort
    try:
        return content.decode("utf-8", errors="replace")
    except Exception:
        return ""


# ── Chunking ────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
) -> List[str]:
    """
    Split text into overlapping chunks by character count.

    A simple but effective chunker that respects paragraph boundaries
    where possible.
    """
    size = chunk_size or cfg.CHUNK_SIZE
    ov = overlap if overlap is not None else cfg.CHUNK_OVERLAP

    if not text or not text.strip():
        return []

    # Split on double-newline (paragraphs) first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # Para itself may exceed chunk_size → split by chars
            while len(para) > size:
                chunks.append(para[:size])
                para = para[max(0, size - ov):]
            current = para

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


def format_chunk_text(
    chunk: str,
    file_name: str,
    tags: List[str],
) -> str:
    """
    Format a chunk for embedding according to the spec:

    [FILE] <file_name>
    [TAGS] tag1, tag2
    <chunk_body>
    """
    tag_str = ", ".join(tags) if tags else ""
    header = f"[FILE] {file_name}"
    if tag_str:
        header += f"\n[TAGS] {tag_str}"
    return f"{header}\n{chunk}"
