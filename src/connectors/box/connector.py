"""Box connector using OAuth 2.0.

Follows the same pattern as OneDriveConnector / SharePointConnector.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from connectors.base import BaseConnector, ConnectorDocument, DocumentACL
from connectors.box.oauth import BoxOAuth
from utils.logging_config import get_logger

logger = get_logger(__name__)

BOX_API_BASE = "https://api.box.com/2.0"
BOX_TARGET_FOLDER_ID = os.getenv("BOX_TARGET_FOLDER_ID", "0")


class BoxConnector(BaseConnector):
    """Box connector using OAuth 2.0 for authentication.

    Follows the same pattern as OneDriveConnector / SharePointConnector.
    """

    CLIENT_ID_ENV_VAR = "BOX_OAUTH_CLIENT_ID"
    CLIENT_SECRET_ENV_VAR = "BOX_OAUTH_CLIENT_SECRET"  # pragma: allowlist secret

    CONNECTOR_NAME = "Box"
    CONNECTOR_DESCRIPTION = "Add knowledge from Box"
    CONNECTOR_ICON = "box"

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config or {})
        self._oauth: BoxOAuth | None = None
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Initialise OAuth handler (tokens must already be stored on disk)."""
        try:
            client_id = self.get_client_id()
            client_secret = self.get_client_secret()
        except ValueError as exc:
            logger.warning("Box OAuth credentials not configured", error=str(exc))
            return False

        self._oauth = BoxOAuth(
            client_id=client_id,
            client_secret=client_secret,
        )
        self._http = httpx.AsyncClient(
            base_url=BOX_API_BASE,
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        )
        self._authenticated = True
        return True

    async def setup_subscription(self) -> str:
        """Box webhook subscription — not needed for ETL polling."""
        return ""

    async def list_files(
        self,
        page_token: Optional[str] = None,
        max_files: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List files in the target Box folder (root by default)."""
        folder_id = self.config.get("folder_id", BOX_TARGET_FOLDER_ID)
        return await self._list_folder_recursive(folder_id)

    async def get_file_content(self, file_id: str) -> ConnectorDocument:
        """Download a Box file and return a ConnectorDocument."""
        return await self.download_file(file_id)

    async def handle_webhook(self, payload: Dict[str, Any]) -> List[str]:
        """Handle Box webhook events."""
        source = payload.get("source", {})
        file_id = source.get("id")
        return [file_id] if file_id else []

    async def cleanup_subscription(self, subscription_id: str) -> bool:
        return True

    # ------------------------------------------------------------------
    # Box-specific helpers
    # ------------------------------------------------------------------

    async def _auth_headers(self) -> Dict[str, str]:
        token = await self._oauth.get_access_token()  # type: ignore[union-attr]
        return {"Authorization": f"Bearer {token}"}

    async def _list_folder_recursive(
        self, folder_id: str
    ) -> Dict[str, Any]:
        """Recursively list all files under *folder_id*."""
        headers = await self._auth_headers()
        files: list[dict] = []

        url = f"/folders/{folder_id}/items"
        params = {"fields": "id,name,type,modified_at,size,shared_link", "limit": 200}

        while url:
            resp = await self._http.get(url, headers=headers, params=params)  # type: ignore[union-attr]
            resp.raise_for_status()
            data = resp.json()
            for entry in data.get("entries", []):
                if entry["type"] == "file":
                    files.append(entry)
                elif entry["type"] == "folder":
                    sub = await self._list_folder_recursive(entry["id"])
                    files.extend(sub.get("files", []))
            # Pagination
            offset = data.get("offset", 0) + data.get("limit", 200)
            if offset < data.get("total_count", 0):
                params = {**params, "offset": offset}  # type: ignore[arg-type]
            else:
                break

        return {"files": files}

    async def download_file(self, file_id: str) -> ConnectorDocument:
        """Download a Box file by ID."""
        headers = await self._auth_headers()

        # Metadata
        meta_resp = await self._http.get(  # type: ignore[union-attr]
            f"/files/{file_id}",
            headers=headers,
            params={"fields": "id,name,modified_at,created_at,size,parent"},
        )
        meta_resp.raise_for_status()
        meta = meta_resp.json()

        # Content
        content_resp = await self._http.get(  # type: ignore[union-attr]
            f"/files/{file_id}/content",
            headers=headers,
        )
        content_resp.raise_for_status()

        name = meta.get("name", f"box_file_{file_id}")
        modified_at = meta.get("modified_at", "")
        created_at = meta.get("created_at", "")

        def _parse_dt(s: str) -> datetime:
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return datetime.now(tz=timezone.utc)

        mimetype = _guess_mimetype(name)

        return ConnectorDocument(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"box:{file_id}")),
            filename=name,
            mimetype=mimetype,
            content=content_resp.content,
            source_url=f"https://app.box.com/file/{file_id}",
            acl=DocumentACL(owner="box"),
            modified_time=_parse_dt(modified_at),
            created_time=_parse_dt(created_at),
            metadata={
                "source_type": "box",
                "box_file_id": file_id,
                "parent_folder": meta.get("parent", {}).get("id", ""),
            },
        )

    async def get_updated_files(
        self,
        folder_id: str,
        since: datetime,
    ) -> list[Dict[str, Any]]:
        """Return files modified after *since* (differential fetch)."""
        all_files_data = await self._list_folder_recursive(folder_id)
        updated = []
        for f in all_files_data.get("files", []):
            modified_at_str = f.get("modified_at", "")
            try:
                modified_at = datetime.fromisoformat(modified_at_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if modified_at > since:
                updated.append(f)
        return updated

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()


def _guess_mimetype(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    _map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "txt": "text/plain",
        "md": "text/markdown",
        "html": "text/html",
        "htm": "text/html",
        "csv": "text/csv",
    }
    return _map.get(ext, "application/octet-stream")
