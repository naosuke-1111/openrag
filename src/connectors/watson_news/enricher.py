"""AI エンリッチメント処理: 要約、感情分析、エンティティ抽出、
トピック分類、および watsonx.ai オンプレミスによる埋め込み生成。
"""

import asyncio
import json
import os
import ssl
from typing import Any

import httpx
from utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 設定（環境変数から読み込み – .env / .creds_example の値を使用）
# ---------------------------------------------------------------------------
WATSONX_API_URL = os.getenv("WATSONX_API_URL", "")
WATSONX_API_KEY = os.getenv("WATSONX_API_KEY", "")
WATSONX_AUTH_URL = os.getenv(
    "WATSONX_AUTH_URL", ""
)
WATSONX_API_VERSION = os.getenv("WATSONX_API_VERSION", "2025-02-06")
WATSONX_SSL_VERIFY = os.getenv("WATSONX_SSL_VERIFY", "true").lower() not in (
    "false", "0", "no"
)
WATSONX_CA_BUNDLE_PATH = os.getenv("WATSONX_CA_BUNDLE_PATH", "")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_USERNAME = os.getenv("WATSONX_USERNAME", "")
WATSONX_PASSWORD = os.getenv("WATSONX_PASSWORD", "")

# LLM と埋め込みモデル
WATSON_NEWS_ENRICH_MODEL = os.getenv(
    "WATSON_NEWS_ENRICH_MODEL", os.getenv("WATSONX_LLM_ID1", "openai/gpt-oss-120b")
)
WATSON_NEWS_EMBED_MODEL = os.getenv(
    "WATSON_NEWS_EMBED_MODEL",
    os.getenv("WATSONX_LLM_ID3", "ibm/granite-embedding-107m-multilingual"),
)

# Watson News の埋め込み次元数（granite-embedding-107m-multilingual = 384）
WATSON_NEWS_EMBED_DIM = 384

_ENRICH_PROMPT_TEMPLATE = """You are an AI analyst. Analyze the following news article and return a JSON object with these fields:
- summary: a concise 2-3 sentence summary in the same language as the article
- sentiment_label: one of "positive", "neutral", or "negative"
- sentiment_score: float between -1.0 (very negative) and 1.0 (very positive)
- entities: list of objects with "name" (string) and "type" (one of "org", "person", "location", "product", "technology")
- topic: one of "ai", "cloud", "security", "consulting", "finance", "research", "other"

Respond ONLY with valid JSON, no markdown fences.

Article title: {title}
Article body:
{body}"""


def _build_ssl_context() -> bool | ssl.SSLContext:
    """環境設定に基づいて SSL コンテキストを構築する。"""
    if not WATSONX_SSL_VERIFY:
        return False
    if WATSONX_CA_BUNDLE_PATH:
        ctx = ssl.create_default_context(cafile=WATSONX_CA_BUNDLE_PATH)
        return ctx
    return True


class WatsonXClient:
    """watsonx.ai オンプレミス REST API 向けの軽量非同期クライアント。"""

    def __init__(self) -> None:
        ssl_verify = _build_ssl_context()
        self._http = httpx.AsyncClient(
            verify=ssl_verify,
            timeout=httpx.Timeout(120.0, connect=30.0),
            follow_redirects=True,
        )
        self._bearer_token: str | None = None

    async def _get_bearer_token(self) -> str:
        """ICP4D 認証エンドポイントからベアラートークンを取得する。"""
        if self._bearer_token:
            return self._bearer_token

        payload = {"username": WATSONX_USERNAME, "password": WATSONX_PASSWORD}
        resp = await self._http.post(WATSONX_AUTH_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("token") or data.get("access_token", "")
        self._bearer_token = token
        return token

    async def _auth_headers(self) -> dict[str, str]:
        token = await self._get_bearer_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def generate(self, prompt: str, max_new_tokens: int = 1024) -> str:
        """watsonx.ai テキスト生成エンドポイントを呼び出す。"""
        headers = await self._auth_headers()
        url = (
            f"{WATSONX_API_URL}/ml/v1/text/generation"
            f"?version={WATSONX_API_VERSION}"
        )
        payload = {
            "model_id": WATSON_NEWS_ENRICH_MODEL,
            "project_id": WATSONX_PROJECT_ID,
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": max_new_tokens,
                "repetition_penalty": 1.05,
            },
        }
        for attempt in range(1, 4):
            try:
                resp = await self._http.post(url, headers=headers, json=payload)
                if resp.status_code == 401:
                    # トークンが期限切れの可能性 — リフレッシュしてリトライ
                    self._bearer_token = None
                    headers = await self._auth_headers()
                    continue
                resp.raise_for_status()
                result = resp.json()
                return result["results"][0]["generated_text"].strip()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning("WatsonX generate error", attempt=attempt, error=str(exc))
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)
        return ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """watsonx.ai 埋め込みエンドポイントを呼び出す。"""
        headers = await self._auth_headers()
        url = (
            f"{WATSONX_API_URL}/ml/v1/text/embeddings"
            f"?version={WATSONX_API_VERSION}"
        )
        payload = {
            "model_id": WATSON_NEWS_EMBED_MODEL,
            "project_id": WATSONX_PROJECT_ID,
            "inputs": texts,
        }
        for attempt in range(1, 4):
            try:
                resp = await self._http.post(url, headers=headers, json=payload)
                if resp.status_code == 401:
                    self._bearer_token = None
                    headers = await self._auth_headers()
                    continue
                resp.raise_for_status()
                data = resp.json()
                return [item["embedding"] for item in data["results"]]
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning("WatsonX embed error", attempt=attempt, error=str(exc))
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)
        return [[] for _ in texts]

    async def close(self) -> None:
        await self._http.aclose()


# モジュールレベルのシングルトン
_client: WatsonXClient | None = None


def get_watsonx_client() -> WatsonXClient:
    global _client
    if _client is None:
        _client = WatsonXClient()
    return _client


async def enrich_article(clean_record: dict[str, Any]) -> dict[str, Any]:
    """クリーニング済みニュース記事レコードを AI 生成フィールドでエンリッチする。

    追加されるフィールド: ``summary``、``sentiment_label``、``sentiment_score``、
    ``entities``、``topic``、``vector``。
    """
    title = clean_record.get("title", "")
    body = clean_record.get("clean_body", "")[:4000]  # トークンオーバーフロー防止のため切り捨て

    prompt = _ENRICH_PROMPT_TEMPLATE.format(title=title, body=body)
    client = get_watsonx_client()

    try:
        raw_json = await client.generate(prompt)
        parsed = json.loads(raw_json)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(
            "Failed to parse enrichment JSON", error=str(exc), url=clean_record.get("url")
        )
        parsed = {
            "summary": "",
            "sentiment_label": "neutral",
            "sentiment_score": 0.0,
            "entities": [],
            "topic": "other",
        }

    embed_text = f"{title}\n{body}"
    vectors = await client.embed([embed_text])
    vector = vectors[0] if vectors else []

    return {
        **clean_record,
        "summary": parsed.get("summary", ""),
        "sentiment_label": parsed.get("sentiment_label", "neutral"),
        "sentiment_score": float(parsed.get("sentiment_score", 0.0)),
        "entities": parsed.get("entities", []),
        "topic": parsed.get("topic", "other"),
        "vector": vector,
        "enrich_model": WATSON_NEWS_ENRICH_MODEL,
        "embed_model": WATSON_NEWS_EMBED_MODEL,
    }


async def enrich_box_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Box ドキュメントチャンクを埋め込み（およびオプションのトピック抽出）でエンリッチする。"""
    text = chunk.get("clean_text", "")[:4000]
    client = get_watsonx_client()

    vectors = await client.embed([text])
    vector = vectors[0] if vectors else []

    return {
        **chunk,
        "vector": vector,
        "embed_model": WATSON_NEWS_EMBED_MODEL,
    }
