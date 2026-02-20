#!/usr/bin/env bash
# ── Box RAG setup helper ─────────────────────────────────────────────────────
# Run from the project root: bash box-rag/setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Box RAG セットアップ ==="
echo ""

# ── Step 1: .env の準備 ───────────────────────────────────────────────────────
ENV_FILE="${SCRIPT_DIR}/.env"
CREDS_EXAMPLE="${PROJECT_ROOT}/.creds_example"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"

if [[ -f "${ENV_FILE}" ]]; then
  echo "[OK] box-rag/.env が既に存在します"
else
  echo "[INFO] box-rag/.env を作成します..."

  if [[ -f "${CREDS_EXAMPLE}" ]]; then
    echo "  .creds_example から watsonx.ai 設定をコピーします"
    cp "${CREDS_EXAMPLE}" "${ENV_FILE}"
    # Append Box RAG specific defaults from .env.example (skip duplicates)
    grep -v "^#\|^$\|WATSONX_\|SPEECH_\|TEXT_TO_SPEECH\|NODE_ENV\|LOG_LEVEL\|.*_PORT\|OPENSEARCH_\|LANGFLOW_\|DISABLE_\|FRONTEND_\|BACKEND_\|NGINX_" \
      "${ENV_EXAMPLE}" >> "${ENV_FILE}" 2>/dev/null || true
    echo "  [OK] .env を作成しました (.creds_example ベース)"
  else
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    echo "  [OK] .env.example から .env を作成しました"
    echo "  [!] 必要な値を入力してください: ${ENV_FILE}"
  fi
fi

echo ""

# ── Step 2: OpenRAG ネットワーク確認 ─────────────────────────────────────────
NETWORK_NAME="openrag_default"
if podman network exists "${NETWORK_NAME}" 2>/dev/null || \
   docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  echo "[OK] Docker ネットワーク '${NETWORK_NAME}' が存在します"
else
  echo "[WARN] Docker ネットワーク '${NETWORK_NAME}' が見つかりません"
  echo "  OpenRAG ベーススタックを先に起動してください:"
  echo "  podman-compose -f ${PROJECT_ROOT}/docker-compose.yml up -d"
fi

echo ""

# ── Step 3: ビルドと起動 ──────────────────────────────────────────────────────
echo "Box RAG サービスをビルド・起動しますか？ [y/N]"
read -r CONFIRM
if [[ "${CONFIRM}" =~ ^[Yy]$ ]]; then
  COMPOSE_CMD="docker compose"
  if command -v podman-compose &>/dev/null; then
    COMPOSE_CMD="podman-compose"
  elif command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
  fi

  cd "${PROJECT_ROOT}"
  ${COMPOSE_CMD} \
    -f docker-compose.yml \
    -f box-rag/docker-compose.box-rag.yml \
    up -d --build box-rag-backend

  echo ""
  echo "[OK] Box RAG バックエンドを起動しました"
  echo ""
  echo "  Web UI:  http://localhost:8100/"
  echo "  API Doc: http://localhost:8100/docs"
  echo "  Health:  http://localhost:8100/health"
else
  echo ""
  echo "手動で起動するには:"
  echo ""
  echo "  # Podman の場合"
  echo "  podman-compose \\"
  echo "    -f docker-compose.yml \\"
  echo "    -f box-rag/docker-compose.box-rag.yml \\"
  echo "    up -d --build box-rag-backend"
  echo ""
  echo "  # Docker の場合"
  echo "  docker compose \\"
  echo "    -f docker-compose.yml \\"
  echo "    -f box-rag/docker-compose.box-rag.yml \\"
  echo "    up -d --build box-rag-backend"
fi

echo ""
echo "=== セットアップ完了 ==="
