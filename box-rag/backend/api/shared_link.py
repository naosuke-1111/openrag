"""
POST /shared-link/resolve

Resolves a Box shared link (file or folder) and returns:
- For file:   file metadata
- For folder: folder tree with file counts
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

import box_client as bc

logger = logging.getLogger(__name__)
router = APIRouter()

TAG_PATTERN = re.compile(r"^[\u3000-\u9FFF\uF900-\uFAFF\uFF01-\uFF9F\u0041-\u005A\u0061-\u007A\u0030-\u0039\u3040-\u30FF\u4E00-\u9FFF\u00C0-\u024F]*$")
# Allow: full-width chars (CJK, Katakana, Hiragana, etc.) + half-width alphanumeric
# Reject: half-width symbols, full-width symbols

MAX_TAGS = 20
MAX_TAG_LEN = 64


class SharedLinkRequest(BaseModel):
    shared_link_url: str
    shared_link_password: Optional[str] = None
    tags: Optional[list[str]] = None

    @field_validator("tags", mode="before")
    @classmethod
    def parse_and_validate_tags(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            # Allow comma or space separated
            import re as _re
            v = [t for t in _re.split(r"[,\s]+", v) if t]
        if len(v) > MAX_TAGS:
            raise ValueError(f"Maximum {MAX_TAGS} tags allowed")
        result = []
        for tag in v:
            tag = tag.lower()  # auto lowercase half-width alpha
            if len(tag) > MAX_TAG_LEN:
                raise ValueError(f"Tag '{tag}' exceeds {MAX_TAG_LEN} chars")
            if not TAG_PATTERN.match(tag):
                raise ValueError(
                    f"Tag '{tag}' contains invalid characters. "
                    "Only full-width characters and half-width alphanumerics are allowed."
                )
            result.append(tag)
        return result


@router.post("/shared-link/resolve")
async def resolve_shared_link(req: SharedLinkRequest):
    """
    Resolve a Box shared link.

    Returns:
    - type: "file" or "folder"
    - For file: file metadata dict
    - For folder: nested tree dict + flat file list
    """
    try:
        item = await bc.box_client.resolve_shared_link(
            req.shared_link_url, req.shared_link_password
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to resolve shared link: %s", exc)
        raise HTTPException(status_code=502, detail=f"Box API error: {exc}")

    if item.type == "file":
        return {
            "type": "file",
            "item": {
                "id": item.id,
                "name": item.name,
                "size": item.size,
                "modified_at": item.modified_at,
                "mime_type": item.mime_type,
                "path": item.path,
            },
            "tags": req.tags or [],
        }

    # Folder: build tree
    try:
        tree = await bc.box_client.build_folder_tree(
            folder_id=item.id,
            shared_link_url=req.shared_link_url,
            shared_link_password=req.shared_link_password,
            parent_path=item.name,
        )
        # Also return flat file list for selection
        files, _ = await bc.box_client.list_folder_recursive(
            folder_id=item.id,
            shared_link_url=req.shared_link_url,
            shared_link_password=req.shared_link_password,
            parent_path=item.name,
        )
        flat_files = [
            {
                "id": f.id,
                "name": f.name,
                "size": f.size,
                "modified_at": f.modified_at,
                "mime_type": f.mime_type,
                "path": f.path,
            }
            for f in files
        ]
    except Exception as exc:
        logger.exception("Failed to list folder: %s", exc)
        raise HTTPException(status_code=502, detail=f"Box folder listing error: {exc}")

    return {
        "type": "folder",
        "folder_name": item.name,
        "tree": tree,
        "files": flat_files,
        "tags": req.tags or [],
    }
