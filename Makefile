# OpenRAG 開発用 Makefile
# 開発ワークフロー用コマンドを提供する

# .env が存在する場合に変数を読み込み、`make` コマンドで利用できるようにする
# python-dotenv のように引用符を処理しないツールとの問題を避けるため、値から引用符を除去する
ifneq (,$(wildcard .env))
  include .env
  export $(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env)
  # すべてのエクスポート変数からシングルクォートを除去する
  $(foreach var,$(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env),$(eval $(var):=$(shell echo $($(var)) | sed "s/^'//;s/'$$//")))
endif

hostname ?= 0.0.0.0

# dev-branch ビルドのデフォルト値（コマンドラインから上書き可能）
# 使用方法: make dev-branch BRANCH=test-openai-responses REPO=https://github.com/myorg/langflow.git
BRANCH ?= main
REPO ?= https://github.com/langflow-ai/langflow.git

# コンテナランタイムの自動検出: docker を優先し、なければ podman にフォールバックする
CONTAINER_RUNTIME := $(shell command -v docker >/dev/null 2>&1 && echo "docker" || echo "podman")
COMPOSE_CMD := $(CONTAINER_RUNTIME) compose
EXTRA_HOSTS_OPT := -f docker-compose.extra-hosts.yaml

######################
# カラー定義
######################
RED=\033[0;31m
PURPLE=\033[38;2;119;62;255m
YELLOW=\033[1;33m
CYAN=\033[0;36m
NC=\033[0m
GREEN=\033[0;32m

######################
# 再利用可能な関数
######################

# JWT OpenSearch テスト関数 - JWT 認証が OpenSearch に対して機能することをテストする
# 使用方法: $(call test_jwt_opensearch)
define test_jwt_opensearch
	echo "$(CYAN)=== JWT OpenSearch Authentication Test ===$(NC)"; \
	echo "$(YELLOW)Generating test JWT token...$(NC)"; \
	TEST_TOKEN=$$(uv run python -c 'from utils.logging_config import configure_logging; configure_logging(log_level="CRITICAL"); \
	    from src.session_manager import SessionManager, AnonymousUser; \
	    sm = SessionManager("test"); \
	    print(sm.create_jwt_token(AnonymousUser()))' 2>/dev/null); \
	if [ -z "$$TEST_TOKEN" ]; then \
	    echo "$(RED)Failed to generate JWT token$(NC)"; \
	    exit 1; \
	fi; \
	echo "$(YELLOW)Testing JWT against OpenSearch...$(NC)"; \
	RESPONSE_FILE=$$(mktemp /tmp/jwt-os-diag.XXXXXX); \
	curl --fail-with-body -k -s \
	    -o "$$RESPONSE_FILE" \
	    -H "Authorization: Bearer $$TEST_TOKEN" \
	    -H "Content-Type: application/json" \
	    https://localhost:9200/documents/_search \
	    -d '{"query":{"match_all":{}}}' \
	    || { echo "$(RED)curl command failed (network error or HTTP 4xx/5xx)$(NC)"; cat "$$RESPONSE_FILE" 2>/dev/null | head -c 400; rm -f "$$RESPONSE_FILE"; exit 1; }; \
	echo "$(GREEN)Success - OpenSearch accepted JWT$(NC)"; \
	echo "Response preview:"; \
	head -c 200 "$$RESPONSE_FILE" | sed 's/^/  /' || true; \
	rm -f "$$RESPONSE_FILE"; \
	echo "";
endef

######################
# 仮想ターゲット
######################
.PHONY: help check_tools help_docker help_dev help_test help_local help_utils \
       dev dev-cpu dev-local dev-local-cpu dev-mac dev-local-mac stop clean build logs \
       shell-backend shell-frontend install \
       test test-integration test-ci test-ci-local test-sdk test-os-jwt lint \
       backend frontend docling docling-stop install-be install-fe build-be build-fe build-os build-lf logs-be logs-fe logs-lf logs-os \
       shell-be shell-lf shell-os restart status health db-reset clear-os-data flow-upload setup factory-reset \
       dev-branch build-langflow-dev stop-dev clean-dev logs-dev logs-lf-dev shell-lf-dev restart-dev status-dev

all: help

######################
# ユーティリティ
######################

check_tools: ## 必要なツールが正しいバージョンでインストールされていることを確認する
	@echo "$(YELLOW)Checking required tools...$(NC)"
	@echo ""
	@# Python の確認
	@command -v python3 >/dev/null 2>&1 || { echo "$(RED)✗ Python is not installed. Aborting.$(NC)"; exit 1; }
	@PYTHON_VERSION=$$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'); \
	PYTHON_MAJOR=$$(echo $$PYTHON_VERSION | cut -d. -f1); \
	PYTHON_MINOR=$$(echo $$PYTHON_VERSION | cut -d. -f2); \
	if [ "$$PYTHON_MAJOR" -lt 3 ] || ([ "$$PYTHON_MAJOR" -eq 3 ] && [ "$$PYTHON_MINOR" -lt 13 ]); then \
		echo "$(RED)✗ Python $$PYTHON_VERSION found, but 3.13+ required$(NC)"; exit 1; \
	else \
		echo "$(PURPLE)✓ Python $$PYTHON_VERSION$(NC)"; \
	fi
	@# uv の確認
	@command -v uv >/dev/null 2>&1 || { echo "$(RED)✗ uv is not installed. Install: curl -LsSf https://astral.sh/uv/install.sh | sh$(NC)"; exit 1; }
	@UV_VERSION=$$(uv --version 2>/dev/null | head -1 | awk '{print $$2}' || echo "unknown"); \
	echo "$(PURPLE)✓ uv $$UV_VERSION$(NC)"
	@# Node.js の確認
	@command -v node >/dev/null 2>&1 || { echo "$(RED)✗ Node.js is not installed. Aborting.$(NC)"; exit 1; }
	@NODE_VERSION=$$(node --version | sed 's/v//'); \
	NODE_MAJOR=$$(echo $$NODE_VERSION | cut -d. -f1); \
	if [ "$$NODE_MAJOR" -lt 18 ]; then \
		echo "$(RED)✗ Node.js $$NODE_VERSION found, but 18+ required$(NC)"; exit 1; \
	else \
		echo "$(PURPLE)✓ Node.js $$NODE_VERSION$(NC)"; \
	fi
	@# npm の確認
	@command -v npm >/dev/null 2>&1 || { echo "$(RED)✗ npm is not installed. Aborting.$(NC)"; exit 1; }
	@NPM_VERSION=$$(npm --version 2>/dev/null || echo "unknown"); \
	echo "$(PURPLE)✓ npm $$NPM_VERSION$(NC)"
	@# コンテナランタイムの確認
	@command -v $(CONTAINER_RUNTIME) >/dev/null 2>&1 || { echo "$(RED)✗ $(CONTAINER_RUNTIME) is not installed. Aborting.$(NC)"; exit 1; }
	@CONTAINER_VERSION=$$($(CONTAINER_RUNTIME) --version 2>/dev/null | head -1 || echo "unknown"); \
	echo "$(PURPLE)✓ $$CONTAINER_VERSION$(NC)"
	@# make の確認（このコマンドが実行できている場合は常に存在する）
	@MAKE_VERSION=$$(make --version 2>/dev/null | head -1 || echo "unknown"); \
	echo "$(PURPLE)✓ $$MAKE_VERSION$(NC)"
	@echo ""
	@echo "$(PURPLE)All required tools are installed and meet version requirements!$(NC)"

######################
# ヘルプシステム
######################

help: ## よく使うコマンドを含むメインヘルプを表示する
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(PURPLE)                    OPENRAG MAKEFILE COMMANDS                       $(NC)"
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''
	@echo "$(PURPLE)Quick Start:$(NC)"
	@echo "  $(PURPLE)make setup$(NC)           - Initialize project (install dependencies, create .env)"
	@echo "  $(PURPLE)make dev$(NC)             - Start full stack with GPU support"
	@echo "  $(PURPLE)make dev-cpu$(NC)         - Start full stack with CPU only"
	@echo "  $(PURPLE)make stop$(NC)            - Stop and remove all OpenRAG containers"
	@echo ''
	@echo "$(PURPLE)Common Commands:$(NC)"
	@echo "  $(PURPLE)make backend$(NC)         - Run backend locally"
	@echo "  $(PURPLE)make frontend$(NC)        - Run frontend locally"
	@echo "  $(PURPLE)make docling$(NC)         - Start docling-serve for document processing"
	@echo "  $(PURPLE)make docling-stop$(NC)    - Stop docling-serve"
	@echo "  $(PURPLE)make test$(NC)            - Run all backend tests"
	@echo "  $(PURPLE)make logs$(NC)            - Show logs from all containers"
	@echo "  $(PURPLE)make status$(NC)          - Show container status"
	@echo "  $(PURPLE)make health$(NC)          - Check health of all services"
	@echo ''
	@echo "$(PURPLE)Specialized Help Commands:$(NC)"
	@echo "  $(PURPLE)make help_dev$(NC)        - Development environment commands"
	@echo "  $(PURPLE)make help_docker$(NC)     - Docker and container commands"
	@echo "  $(PURPLE)make help_test$(NC)       - Testing commands"
	@echo "  $(PURPLE)make help_local$(NC)      - Local development commands"
	@echo "  $(PURPLE)make help_utils$(NC)      - Utility commands (logs, cleanup, etc.)"
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''

help_dev: ## 開発環境コマンドを表示する
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(PURPLE)                 DEVELOPMENT ENVIRONMENT COMMANDS                   $(NC)"
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''
	@echo "$(PURPLE)Full Stack Development:$(NC)"
	@echo "  $(PURPLE)make dev$(NC)             - Start full stack with GPU support ($(COMPOSE_CMD))"
	@echo "  $(PURPLE)make dev-cpu$(NC)         - Start full stack with CPU only"
	@echo "  $(PURPLE)make dev-mac$(NC)         - Start full stack for macOS Apple Silicon (ARM64, no GPU)"
	@echo "  $(PURPLE)make stop$(NC)            - Stop and remove all OpenRAG containers"
	@echo "  $(PURPLE)make restart$(NC)         - Restart all containers"
	@echo ''
	@echo "$(PURPLE)Infrastructure Only:$(NC)"
	@echo "  $(PURPLE)make dev-local$(NC)       - Start infrastructure only (for local backend/frontend)"
	@echo "  $(PURPLE)make dev-local-cpu$(NC)   - Start infrastructure for local backend/frontend with CPU only"
	@echo "  $(PURPLE)make dev-local-mac$(NC)   - Start infrastructure for macOS Apple Silicon (ARM64, no GPU)"
	@echo ''
	@echo "$(PURPLE)Branch Development (build Langflow from source):$(NC)"
	@echo "  $(PURPLE)make dev-branch$(NC)      - Build & run with custom Langflow branch"
	@echo "                         Usage: make dev-branch BRANCH=test-openai-responses"
	@echo "                                make dev-branch BRANCH=feature-x REPO=https://github.com/org/langflow.git"
	@echo "  $(PURPLE)make build-langflow-dev$(NC) - Build only the Langflow dev image (no cache)"
	@echo "  $(PURPLE)make stop-dev$(NC)        - Stop dev environment containers"
	@echo "  $(PURPLE)make restart-dev$(NC)     - Restart dev environment"
	@echo "  $(PURPLE)make clean-dev$(NC)       - Stop dev containers and remove volumes"
	@echo "  $(PURPLE)make logs-dev$(NC)        - Show all dev container logs"
	@echo "  $(PURPLE)make logs-lf-dev$(NC)     - Show Langflow dev logs"
	@echo "  $(PURPLE)make shell-lf-dev$(NC)    - Shell into Langflow dev container"
	@echo "  $(PURPLE)make status-dev$(NC)      - Show dev container status"
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''

help_docker: ## Docker とコンテナコマンドを表示する
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(PURPLE)                    DOCKER & CONTAINER COMMANDS                     $(NC)"
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''
	@echo "$(PURPLE)Build Images:$(NC)"
	@echo "  $(PURPLE)make build$(NC)           - Build all Docker images locally"
	@echo "  $(PURPLE)make build-os$(NC)        - Build OpenSearch Docker image only"
	@echo "  $(PURPLE)make build-be$(NC)        - Build backend Docker image only"
	@echo "  $(PURPLE)make build-fe$(NC)        - Build frontend Docker image only"
	@echo "  $(PURPLE)make build-lf$(NC)        - Build Langflow Docker image only"
	@echo ''
	@echo "$(PURPLE)Container Management:$(NC)"
	@echo "  $(PURPLE)make stop$(NC)            - Stop and remove all OpenRAG containers"
	@echo "  $(PURPLE)make restart$(NC)         - Restart all containers"
	@echo "  $(PURPLE)make clean$(NC)           - Stop containers and remove volumes"
	@echo "  $(PURPLE)make status$(NC)          - Show container status"
	@echo ''
	@echo "$(PURPLE)Shell Access:$(NC)"
	@echo "  $(PURPLE)make shell-be$(NC)        - Shell into backend container"
	@echo "  $(PURPLE)make shell-lf$(NC)        - Shell into langflow container"
	@echo "  $(PURPLE)make shell-os$(NC)        - Shell into opensearch container"
	@echo ''
	@echo "$(YELLOW)Note:$(NC) Using container runtime: $(PURPLE)$(CONTAINER_RUNTIME)$(NC)"
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''

help_test: ## テストコマンドを表示する
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(PURPLE)                       TESTING COMMANDS                             $(NC)"
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''
	@echo "$(PURPLE)Unit & Integration Tests:$(NC)"
	@echo "  $(PURPLE)make test$(NC)            - Run all backend tests"
	@echo "  $(PURPLE)make test-integration$(NC) - Run integration tests (requires infra)"
	@echo ''
	@echo "$(PURPLE)CI Tests:$(NC)"
	@echo "  $(PURPLE)make test-ci$(NC)         - Start infra, run integration + SDK tests, tear down"
	@echo "                         (uses DockerHub images)"
	@echo "  $(PURPLE)make test-ci-local$(NC)   - Same as test-ci but builds all images locally"
	@echo ''
	@echo "$(PURPLE)SDK Tests:$(NC)"
	@echo "  $(PURPLE)make test-sdk$(NC)        - Run SDK integration tests"
	@echo "                         (requires running OpenRAG at localhost:3000)"
	@echo ''
	@echo "$(PURPLE)Diagnostic Tests:$(NC)"
	@echo "  $(PURPLE)make test-os-jwt$(NC)     - Test JWT authentication against OpenSearch"
	@echo "                         (requires running OpenSearch)"
	@echo ''
	@echo "$(PURPLE)Code Quality:$(NC)"
	@echo "  $(PURPLE)make lint$(NC)            - Run linting checks"
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''

help_local: ## ローカル開発コマンドを表示する
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(PURPLE)                   LOCAL DEVELOPMENT COMMANDS                       $(NC)"
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''
	@echo "$(PURPLE)Run Services Locally:$(NC)"
	@echo "  $(PURPLE)make backend$(NC)         - Run backend locally (requires infrastructure)"
	@echo "  $(PURPLE)make frontend$(NC)        - Run frontend locally"
	@echo "  $(PURPLE)make docling$(NC)         - Start docling-serve for document processing"
	@echo "  $(PURPLE)make docling-stop$(NC)    - Stop docling-serve"
	@echo ''
	@echo "$(PURPLE)Installation:$(NC)"
	@echo "  $(PURPLE)make install$(NC)         - Install all dependencies"
	@echo "  $(PURPLE)make install-be$(NC)      - Install backend dependencies (uv)"
	@echo "  $(PURPLE)make install-fe$(NC)      - Install frontend dependencies (npm)"
	@echo "  $(PURPLE)make setup$(NC)           - Full setup (install deps + create .env)"
	@echo ''
	@echo "$(PURPLE)Typical Workflow:$(NC)"
	@echo "  1. $(CYAN)make dev-local$(NC)     - Start infrastructure"
	@echo "  2. $(CYAN)make backend$(NC)       - Run backend in one terminal"
	@echo "  3. $(CYAN)make frontend$(NC)      - Run frontend in another terminal"
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''

help_utils: ## ユーティリティコマンドを表示する
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(PURPLE)                       UTILITY COMMANDS                             $(NC)"
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''
	@echo "$(PURPLE)Logs:$(NC)"
	@echo "  $(PURPLE)make logs$(NC)            - Show logs from all containers"
	@echo "  $(PURPLE)make logs-be$(NC)         - Show backend container logs"
	@echo "  $(PURPLE)make logs-fe$(NC)         - Show frontend container logs"
	@echo "  $(PURPLE)make logs-lf$(NC)         - Show langflow container logs"
	@echo "  $(PURPLE)make logs-os$(NC)         - Show opensearch container logs"
	@echo ''
	@echo "$(PURPLE)Status & Health:$(NC)"
	@echo "  $(PURPLE)make status$(NC)          - Show container status"
	@echo "  $(PURPLE)make health$(NC)          - Check health of all services"
	@echo ''
	@echo "$(PURPLE)Database Operations:$(NC)"
	@echo "  $(PURPLE)make db-reset$(NC)        - Reset OpenSearch indices"
	@echo "  $(PURPLE)make clear-os-data$(NC)   - Clear OpenSearch data directory"
	@echo ''
	@echo "$(PURPLE)Cleanup:$(NC)"
	@echo "  $(PURPLE)make clean$(NC)           - Stop containers and remove volumes"
	@echo "  $(PURPLE)make clean-dev$(NC)       - Clean dev environment"
	@echo "  $(PURPLE)make factory-reset$(NC)   - Complete reset (stop, remove volumes, clear data)"
	@echo ''
	@echo "$(PURPLE)Flows:$(NC)"
	@echo "  $(PURPLE)make flow-upload$(NC)     - Upload flow to Langflow"
	@echo "                         Usage: make flow-upload FLOW_FILE=path/to/flow.json"
	@echo ''
	@echo "$(PURPLE)═══════════════════════════════════════════════════════════════════$(NC)"
	@echo ''

######################
# 開発環境
######################

dev: ## GPU サポートでフルスタックを起動する
	@echo "$(YELLOW)Starting OpenRAG with GPU support...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.gpu.yml $(EXTRA_HOSTS_OPT) up -d
	@echo "$(PURPLE)Services started!$(NC)"
	@echo "   $(CYAN)Backend:$(NC)    http://openrag-backend"
	@echo "   $(CYAN)Frontend:$(NC)   http://localhost:3000"
	@echo "   $(CYAN)Langflow:$(NC)   http://localhost:7860"
	@echo "   $(CYAN)OpenSearch:$(NC) https://localhost:9200"
	@echo "   $(CYAN)Dashboards:$(NC) http://localhost:5601"

dev-cpu: ## CPU のみでフルスタックを起動する
	@echo "$(YELLOW)Starting OpenRAG with CPU only...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) up -d
	@echo "$(PURPLE)Services started!$(NC)"
	@echo "   $(CYAN)Backend:$(NC)    http://openrag-backend"
	@echo "   $(CYAN)Frontend:$(NC)   http://localhost:3000"
	@echo "   $(CYAN)Langflow:$(NC)   http://localhost:7860"
	@echo "   $(CYAN)OpenSearch:$(NC) https://localhost:9200"
	@echo "   $(CYAN)Dashboards:$(NC) http://localhost:5601"

dev-local: ## ローカル開発用インフラを起動する
	@echo "$(YELLOW)Starting infrastructure only (for local development)...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.gpu.yml $(EXTRA_HOSTS_OPT) up -d opensearch openrag-backend dashboards langflow
	@echo "$(PURPLE)Infrastructure started!$(NC)"
	@echo "   $(CYAN)Backend:$(NC)    http://openrag-backend"
	@echo "   $(CYAN)Langflow:$(NC)   http://localhost:7860"
	@echo "   $(CYAN)OpenSearch:$(NC) https://localhost:9200"
	@echo "   $(CYAN)Dashboards:$(NC) http://localhost:5601"
	@echo ""
	@echo "$(YELLOW)Now run 'make backend' and 'make frontend' in separate terminals$(NC)"

dev-local-cpu: ## ローカル開発用インフラを CPU のみで起動する
	@echo "$(YELLOW)Starting infrastructure only (for local development)...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) up -d opensearch openrag-backend dashboards langflow
	@echo "$(PURPLE)Infrastructure started!$(NC)"
	@echo "   $(CYAN)Backend:$(NC)    http://openrag-backend"
	@echo "   $(CYAN)Langflow:$(NC)   http://localhost:7860"
	@echo "   $(CYAN)OpenSearch:$(NC) https://localhost:9200"
	@echo "   $(CYAN)Dashboards:$(NC) http://localhost:5601"
	@echo ""
	@echo "$(YELLOW)Now run 'make backend' and 'make frontend' in separate terminals$(NC)"

######################
# macOS（Apple Silicon / ARM64）開発
######################
# docker-compose.mac.yml を使って linux/arm64 イメージでスタック全体を起動する。
# GPU オーバーライド (docker-compose.gpu.yml) は含まない。
# 使用方法: make dev-mac
#           make dev-local-mac

MAC_COMPOSE_CMD := $(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.mac.yml $(EXTRA_HOSTS_OPT)

dev-mac: ## macOS Apple Silicon（ARM64、GPU なし）でフルスタックを起動する
	@echo "$(YELLOW)Starting OpenRAG for macOS Apple Silicon (ARM64)...$(NC)"
	$(MAC_COMPOSE_CMD) up -d
	@echo "$(PURPLE)Services started!$(NC)"
	@echo "   $(CYAN)Frontend:$(NC)   http://localhost:3000"
	@echo "   $(CYAN)Langflow:$(NC)   http://localhost:7860"
	@echo "   $(CYAN)OpenSearch:$(NC) https://localhost:9200"
	@echo "   $(CYAN)Dashboards:$(NC) http://localhost:5601"

dev-local-mac: ## macOS Apple Silicon（ARM64、GPU なし）用インフラのみを起動する
	@echo "$(YELLOW)Starting infrastructure only (macOS Apple Silicon)...$(NC)"
	$(MAC_COMPOSE_CMD) up -d opensearch openrag-backend dashboards langflow
	@echo "$(PURPLE)Infrastructure started!$(NC)"
	@echo "   $(CYAN)Backend:$(NC)    http://localhost:8000"
	@echo "   $(CYAN)Langflow:$(NC)   http://localhost:7860"
	@echo "   $(CYAN)OpenSearch:$(NC) https://localhost:9200"
	@echo "   $(CYAN)Dashboards:$(NC) http://localhost:5601"
	@echo ""
	@echo "$(YELLOW)Now run 'make backend' and 'make frontend' in separate terminals$(NC)"

######################
# ブランチ開発
######################
# 使用方法: make dev-branch BRANCH=test-openai-responses
#           make dev-branch BRANCH=feature-x REPO=https://github.com/myorg/langflow.git

dev-branch: ## カスタム Langflow ブランチでフルスタックをビルド & 起動する
	@echo "$(YELLOW)Building Langflow from branch: $(BRANCH)$(NC)"
	@echo "   $(CYAN)Repository:$(NC) $(REPO)"
	@echo ""
	@echo "$(YELLOW)This may take several minutes for the first build...$(NC)"
	GIT_BRANCH=$(BRANCH) GIT_REPO=$(REPO) $(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.gpu.yml -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) build langflow
	@echo ""
	@echo "$(YELLOW)Starting OpenRAG with custom Langflow build...$(NC)"
	GIT_BRANCH=$(BRANCH) GIT_REPO=$(REPO) $(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.gpu.yml -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) up -d
	@echo ""
	@echo "$(PURPLE)Dev environment started!$(NC)"
	@echo "   $(CYAN)Langflow ($(BRANCH)):$(NC) http://localhost:7860"
	@echo "   $(CYAN)Frontend:$(NC)              http://localhost:3000"
	@echo "   $(CYAN)OpenSearch:$(NC)            https://localhost:9200"
	@echo "   $(CYAN)Dashboards:$(NC)            http://localhost:5601"

dev-branch-cpu: ## カスタム Langflow ブランチと CPU のみモードでフルスタックをビルド & 起動する
	@echo "$(YELLOW)Building Langflow from branch: $(BRANCH)$(NC)"
	@echo "   $(CYAN)Repository:$(NC) $(REPO)"
	@echo ""
	@echo "$(YELLOW)This may take several minutes for the first build...$(NC)"
	GIT_BRANCH=$(BRANCH) GIT_REPO=$(REPO) $(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) build langflow
	@echo ""
	@echo "$(YELLOW)Starting OpenRAG (CPU only) with custom Langflow build...$(NC)"
	GIT_BRANCH=$(BRANCH) GIT_REPO=$(REPO) $(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) up -d
	@echo ""
	@echo "$(PURPLE)Dev environment started!$(NC)"
	@echo "   $(CYAN)Langflow ($(BRANCH)):$(NC) http://localhost:7860"
	@echo "   $(CYAN)Frontend:$(NC)              http://localhost:3000"
	@echo "   $(CYAN)OpenSearch:$(NC)            https://localhost:9200"
	@echo "   $(CYAN)Dashboards:$(NC)            http://localhost:5601"

build-langflow-dev: ## Langflow 開発イメージのみをビルドする（キャッシュなし）
	@echo "$(YELLOW)Building Langflow dev image from branch: $(BRANCH)$(NC)"
	@echo "   $(CYAN)Repository:$(NC) $(REPO)"
	GIT_BRANCH=$(BRANCH) GIT_REPO=$(REPO) $(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) build --no-cache langflow
	@echo "$(PURPLE)Langflow dev image built!$(NC)"

stop-dev: ## 開発環境コンテナを停止する
	@echo "$(YELLOW)Stopping dev environment containers...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) down
	@echo "$(PURPLE)Dev environment stopped.$(NC)"

restart-dev: ## 開発環境を再起動する
	@echo "$(YELLOW)Restarting dev environment with branch: $(BRANCH)$(NC)"
	$(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) down
	GIT_BRANCH=$(BRANCH) GIT_REPO=$(REPO) $(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) up -d
	@echo "$(PURPLE)Dev environment restarted!$(NC)"

clean-dev: ## 開発コンテナを停止してボリュームを削除する
	@echo "$(YELLOW)Cleaning up dev containers and volumes...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) down -v --remove-orphans
	@echo "$(PURPLE)Dev environment cleaned!$(NC)"

logs-dev: ## すべての開発コンテナのログを表示する
	@echo "$(YELLOW)Showing all dev container logs...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) logs -f

logs-lf-dev: ## Langflow 開発ログを表示する
	@echo "$(YELLOW)Showing Langflow dev logs...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) logs -f langflow

shell-lf-dev: ## Langflow 開発コンテナのシェルを開く
	@echo "$(YELLOW)Opening shell in Langflow dev container...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) exec langflow /bin/bash

status-dev: ## 開発コンテナのステータスを表示する
	@echo "$(PURPLE)Dev container status:$(NC)"
	@$(COMPOSE_CMD) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) ps 2>/dev/null || echo "$(YELLOW)No dev containers running$(NC)"

######################
# コンテナ管理
######################

stop: ## すべての OpenRAG コンテナを停止して削除する
	@echo "$(YELLOW)Stopping and removing all OpenRAG containers...$(NC)"
	@$(COMPOSE_CMD) $(OPENRAG_ENV_FILE) -f docker-compose.yml $(EXTRA_HOSTS_OPT) down --remove-orphans 2>/dev/null || true
	@$(COMPOSE_CMD) $(OPENRAG_ENV_FILE) -f docker-compose.dev.yml $(EXTRA_HOSTS_OPT) down --remove-orphans 2>/dev/null || true
	@$(CONTAINER_RUNTIME) ps -a --filter "name=openrag" --filter "name=langflow" --filter "name=opensearch" -q | xargs -r $(CONTAINER_RUNTIME) rm -f 2>/dev/null || true
	@echo "$(PURPLE)All OpenRAG containers stopped and removed.$(NC)"

restart: stop dev ## すべてのコンテナを再起動する

clean: stop ## コンテナを停止してボリュームを削除する
	@echo "$(YELLOW)Cleaning up containers and volumes...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) down -v --remove-orphans
	$(CONTAINER_RUNTIME) system prune -f
	@echo "$(PURPLE)Cleanup complete!$(NC)"

factory-reset: ## 完全リセット（停止、ボリューム削除、データ削除、イメージ削除）
	@echo "$(RED)WARNING: This will completely reset OpenRAG!$(NC)"; \
	echo "$(YELLOW)This will:$(NC)"; \
	echo "  - Stop all containers"; \
	echo "  - Remove all volumes"; \
	echo "  - Delete opensearch-data directory"; \
	echo "  - Delete config directory"; \
	echo "  - Delete JWT keys (private_key.pem, public_key.pem)"; \
	echo "  - Remove local OpenRAG images"; \
	echo ""; \
	read -p "Are you sure? Type 'yes' to continue: " confirm; \
	if [ "$$confirm" != "yes" ]; then \
		echo "$(CYAN)Factory reset cancelled.$(NC)"; \
		exit 0; \
	fi; \
	echo ""; \
	echo "$(YELLOW)Stopping all services and removing volumes...$(NC)"; \
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) down -v --remove-orphans --rmi local || true; \
	echo "$(YELLOW)Removing local data directories...$(NC)"; \
	if [ -d "opensearch-data" ]; then \
		echo "Removing opensearch-data..."; \
		uv run python scripts/clear_opensearch_data.py 2>/dev/null || \
		$(CONTAINER_RUNTIME) run --rm -v "$$(pwd)/opensearch-data:/data" alpine sh -c "rm -rf /data/*" 2>/dev/null || \
		rm -rf opensearch-data/* 2>/dev/null || true; \
		rm -rf opensearch-data 2>/dev/null || true; \
		echo "$(PURPLE)opensearch-data removed$(NC)"; \
	fi; \
	if [ -d "config" ]; then \
		echo "Removing config..."; \
		rm -rf config; \
		echo "$(PURPLE)config removed$(NC)"; \
	fi; \
	if [ -f "keys/private_key.pem" ] || [ -f "keys/public_key.pem" ]; then \
		echo "Removing JWT keys..."; \
		rm -f keys/private_key.pem keys/public_key.pem; \
		echo "$(PURPLE)JWT keys removed$(NC)"; \
	fi; \
	echo "$(YELLOW)Cleaning up system...$(NC)"; \
	$(CONTAINER_RUNTIME) system prune -f; \
	echo ""; \
	echo "$(PURPLE)Factory reset complete!$(NC)"; \
	echo "$(CYAN)Run 'make dev' or 'make dev-cpu' to start fresh.$(NC)";

######################
# ローカル開発
######################

backend: ## バックエンドをローカルで実行する
	@echo "$(YELLOW)Starting backend locally...$(NC)"
	@if [ ! -f .env ]; then echo "$(RED).env file not found. Copy .env.example to .env first$(NC)"; exit 1; fi
	uv run python src/main.py

frontend: ## フロントエンドをローカルで実行する
	@echo "$(YELLOW)Starting frontend locally...$(NC)"
	@if [ ! -d "frontend/node_modules" ]; then echo "$(YELLOW)Installing frontend dependencies first...$(NC)"; cd frontend && npm install; fi
	cd frontend && npx next dev \
		--hostname $(hostname)

docling: ## ドキュメント処理用の docling-serve を起動する
	@echo "$(YELLOW)Starting docling-serve...$(NC)"
	@uv run python scripts/docling_ctl.py start
	@echo "$(PURPLE)Docling-serve started! Use 'make docling-stop' to stop it.$(NC)"

docling-stop: ## docling-serve を停止する
	@echo "$(YELLOW)Stopping docling-serve...$(NC)"
	@uv run python scripts/docling_ctl.py stop
	@echo "$(PURPLE)Docling-serve stopped.$(NC)"

######################
# インストール
######################

install: install-be install-fe ## すべての依存関係をインストールする
	@echo "$(PURPLE)All dependencies installed!$(NC)"

install-be: ## バックエンド依存関係をインストールする
	@echo "$(YELLOW)Installing backend dependencies...$(NC)"
	uv sync
	@echo "$(PURPLE)Backend dependencies installed.$(NC)"

install-fe: ## フロントエンド依存関係をインストールする
	@echo "$(YELLOW)Installing frontend dependencies...$(NC)"
	cd frontend && npm install
	@echo "$(PURPLE)Frontend dependencies installed.$(NC)"

######################
# Docker ビルド
######################

build: build-os build-be build-fe build-lf ## すべての Docker イメージをローカルでビルドする
	@echo "$(PURPLE)All images built successfully!$(NC)"

build-os: ## OpenSearch Docker イメージをビルドする
	@echo "$(YELLOW)Building OpenSearch image...$(NC)"
	$(CONTAINER_RUNTIME) build -t langflowai/openrag-opensearch:latest -f Dockerfile .
	@echo "$(PURPLE)OpenSearch image built.$(NC)"

build-be: ## バックエンド Docker イメージをビルドする
	@echo "$(YELLOW)Building backend image...$(NC)"
	$(CONTAINER_RUNTIME) build -t langflowai/openrag-backend:latest -f Dockerfile.backend .
	@echo "$(PURPLE)Backend image built.$(NC)"

build-fe: ## フロントエンド Docker イメージをビルドする
	@echo "$(YELLOW)Building frontend image...$(NC)"
	$(CONTAINER_RUNTIME) build -t langflowai/openrag-frontend:latest -f Dockerfile.frontend .
	@echo "$(PURPLE)Frontend image built.$(NC)"

build-lf: ## Langflow Docker イメージをビルドする
	@echo "$(YELLOW)Building Langflow image...$(NC)"
	$(CONTAINER_RUNTIME) build -t langflowai/openrag-langflow:latest -f Dockerfile.langflow .
	@echo "$(PURPLE)Langflow image built.$(NC)"

######################
# ログ
######################

logs: ## すべてのコンテナのログを表示する
	@echo "$(YELLOW)Showing all container logs...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) logs -f

logs-be: ## バックエンドコンテナのログを表示する
	@echo "$(YELLOW)Showing backend logs...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) logs -f openrag-backend

logs-fe: ## フロントエンドコンテナのログを表示する
	@echo "$(YELLOW)Showing frontend logs...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) logs -f openrag-frontend

logs-lf: ## langflow コンテナのログを表示する
	@echo "$(YELLOW)Showing langflow logs...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) logs -f langflow

logs-os: ## opensearch コンテナのログを表示する
	@echo "$(YELLOW)Showing opensearch logs...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) logs -f opensearch

######################
# シェルアクセス
######################

shell-be: ## バックエンドコンテナのシェルを開く
	@echo "$(YELLOW)Opening shell in backend container...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) exec openrag-backend /bin/bash

shell-lf: ## langflow コンテナのシェルを開く
	@echo "$(YELLOW)Opening shell in langflow container...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) exec langflow /bin/bash

shell-os: ## opensearch コンテナのシェルを開く
	@echo "$(YELLOW)Opening shell in opensearch container...$(NC)"
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) exec opensearch /bin/bash

######################
# テスト
######################

test: ## すべてのバックエンドテストを実行する
	@echo "$(YELLOW)Running all backend tests...$(NC)"
	uv run pytest tests/ -v
	@echo "$(PURPLE)Tests complete.$(NC)"

test-integration: ## 統合テストを実行する（インフラが必要）
	@echo "$(YELLOW)Running integration tests (requires infrastructure)...$(NC)"
	@echo "$(CYAN)Make sure to run 'make dev-local' first!$(NC)"
	uv run pytest tests/integration/ -v

test-ci: ## インフラを起動し、統合テスト + SDK テストを実行して停止する（DockerHub イメージを使用）
	@set -e; \
	echo "$(YELLOW)Installing test dependencies...$(NC)"; \
	uv sync --group dev; \
	if [ ! -f keys/private_key.pem ]; then \
		echo "$(YELLOW)Generating RSA keys for JWT signing...$(NC)"; \
		uv run python -c "from src.main import generate_jwt_keys; generate_jwt_keys()"; \
	else \
		echo "$(CYAN)RSA keys already exist, ensuring correct permissions...$(NC)"; \
		chmod 600 keys/private_key.pem 2>/dev/null || true; \
		chmod 644 keys/public_key.pem 2>/dev/null || true; \
	fi; \
	echo "$(YELLOW)Cleaning up old containers and volumes...$(NC)"; \
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) down -v 2>/dev/null || true; \
	echo "$(YELLOW)Pulling latest images...$(NC)"; \
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) pull; \
	echo "$(YELLOW)Building OpenSearch image override...$(NC)"; \
	$(CONTAINER_RUNTIME) build --no-cache -t langflowai/openrag-opensearch:latest -f Dockerfile .; \
	echo "$(YELLOW)Starting infra (OpenSearch + Dashboards + Langflow + Backend + Frontend) with CPU containers$(NC)"; \
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) up -d opensearch dashboards langflow openrag-backend openrag-frontend; \
	echo "$(YELLOW)Starting docling-serve...$(NC)"; \
	DOCLING_ENDPOINT=$$(uv run python scripts/docling_ctl.py start --port 5001 | grep "Endpoint:" | awk '{print $$2}'); \
	echo "$(PURPLE)Docling-serve started at $$DOCLING_ENDPOINT$(NC)"; \
	echo "$(YELLOW)Waiting for backend OIDC endpoint...$(NC)"; \
	for i in $$(seq 1 60); do \
		$(CONTAINER_RUNTIME) exec openrag-backend curl -s http://localhost:8000/.well-known/openid-configuration >/dev/null 2>&1 && break || sleep 2; \
	done; \
	echo "$(YELLOW)Waiting for OpenSearch security config to be fully applied...$(NC)"; \
	for i in $$(seq 1 60); do \
		if $(CONTAINER_RUNTIME) logs os 2>&1 | grep -q "Security configuration applied successfully"; then \
			echo "$(PURPLE)Security configuration applied$(NC)"; \
			break; \
		fi; \
		sleep 2; \
	done; \
	echo "$(YELLOW)Verifying OIDC authenticator is active in OpenSearch...$(NC)"; \
	AUTHC_CONFIG=$$(curl -k -s -u admin:$${OPENSEARCH_PASSWORD} https://localhost:9200/_opendistro/_security/api/securityconfig 2>/dev/null); \
	if echo "$$AUTHC_CONFIG" | grep -q "openid_auth_domain"; then \
		echo "$(PURPLE)OIDC authenticator configured$(NC)"; \
		echo "$$AUTHC_CONFIG" | grep -A 5 "openid_auth_domain"; \
	else \
		echo "$(RED)OIDC authenticator NOT found in security config!$(NC)"; \
		echo "Security config:"; \
		echo "$$AUTHC_CONFIG" | head -50; \
		exit 1; \
	fi; \
	echo "$(YELLOW)Waiting for Langflow...$(NC)"; \
	for i in $$(seq 1 60); do \
		curl -s http://localhost:7860/ >/dev/null 2>&1 && break || sleep 2; \
	done; \
	echo "$(YELLOW)Waiting for docling-serve at $$DOCLING_ENDPOINT...$(NC)"; \
	for i in $$(seq 1 60); do \
		curl -s $${DOCLING_ENDPOINT}/health >/dev/null 2>&1 && break || sleep 2; \
	done; \
	echo "$(PURPLE)Running integration tests$(NC)"; \
	LOG_LEVEL=$${LOG_LEVEL:-DEBUG} \
	GOOGLE_OAUTH_CLIENT_ID="" \
	GOOGLE_OAUTH_CLIENT_SECRET="" \
	OPENSEARCH_HOST=localhost OPENSEARCH_PORT=9200 \
	OPENSEARCH_USERNAME=admin OPENSEARCH_PASSWORD=$${OPENSEARCH_PASSWORD} \
	DISABLE_STARTUP_INGEST=$${DISABLE_STARTUP_INGEST:-true} \
	uv run pytest tests/integration -vv -s -o log_cli=true --log-cli-level=DEBUG; \
	TEST_RESULT=$$?; \
	echo ""; \
	echo "$(YELLOW)Waiting for frontend at http://localhost:3000...$(NC)"; \
	for i in $$(seq 1 60); do \
		curl -s http://localhost:3000/ >/dev/null 2>&1 && break || sleep 2; \
	done; \
	echo "$(PURPLE)Running Python SDK integration tests$(NC)"; \
	cd sdks/python && \
	uv sync --extra dev && \
	OPENRAG_URL=http://localhost:3000 uv run pytest tests/test_integration.py -vv -s || TEST_RESULT=1; \
	cd ../..; \
	echo "$(PURPLE)Running TypeScript SDK integration tests$(NC)"; \
	cd sdks/typescript && \
	npm install && npm run build && \
	OPENRAG_URL=http://localhost:3000 npm test || TEST_RESULT=1; \
	cd ../..; \
	echo "$(CYAN)=================================$(NC)"; \
	echo ""; \
	($(call test_jwt_opensearch)) || TEST_RESULT=1; \
	echo "$(YELLOW)Tearing down infra$(NC)"; \
	uv run python scripts/docling_ctl.py stop || true; \
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) down -v 2>/dev/null || true; \
	exit $$TEST_RESULT

test-ci-local: ## test-ci と同じだが、すべてのイメージをローカルでビルドする
	@set -e; \
	echo "$(YELLOW)Installing test dependencies...$(NC)"; \
	uv sync --group dev; \
	if [ ! -f keys/private_key.pem ]; then \
		echo "$(YELLOW)Generating RSA keys for JWT signing...$(NC)"; \
		uv run python -c "from src.main import generate_jwt_keys; generate_jwt_keys()"; \
	else \
		echo "$(CYAN)RSA keys already exist, ensuring correct permissions...$(NC)"; \
		chmod 600 keys/private_key.pem 2>/dev/null || true; \
		chmod 644 keys/public_key.pem 2>/dev/null || true; \
	fi; \
	echo "$(YELLOW)Cleaning up old containers and volumes...$(NC)"; \
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) down -v 2>/dev/null || true; \
	echo "$(YELLOW)Building all images locally...$(NC)"; \
	$(CONTAINER_RUNTIME) build -t langflowai/openrag-opensearch:latest -f Dockerfile .; \
	$(CONTAINER_RUNTIME) build -t langflowai/openrag-backend:latest -f Dockerfile.backend .; \
	$(CONTAINER_RUNTIME) build -t langflowai/openrag-frontend:latest -f Dockerfile.frontend .; \
	$(CONTAINER_RUNTIME) build -t langflowai/openrag-langflow:latest -f Dockerfile.langflow .; \
	echo "$(YELLOW)Starting infra (OpenSearch + Dashboards + Langflow + Backend + Frontend) with CPU containers$(NC)"; \
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) up -d opensearch dashboards langflow openrag-backend openrag-frontend; \
	echo "$(YELLOW)Starting docling-serve...$(NC)"; \
	DOCLING_ENDPOINT=$$(uv run python scripts/docling_ctl.py start --port 5001 | grep "Endpoint:" | awk '{print $$2}'); \
	echo "$(PURPLE)Docling-serve started at $$DOCLING_ENDPOINT$(NC)"; \
	echo "$(YELLOW)Waiting for backend OIDC endpoint...$(NC)"; \
	for i in $$(seq 1 60); do \
		$(CONTAINER_RUNTIME) exec openrag-backend curl -s http://localhost:8000/.well-known/openid-configuration >/dev/null 2>&1 && break || sleep 2; \
	done; \
	echo "$(YELLOW)Waiting for OpenSearch security config to be fully applied...$(NC)"; \
	for i in $$(seq 1 60); do \
		if $(CONTAINER_RUNTIME) logs os 2>&1 | grep -q "Security configuration applied successfully"; then \
			echo "$(PURPLE)Security configuration applied$(NC)"; \
			break; \
		fi; \
		sleep 2; \
	done; \
	echo "$(YELLOW)Verifying OIDC authenticator is active in OpenSearch...$(NC)"; \
	AUTHC_CONFIG=$$(curl -k -s -u admin:$${OPENSEARCH_PASSWORD} https://localhost:9200/_opendistro/_security/api/securityconfig 2>/dev/null); \
	if echo "$$AUTHC_CONFIG" | grep -q "openid_auth_domain"; then \
		echo "$(PURPLE)OIDC authenticator configured$(NC)"; \
		echo "$$AUTHC_CONFIG" | grep -A 5 "openid_auth_domain"; \
	else \
		echo "$(RED)OIDC authenticator NOT found in security config!$(NC)"; \
		echo "Security config:"; \
		echo "$$AUTHC_CONFIG" | head -50; \
		exit 1; \
	fi; \
	echo "$(YELLOW)Waiting for Langflow...$(NC)"; \
	for i in $$(seq 1 60); do \
		curl -s http://localhost:7860/ >/dev/null 2>&1 && break || sleep 2; \
	done; \
	echo "$(YELLOW)Waiting for docling-serve at $$DOCLING_ENDPOINT...$(NC)"; \
	for i in $$(seq 1 60); do \
		curl -s $${DOCLING_ENDPOINT}/health >/dev/null 2>&1 && break || sleep 2; \
	done; \
	echo "$(PURPLE)Running integration tests$(NC)"; \
	LOG_LEVEL=$${LOG_LEVEL:-DEBUG} \
	GOOGLE_OAUTH_CLIENT_ID="" \
	GOOGLE_OAUTH_CLIENT_SECRET="" \
	OPENSEARCH_HOST=localhost OPENSEARCH_PORT=9200 \
	OPENSEARCH_USERNAME=admin OPENSEARCH_PASSWORD=$${OPENSEARCH_PASSWORD} \
	DISABLE_STARTUP_INGEST=$${DISABLE_STARTUP_INGEST:-true} \
	uv run pytest tests/integration -vv -s -o log_cli=true --log-cli-level=DEBUG; \
	TEST_RESULT=$$?; \
	echo ""; \
	echo "$(YELLOW)Waiting for frontend at http://localhost:3000...$(NC)"; \
	for i in $$(seq 1 60); do \
		curl -s http://localhost:3000/ >/dev/null 2>&1 && break || sleep 2; \
	done; \
	echo "$(PURPLE)Running Python SDK integration tests$(NC)"; \
	cd sdks/python && \
	uv sync --extra dev && \
	OPENRAG_URL=http://localhost:3000 uv run pytest tests/test_integration.py -vv -s || TEST_RESULT=1; \
	cd ../..; \
	echo "$(PURPLE)Running TypeScript SDK integration tests$(NC)"; \
	cd sdks/typescript && \
	npm install && npm run build && \
	OPENRAG_URL=http://localhost:3000 npm test || TEST_RESULT=1; \
	cd ../..; \
	echo "$(CYAN)=================================$(NC)"; \
	echo ""; \
	if [ $$TEST_RESULT -ne 0 ]; then \
		echo "$(RED)=== Tests failed, dumping container logs ===$(NC)"; \
		echo ""; \
		echo "$(YELLOW)=== Langflow logs (last 500 lines) ===$(NC)"; \
		$(CONTAINER_RUNTIME) logs langflow 2>&1 | tail -500 || echo "$(RED)Could not get Langflow logs$(NC)"; \
		echo ""; \
		echo "$(YELLOW)=== Backend logs (last 200 lines) ===$(NC)"; \
		$(CONTAINER_RUNTIME) logs openrag-backend 2>&1 | tail -200 || echo "$(RED)Could not get backend logs$(NC)"; \
		echo ""; \
	fi; \
	($(call test_jwt_opensearch)) || TEST_RESULT=1; \
	echo "$(YELLOW)Tearing down infra$(NC)"; \
	uv run python scripts/docling_ctl.py stop || true; \
	$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) down -v 2>/dev/null || true; \
	exit $$TEST_RESULT

test-os-jwt: ## OpenSearch に対して JWT 認証をテストする
	@$(call test_jwt_opensearch)

test-sdk: ## SDK 統合テストを実行する（localhost:3000 で OpenRAG が実行中であることが必要）
	@echo "$(YELLOW)Running SDK integration tests...$(NC)"
	@echo "$(CYAN)Make sure OpenRAG is running at localhost:3000 (make dev)$(NC)"
	@echo ""
	@echo "$(PURPLE)Running Python SDK tests...$(NC)"
	cd sdks/python && uv sync --extra dev && OPENRAG_URL=http://localhost:3000 uv run pytest tests/test_integration.py -vv -s
	@echo ""
	@echo "$(PURPLE)Running TypeScript SDK tests...$(NC)"
	cd sdks/typescript && npm install && npm run build && OPENRAG_URL=http://localhost:3000 npm test
	@echo "$(PURPLE)SDK tests complete.$(NC)"

lint: ## リンティングチェックを実行する
	@echo "$(YELLOW)Running linting checks...$(NC)"
	cd frontend && npm run lint
	@echo "$(PURPLE)Frontend linting complete.$(NC)"

######################
# ステータス & ヘルス
######################

status: ## コンテナのステータスを表示する
	@echo "$(PURPLE)Container status:$(NC)"
	@$(COMPOSE_CMD) -f docker-compose.yml $(EXTRA_HOSTS_OPT) ps 2>/dev/null || echo "$(YELLOW)No containers running$(NC)"

health: ## すべてのサービスのヘルスチェックを行う
	@echo "$(PURPLE)Health check:$(NC)"
	@echo "$(CYAN)Backend:$(NC)    $$(curl -s http://localhost:8000/health 2>/dev/null || echo '$(RED)Not responding$(NC)')"
	@echo "$(CYAN)Langflow:$(NC)   $$(curl -s http://localhost:7860/health 2>/dev/null || echo '$(RED)Not responding$(NC)')"
	@echo "$(CYAN)OpenSearch:$(NC) $$(curl -s -k -u admin:$${OPENSEARCH_PASSWORD} https://localhost:9200 2>/dev/null | jq -r .tagline 2>/dev/null || echo '$(RED)Not responding$(NC)')"

######################
# データベース操作
######################

db-reset: ## OpenSearch インデックスをリセットする
	@echo "$(YELLOW)Resetting OpenSearch indices...$(NC)"
	curl -k -X DELETE "https://localhost:9200/documents" -u admin:$${OPENSEARCH_PASSWORD} || true
	curl -k -X DELETE "https://localhost:9200/knowledge_filters" -u admin:$${OPENSEARCH_PASSWORD} || true
	@echo "$(PURPLE)Indices reset. Restart backend to recreate.$(NC)"

clear-os-data: ## OpenSearch データディレクトリをクリアする
	@echo "$(YELLOW)Clearing OpenSearch data directory...$(NC)"
	@uv run python scripts/clear_opensearch_data.py
	@echo "$(PURPLE)OpenSearch data cleared.$(NC)"

######################
# フロー管理
######################

flow-upload: ## Langflow にフローをアップロードする
	@echo "$(YELLOW)Uploading flow to Langflow...$(NC)"
	@if [ -z "$(FLOW_FILE)" ]; then echo "$(RED)Usage: make flow-upload FLOW_FILE=path/to/flow.json$(NC)"; exit 1; fi
	curl -X POST "http://localhost:7860/api/v1/flows" \
		-H "Content-Type: application/json" \
		-d @$(FLOW_FILE)
	@echo "$(PURPLE)Flow uploaded.$(NC)"

######################
# セットアップ
######################

setup: check_tools ## 開発環境をセットアップする
	@echo "$(YELLOW)Setting up development environment...$(NC)"
	@if [ ! -f .env ]; then cp .env.example .env && echo "$(PURPLE)Created .env from template$(NC)"; fi
	@$(MAKE) install
	@echo "$(PURPLE)Setup complete! Run 'make dev' to start.$(NC)"
