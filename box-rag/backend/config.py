"""
Configuration module for Box RAG service.
Loads from .env file if present, otherwise from environment (OCP Secret mount).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the box-rag directory or parent directory
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)
else:
    # Fallback: look for .env in current working directory (OCP volume mount)
    load_dotenv(override=False)


# ── watsonx.ai ─────────────────────────────────────────────────────────────
WATSONX_API_URL: str = os.environ["WATSONX_API_URL"]
WATSONX_API_KEY: str = os.getenv("WATSONX_API_KEY", "")
WATSONX_AUTH_URL: str = os.environ["WATSONX_AUTH_URL"]
WATSONX_API_VERSION: str = os.getenv("WATSONX_API_VERSION", "2025-02-06")
WATSONX_PROJECT_ID: str = os.environ["WATSONX_PROJECT_ID"]
WATSONX_USERNAME: str = os.getenv("WATSONX_USERNAME", "")
WATSONX_PASSWORD: str = os.getenv("WATSONX_PASSWORD", "")
WATSONX_SSL_VERIFY: bool = os.getenv("WATSONX_SSL_VERIFY", "false").lower() not in ("false", "0", "no")
WATSONX_CA_BUNDLE_PATH: str = os.getenv("WATSONX_CA_BUNDLE_PATH", "")

# LLM / embedding model IDs
WATSONX_LLM_MODEL: str = os.getenv("WATSONX_LLM_ID1", "openai/gpt-oss-120b")
WATSONX_EMBED_MODEL: str = os.getenv("WATSONX_LLM_ID3", "ibm/granite-embedding-107m-multilingual")

# Known embedding dimensions
EMBED_DIMENSIONS: dict = {
    "ibm/granite-embedding-107m-multilingual": 384,
    "ibm/granite-embedding-278m-multilingual": 1024,
    "ibm/slate-125m-english-rtrvr": 768,
    "ibm/slate-125m-english-rtrvr-v2": 768,
}
EMBED_DIM: int = EMBED_DIMENSIONS.get(WATSONX_EMBED_MODEL, 384)

# ── OpenSearch ──────────────────────────────────────────────────────────────
OPENSEARCH_HOST: str = os.getenv("OPENSEARCH_HOST", "opensearch")
OPENSEARCH_PORT: int = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USERNAME: str = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD: str = os.getenv("OPENSEARCH_PASSWORD", "")
OPENSEARCH_USE_SSL: bool = os.getenv("OPENSEARCH_USE_SSL", "true").lower() not in ("false", "0", "no")
OPENSEARCH_VERIFY_CERTS: bool = os.getenv("OPENSEARCH_VERIFY_CERTS", "false").lower() not in ("false", "0", "no")

# Box RAG specific OpenSearch index names
BOX_DOCUMENTS_INDEX: str = os.getenv("BOX_DOCUMENTS_INDEX", "box_documents")
BOX_CHUNKS_INDEX: str = os.getenv("BOX_CHUNKS_INDEX", "box_chunks")

# ── Box ─────────────────────────────────────────────────────────────────────
BOX_CLIENT_ID: str = os.getenv("BOX_CLIENT_ID", "")
BOX_CLIENT_SECRET: str = os.getenv("BOX_CLIENT_SECRET", "")
BOX_ENTERPRISE_ID: str = os.getenv("BOX_ENTERPRISE_ID", "")

# JWT auth (production)
BOX_JWT_PRIVATE_KEY: str = os.getenv("BOX_JWT_PRIVATE_KEY", "")
BOX_JWT_PRIVATE_KEY_PASSPHRASE: str = os.getenv("BOX_JWT_PRIVATE_KEY_PASSPHRASE", "")
BOX_JWT_PUBLIC_KEY_ID: str = os.getenv("BOX_JWT_PUBLIC_KEY_ID", "")

# Box auth mode: "jwt" | "ccg" | "none" (anonymous for public shared links)
BOX_AUTH_MODE: str = os.getenv("BOX_AUTH_MODE", "none")

# ── Docling ─────────────────────────────────────────────────────────────────
# If set, calls Docling serve API; otherwise uses docling Python library
DOCLING_SERVE_URL: str = os.getenv("DOCLING_SERVE_URL", "")

# ── Chunking ────────────────────────────────────────────────────────────────
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "64"))

# ── Application ─────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
BOX_RAG_PORT: int = int(os.getenv("BOX_RAG_PORT", "8100"))

# ── RAG ─────────────────────────────────────────────────────────────────────
RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
RAG_MAX_TOKENS: int = int(os.getenv("RAG_MAX_TOKENS", "1024"))

def get_ssl_verify():
    """Return SSL verification value for requests/httpx."""
    if WATSONX_SSL_VERIFY:
        if WATSONX_CA_BUNDLE_PATH:
            return WATSONX_CA_BUNDLE_PATH
        return True
    return False
