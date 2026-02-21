"""Box OAuth 2.0 authentication handler.

Mirrors the structure of the existing OneDrive/SharePoint OAuth handlers.
Tokens are persisted to a local JSON file to survive restarts.
"""

import json
import os
import time
from pathlib import Path

import httpx

from utils.logging_config import get_logger

logger = get_logger(__name__)

AUTH_ENDPOINT = "https://account.box.com/api/oauth2/authorize"
TOKEN_ENDPOINT = "https://api.box.com/oauth2/token"


class BoxOAuth:
    """Box OAuth 2.0 handler (Authorization Code flow).

    Usage::

        oauth = BoxOAuth(client_id=..., client_secret=...)
        token = await oauth.get_access_token()
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_file: str | None = None,
        redirect_uri: str = "http://localhost",
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._token_file = Path(
            token_file or os.getenv("BOX_TOKEN_FILE", "box_token.json")
        )
        self._token_data: dict = {}
        self._load_tokens()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_authorization_url(self, state: str = "") -> str:
        """Return the URL the user must visit to authorise this application."""
        params = (
            f"response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&state={state}"
        )
        return f"{AUTH_ENDPOINT}?{params}"

    async def exchange_code(self, code: str) -> None:
        """Exchange an authorization code for access + refresh tokens."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                },
            )
            resp.raise_for_status()
        self._save_tokens(resp.json())

    async def get_access_token(self) -> str:
        """Return a valid access token, refreshing if necessary."""
        if self._is_token_valid():
            return self._token_data["access_token"]
        await self.refresh_token()
        return self._token_data["access_token"]

    async def refresh_token(self) -> None:
        """Refresh the access token using the stored refresh token."""
        refresh_tok = self._token_data.get("refresh_token")
        if not refresh_tok:
            raise ValueError(
                "No refresh token available. Complete the OAuth flow first by "
                "visiting the authorization URL."
            )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tok,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()
        self._save_tokens(resp.json())
        logger.info("Box access token refreshed successfully")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_token_valid(self) -> bool:
        token = self._token_data.get("access_token")
        expires_at = self._token_data.get("expires_at", 0)
        return bool(token) and time.time() < expires_at - 60

    def _save_tokens(self, data: dict) -> None:
        data["expires_at"] = time.time() + data.get("expires_in", 3600)
        self._token_data = data
        try:
            self._token_file.write_text(json.dumps(data, indent=2))
        except OSError as exc:
            logger.warning("Could not save Box token file", error=str(exc))

    def _load_tokens(self) -> None:
        if self._token_file.exists():
            try:
                self._token_data = json.loads(self._token_file.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load Box token file", error=str(exc))
                self._token_data = {}
