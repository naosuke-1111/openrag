"""
watsonx.ai client for Box RAG service.

Handles:
- ICP4D bearer token authentication (username/password)
- Text embeddings via /ml/v1/text/embeddings
- Text generation via /ml/v1/text/generation
- Automatic token refresh
"""
import time
import logging
from typing import List, Optional
import httpx

import config as cfg

logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict = {"token": None, "expires_at": 0}
_TOKEN_TTL_BUFFER = 60  # seconds before expiry to refresh


def _get_ssl_verify():
    """Get SSL verification setting."""
    if not cfg.WATSONX_SSL_VERIFY:
        return False
    if cfg.WATSONX_CA_BUNDLE_PATH:
        return cfg.WATSONX_CA_BUNDLE_PATH
    return True


async def _fetch_bearer_token() -> str:
    """Authenticate with ICP4D and return bearer token."""
    ssl_verify = _get_ssl_verify()

    # Prefer API key auth if available (direct Bearer usage)
    # For ICP4D: POST /icp4d-api/v1/authorize with username/password
    async with httpx.AsyncClient(verify=ssl_verify) as client:
        response = await client.post(
            cfg.WATSONX_AUTH_URL,
            json={"username": cfg.WATSONX_USERNAME, "password": cfg.WATSONX_PASSWORD},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            raise RuntimeError(f"No token in auth response: {data}")
        return token


async def get_bearer_token() -> str:
    """Return a valid bearer token, refreshing if necessary."""
    now = time.time()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"] - _TOKEN_TTL_BUFFER:
        return _TOKEN_CACHE["token"]

    logger.debug("Fetching new watsonx.ai bearer token")
    token = await _fetch_bearer_token()
    # Tokens typically expire in 3600s; we assume 3600 if not specified
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = now + 3600
    return token


async def _get_auth_headers() -> dict:
    """Return Authorization headers.

    ICP4D deployments use username/password → bearer token.
    If WATSONX_API_KEY is provided it is used as the bearer token directly,
    bypassing the username/password token exchange.
    """
    if cfg.WATSONX_API_KEY:
        return {"Authorization": f"Bearer {cfg.WATSONX_API_KEY}"}
    token = await get_bearer_token()
    return {"Authorization": f"Bearer {token}"}


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Get embeddings for a list of texts using watsonx.ai.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (one per input text)
    """
    ssl_verify = _get_ssl_verify()
    headers = await _get_auth_headers()
    headers["Content-Type"] = "application/json"

    url = (
        f"{cfg.WATSONX_API_URL}/ml/v1/text/embeddings"
        f"?version={cfg.WATSONX_API_VERSION}"
    )

    payload = {
        "model_id": cfg.WATSONX_EMBED_MODEL,
        "inputs": texts,
        "project_id": cfg.WATSONX_PROJECT_ID,
    }

    logger.debug("Requesting embeddings: model=%s, count=%d", cfg.WATSONX_EMBED_MODEL, len(texts))

    async with httpx.AsyncClient(verify=ssl_verify) as client:
        response = await client.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    embeddings = [r["embedding"] for r in results]
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Expected {len(texts)} embeddings, got {len(embeddings)}"
        )
    return embeddings


async def embed_single(text: str) -> List[float]:
    """Embed a single text string."""
    embeddings = await embed_texts([text])
    return embeddings[0]


async def generate_text(
    prompt: str,
    max_new_tokens: int = None,
    temperature: float = 0.7,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Generate text using watsonx.ai LLM.

    Args:
        prompt: User prompt
        max_new_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        system_prompt: Optional system prompt

    Returns:
        Generated text string
    """
    ssl_verify = _get_ssl_verify()
    headers = await _get_auth_headers()
    headers["Content-Type"] = "application/json"

    url = (
        f"{cfg.WATSONX_API_URL}/ml/v1/text/generation"
        f"?version={cfg.WATSONX_API_VERSION}"
    )

    # Build input with optional system prompt
    if system_prompt:
        full_input = f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n<|assistant|>\n"
    else:
        full_input = prompt

    payload = {
        "model_id": cfg.WATSONX_LLM_MODEL,
        "input": full_input,
        "parameters": {
            "decoding_method": "greedy" if temperature == 0 else "sample",
            "max_new_tokens": max_new_tokens or cfg.RAG_MAX_TOKENS,
            "temperature": temperature,
            "stop_sequences": ["<|user|>", "<|endoftext|>"],
        },
        "project_id": cfg.WATSONX_PROJECT_ID,
    }

    logger.debug("Requesting text generation", model=cfg.WATSONX_LLM_MODEL)

    async with httpx.AsyncClient(verify=ssl_verify, timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    if not results:
        raise RuntimeError(f"No results in generation response: {data}")

    return results[0].get("generated_text", "").strip()


async def rag_answer(question: str, context_chunks: List[dict]) -> str:
    """
    Generate a RAG answer given a question and retrieved context chunks.

    Args:
        question: User question
        context_chunks: List of chunk dicts with 'text', 'file_name', 'tags'

    Returns:
        Generated answer
    """
    if not context_chunks:
        return "関連するドキュメントが見つかりませんでした。"

    # Build context string
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        file_name = chunk.get("file_name", "Unknown")
        tags = ", ".join(chunk.get("tags", []))
        text = chunk.get("text", "")
        context_parts.append(
            f"[参考文書{i}] ファイル: {file_name}"
            + (f" | タグ: {tags}" if tags else "")
            + f"\n{text}"
        )

    context_str = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "あなたは社内ドキュメントに基づいて質問に答えるアシスタントです。"
        "提供された参考文書のみを根拠として回答してください。"
        "参考文書に答えが見つからない場合は、その旨を伝えてください。"
        "回答は日本語で行ってください。"
    )

    user_prompt = (
        f"以下の参考文書を元に質問に答えてください。\n\n"
        f"## 参考文書\n{context_str}\n\n"
        f"## 質問\n{question}"
    )

    return await generate_text(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.1,
    )
