"""Unit tests for BoxConnector and BoxOAuth."""

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import respx
import httpx

from connectors.box.oauth import BoxOAuth


# ---------------------------------------------------------------------------
# BoxOAuth tests
# ---------------------------------------------------------------------------

def test_box_oauth_authorization_url():
    oauth = BoxOAuth(client_id="my_client", client_secret="my_secret", redirect_uri="http://localhost:8000/callback")
    url = oauth.get_authorization_url(state="xyz")
    assert "client_id=my_client" in url
    assert "state=xyz" in url
    assert "https://account.box.com" in url


def test_box_oauth_loads_tokens_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        token_data = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "expires_at": time.time() + 3600,
        }
        json.dump(token_data, f)
        token_file = f.name

    oauth = BoxOAuth(client_id="id", client_secret="secret", token_file=token_file)
    assert oauth._token_data["access_token"] == "test_access_token"


@pytest.mark.asyncio
async def test_box_oauth_get_access_token_returns_cached_token():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        token_data = {
            "access_token": "valid_token",
            "refresh_token": "refresh_tok",
            "expires_in": 3600,
            "expires_at": time.time() + 3600,
        }
        json.dump(token_data, f)
        token_file = f.name

    oauth = BoxOAuth(client_id="id", client_secret="secret", token_file=token_file)
    token = await oauth.get_access_token()
    assert token == "valid_token"


@pytest.mark.asyncio
@respx.mock
async def test_box_oauth_refresh_token():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        token_data = {
            "access_token": "old_token",
            "refresh_token": "old_refresh",
            "expires_in": 3600,
            "expires_at": time.time() - 1,  # Expired
        }
        json.dump(token_data, f)
        token_file = f.name

    respx.post("https://api.box.com/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "new_token",
                "refresh_token": "new_refresh",
                "expires_in": 3600,
            },
        )
    )

    oauth = BoxOAuth(client_id="id", client_secret="secret", token_file=token_file)
    token = await oauth.get_access_token()
    assert token == "new_token"
