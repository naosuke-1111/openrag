"""
Box API client for Box RAG service.

Handles:
- Shared link resolution (GET /2.0/shared_items)
- Folder recursive enumeration with shared link headers
- File download
- Auth modes: anonymous (public links), CCG, JWT

Uses the Box Python SDK Gen v10 (box-python-sdk-gen) where possible,
with direct HTTP calls for shared link scenarios.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import httpx

import config as cfg

logger = logging.getLogger(__name__)

BOX_API_BASE = "https://api.box.com/2.0"


@dataclass
class BoxItem:
    """Represents a file or folder from Box."""
    id: str
    type: str          # "file" | "folder"
    name: str
    size: int = 0
    modified_at: str = ""
    sha1: str = ""
    mime_type: str = ""
    path: str = ""     # slash-joined parent path for display
    child_count: int = 0  # for folders: total recursive file count

    @property
    def modified_datetime(self) -> Optional[datetime]:
        if self.modified_at:
            try:
                return datetime.fromisoformat(self.modified_at.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def unique_key(self) -> str:
        """Dedup key: box_file_id + modified_at."""
        return f"{self.id}::{self.modified_at}"


class BoxClient:
    """
    Thin wrapper around the Box API for shared link access.

    Auth modes:
    - none:  Anonymous HTTP calls (works for public shared links)
    - ccg:   Client Credentials Grant via box-python-sdk-gen
    - jwt:   JWT via box-python-sdk-gen
    """

    def __init__(self):
        self._sdk_client = None  # lazy-initialised

    # ── Authentication helpers ─────────────────────────────────────────────

    def _get_sdk_client(self):
        """Return a box-python-sdk-gen client (CCG or JWT)."""
        if self._sdk_client:
            return self._sdk_client

        mode = cfg.BOX_AUTH_MODE.lower()

        if mode == "ccg":
            try:
                from box_sdk_gen import BoxClient as BoxSDKClient
                from box_sdk_gen import CCGConfig, BoxCCGAuth

                ccg_config = CCGConfig(
                    client_id=cfg.BOX_CLIENT_ID,
                    client_secret=cfg.BOX_CLIENT_SECRET,
                    enterprise_id=cfg.BOX_ENTERPRISE_ID,
                )
                auth = BoxCCGAuth(config=ccg_config)
                self._sdk_client = BoxSDKClient(auth=auth)
                return self._sdk_client
            except ImportError:
                logger.warning("box-python-sdk-gen not installed; falling back to HTTP-only mode")
                return None

        if mode == "jwt":
            try:
                from box_sdk_gen import BoxClient as BoxSDKClient
                from box_sdk_gen import JWTConfig, BoxJWTAuth

                jwt_config = JWTConfig(
                    client_id=cfg.BOX_CLIENT_ID,
                    client_secret=cfg.BOX_CLIENT_SECRET,
                    enterprise_id=cfg.BOX_ENTERPRISE_ID,
                    jwt_key_id=cfg.BOX_JWT_PUBLIC_KEY_ID,
                    private_key=cfg.BOX_JWT_PRIVATE_KEY,
                    private_key_passphrase=cfg.BOX_JWT_PRIVATE_KEY_PASSPHRASE or None,
                )
                auth = BoxJWTAuth(config=jwt_config)
                self._sdk_client = BoxSDKClient(auth=auth)
                return self._sdk_client
            except ImportError:
                logger.warning("box-python-sdk-gen not installed; falling back to HTTP-only mode")
                return None

        return None  # anonymous / none mode

    async def _get_access_token(self) -> Optional[str]:
        """Return an OAuth access token string if SDK auth is configured."""
        sdk = self._get_sdk_client()
        if sdk is None:
            return None
        try:
            # box-python-sdk-gen exposes token via auth object
            token_obj = await sdk.auth.retrieve_token()
            return token_obj.access_token
        except Exception as exc:
            logger.warning("Could not retrieve Box access token: %s", exc)
            return None

    def _shared_link_headers(
        self, shared_link_url: str, password: Optional[str] = None
    ) -> dict:
        """Build Box shared link HTTP headers."""
        header_val = f"shared_link={shared_link_url}"
        if password:
            header_val += f"&shared_link_password={password}"
        return {"BoxApi": header_val}

    async def _http_headers(
        self,
        shared_link_url: Optional[str] = None,
        shared_link_password: Optional[str] = None,
    ) -> dict:
        """Compose HTTP headers including auth and optional shared link."""
        headers: dict = {"Content-Type": "application/json"}

        access_token = await self._get_access_token()
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        if shared_link_url:
            headers.update(
                self._shared_link_headers(shared_link_url, shared_link_password)
            )

        return headers

    # ── Public API ─────────────────────────────────────────────────────────

    async def resolve_shared_link(
        self, shared_link_url: str, password: Optional[str] = None
    ) -> BoxItem:
        """
        Resolve a Box shared link to a file or folder item.

        Uses GET /2.0/shared_items with BoxApi header.
        """
        headers = await self._http_headers(shared_link_url, password)
        url = f"{BOX_API_BASE}/shared_items"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            if response.status_code == 404:
                raise ValueError("Shared link not found or expired")
            if response.status_code == 403:
                raise PermissionError("Access denied. Check shared link password.")
            response.raise_for_status()
            data = response.json()

        return self._parse_item(data, path="")

    async def list_folder(
        self,
        folder_id: str,
        shared_link_url: Optional[str] = None,
        shared_link_password: Optional[str] = None,
        parent_path: str = "",
    ) -> List[BoxItem]:
        """
        List immediate children of a folder.
        Returns BoxItem list (files and subfolders).
        """
        headers = await self._http_headers(shared_link_url, shared_link_password)
        items: List[BoxItem] = []
        offset = 0
        limit = 1000

        while True:
            url = (
                f"{BOX_API_BASE}/folders/{folder_id}/items"
                f"?limit={limit}&offset={offset}"
                f"&fields=id,type,name,size,modified_at,sha1,item_collection"
            )
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()

            entries = data.get("entries", [])
            for entry in entries:
                path = f"{parent_path}/{entry['name']}" if parent_path else entry["name"]
                items.append(self._parse_item(entry, path=path))

            total_count = data.get("total_count", 0)
            offset += len(entries)
            if offset >= total_count or not entries:
                break

        return items

    async def list_folder_recursive(
        self,
        folder_id: str,
        shared_link_url: Optional[str] = None,
        shared_link_password: Optional[str] = None,
        parent_path: str = "",
        max_files: int = 200,
    ) -> Tuple[List[BoxItem], List[BoxItem]]:
        """
        Recursively enumerate a folder, returning:
        - files:   flat list of all file BoxItems (with path set)
        - folders: flat list of all folder BoxItems

        Stops when max_files is reached.
        """
        all_files: List[BoxItem] = []
        all_folders: List[BoxItem] = []

        children = await self.list_folder(
            folder_id, shared_link_url, shared_link_password, parent_path
        )

        for item in children:
            if item.type == "file":
                all_files.append(item)
                if len(all_files) >= max_files:
                    break
            elif item.type == "folder":
                all_folders.append(item)
                sub_files, sub_folders = await self.list_folder_recursive(
                    item.id,
                    shared_link_url,
                    shared_link_password,
                    parent_path=item.path,
                    max_files=max(1, max_files - len(all_files)),
                )
                all_files.extend(sub_files)
                all_folders.extend(sub_folders)
                if len(all_files) >= max_files:
                    break

        return all_files, all_folders

    async def build_folder_tree(
        self,
        folder_id: str,
        shared_link_url: Optional[str] = None,
        shared_link_password: Optional[str] = None,
        parent_path: str = "",
    ) -> dict:
        """
        Build a tree structure for UI rendering.
        Returns dict with 'id', 'name', 'type', 'path', 'children' (for folders),
        'size', 'modified_at', 'mime_type'.
        """
        children = await self.list_folder(
            folder_id, shared_link_url, shared_link_password, parent_path
        )

        tree_children = []
        for item in children:
            if item.type == "folder":
                subtree = await self.build_folder_tree(
                    item.id,
                    shared_link_url,
                    shared_link_password,
                    parent_path=item.path,
                )
                # Count recursive files
                file_count = _count_files_in_tree(subtree)
                subtree["file_count"] = file_count
                tree_children.append(subtree)
            else:
                tree_children.append({
                    "id": item.id,
                    "type": "file",
                    "name": item.name,
                    "path": item.path,
                    "size": item.size,
                    "modified_at": item.modified_at,
                    "mime_type": item.mime_type,
                })

        return {
            "id": folder_id,
            "type": "folder",
            "name": parent_path.split("/")[-1] if parent_path else "root",
            "path": parent_path,
            "children": tree_children,
        }

    async def download_file(
        self,
        file_id: str,
        shared_link_url: Optional[str] = None,
        shared_link_password: Optional[str] = None,
    ) -> bytes:
        """Download file content by file ID."""
        headers = await self._http_headers(shared_link_url, shared_link_password)
        # Remove Content-Type for download
        headers.pop("Content-Type", None)

        url = f"{BOX_API_BASE}/files/{file_id}/content"

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=120.0)
            response.raise_for_status()
            return response.content

    async def get_file_info(
        self,
        file_id: str,
        shared_link_url: Optional[str] = None,
        shared_link_password: Optional[str] = None,
    ) -> BoxItem:
        """Get file metadata by file ID."""
        headers = await self._http_headers(shared_link_url, shared_link_password)
        url = f"{BOX_API_BASE}/files/{file_id}?fields=id,type,name,size,modified_at,sha1"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()

        return self._parse_item(data, path=data.get("name", ""))

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_item(data: dict, path: str = "") -> BoxItem:
        """Parse a Box API item dict into a BoxItem."""
        mime = data.get("mime_type") or ""
        name = data.get("name", "")
        # Guess mime type from name if not provided
        if not mime and "." in name:
            ext = name.rsplit(".", 1)[-1].lower()
            mime = {
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "txt": "text/plain",
                "md": "text/markdown",
                "html": "text/html",
                "csv": "text/csv",
            }.get(ext, "application/octet-stream")

        return BoxItem(
            id=str(data.get("id", "")),
            type=data.get("type", "file"),
            name=name,
            size=int(data.get("size", 0)),
            modified_at=data.get("modified_at", ""),
            sha1=data.get("sha1", ""),
            mime_type=mime,
            path=path or name,
        )


def _count_files_in_tree(node: dict) -> int:
    """Recursively count files in a tree node."""
    if node.get("type") == "file":
        return 1
    count = 0
    for child in node.get("children", []):
        count += _count_files_in_tree(child)
    return count


# Singleton
box_client = BoxClient()
