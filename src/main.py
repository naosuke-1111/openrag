

# 構造化ログを早期に設定する
from connectors.langflow_connector_service import LangflowConnectorService
from connectors.service import ConnectorService
from services.flows_service import FlowsService
from utils.container_utils import detect_container_environment
from utils.embeddings import create_dynamic_index_body
from utils.logging_config import configure_from_env, get_logger
from utils.telemetry import TelemetryClient, Category, MessageId

configure_from_env()
logger = get_logger(__name__)

import asyncio
import atexit
import mimetypes
import multiprocessing
import os
import shutil
import subprocess
from functools import partial

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

# CUDA との互換性を確保するためマルチプロセス起動方式を 'spawn' に設定する
multiprocessing.set_start_method("spawn", force=True)

# torch/CUDA インポートより前にプロセスプールを作成する
from utils.process_pool import process_pool  # isort: skip
import torch

# API エンドポイント
from api import (
    auth,
    chat,
    connectors,
    docling,
    documents,
    flows,
    knowledge_filter,
    langflow_files,
    models,
    nudges,
    oidc,
    provider_health,
    router,
    search,
    settings,
    tasks,
    upload,
)

# 既存のサービス
from api.connector_router import ConnectorRouter
from auth_middleware import optional_auth, require_auth

# API キー認証
from api_key_middleware import require_api_key
from services.api_key_service import APIKeyService
from api import keys as api_keys
from api.v1 import chat as v1_chat, search as v1_search, documents as v1_documents, settings as v1_settings, models as v1_models, knowledge_filters as v1_knowledge_filters
from api.watson_news import routes as watson_news_routes

# 設定とセットアップ
from config.settings import (
    API_KEYS_INDEX_BODY,
    API_KEYS_INDEX_NAME,
    DISABLE_INGEST_WITH_LANGFLOW,
    INGESTION_TIMEOUT,
    INDEX_BODY,
    SESSION_SECRET,
    clients,
    get_embedding_model,
    get_index_name,
    is_no_auth_mode,
    is_dev_mode,
    get_openrag_config,
)
from services.auth_service import AuthService
from services.langflow_mcp_service import LangflowMCPService
from services.chat_service import ChatService

# サービス
from services.document_service import DocumentService
from services.knowledge_filter_service import KnowledgeFilterService

# サービス
from services.langflow_file_service import LangflowFileService
from services.models_service import ModelsService
from services.monitor_service import MonitorService
from services.search_service import SearchService
from services.task_service import TaskService
from session_manager import SessionManager

logger.info(
    "CUDA デバイス情報",
    cuda_available=torch.cuda.is_available(),
    cuda_version=torch.version.cuda,
)

# 起動時の取り込み対象から除外するファイル名
EXCLUDED_INGESTION_FILES = {"warmup_ocr.pdf"}


async def wait_for_opensearch():
    """OpenSearch が準備完了になるまでリトライしながら待機する。"""
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            await clients.opensearch.ping()
            logger.info("OpenSearch の準備が完了しました")
            await TelemetryClient.send_event(Category.OPENSEARCH_SETUP, MessageId.ORB_OS_CONN_ESTABLISHED)
            return
        except Exception as e:
            logger.warning(
                "OpenSearch がまだ準備できていません",
                attempt=attempt + 1,
                max_retries=max_retries,
                error=str(e),
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                await TelemetryClient.send_event(Category.OPENSEARCH_SETUP, MessageId.ORB_OS_TIMEOUT)
                raise Exception("OpenSearch の準備完了がタイムアウトしました")


async def configure_alerting_security():
    """OpenSearch アラートプラグインのセキュリティ設定を行う。"""
    try:
        # テスト向けに、全認証ユーザーを許可するためバックエンドロールフィルタリングを無効化する
        # 本番環境では適切なロール設定を行うことを推奨する
        alerting_settings = {
            "persistent": {
                "plugins.alerting.filter_by_backend_roles": "false",
                "opendistro.alerting.filter_by_backend_roles": "false",
                "opensearch.notifications.general.filter_by_backend_roles": "false",
            }
        }

        # 管理者クライアントを使用する（clients.opensearch は管理者資格情報を使用）
        response = await clients.opensearch.cluster.put_settings(body=alerting_settings)
        logger.info(
            "アラートセキュリティ設定を正常に構成しました", response=response
        )
    except Exception as e:
        logger.warning("アラートセキュリティ設定の構成に失敗しました", error=str(e))
        # アラート設定が失敗してもサーバー起動を妨げない


async def _ensure_opensearch_index():
    """従来のコネクターサービス使用時に OpenSearch インデックスが存在することを確認する。"""
    try:
        index_name = get_index_name()
        # インデックスが既に存在するか確認する
        if await clients.opensearch.indices.exists(index=index_name):
            logger.debug("OpenSearch インデックスは既に存在します", index_name=index_name)
            return

        # ハードコードされた INDEX_BODY でインデックスを作成する（OpenAI エンベディング次元数を使用）
        await clients.opensearch.indices.create(index=index_name, body=INDEX_BODY)
        logger.info(
            "従来のコネクターサービス用 OpenSearch インデックスを作成しました",
            index_name=index_name,
            vector_dimensions=INDEX_BODY["mappings"]["properties"]["chunk_embedding"][
                "dimension"
            ],
        )
        await TelemetryClient.send_event(Category.OPENSEARCH_INDEX, MessageId.ORB_OS_INDEX_CREATED)

    except Exception as e:
        logger.error(
            "従来のコネクターサービス用 OpenSearch インデックスの初期化に失敗しました",
            error=str(e),
            index_name=get_index_name(),
        )
        await TelemetryClient.send_event(Category.OPENSEARCH_INDEX, MessageId.ORB_OS_INDEX_CREATE_FAIL)
        # 初期化を妨げないよう例外を伝播させない
        # サービスは動作継続できるが、後のドキュメント操作が失敗する可能性がある


async def init_index():
    """OpenSearch インデックスとセキュリティロールを初期化する。"""
    try:
        await wait_for_opensearch()

        # ユーザー設定から設定済みのエンベディングモデルを取得する
        config = get_openrag_config()
        embedding_model = config.knowledge.embedding_model
        embedding_provider = config.knowledge.embedding_provider
        embedding_provider_config = config.get_embedding_provider_config()

        # 設定済みのエンベディングモデルに基づいて動的インデックス定義を作成する
        # Ollama プロービングによる動的次元数解決のためプロバイダーとエンドポイントを渡す
        dynamic_index_body = await create_dynamic_index_body(
            embedding_model,
            provider=embedding_provider,
            endpoint=getattr(embedding_provider_config, "endpoint", None)
        )

        # ドキュメントインデックスを作成する
        index_name = get_index_name()
        if not await clients.opensearch.indices.exists(index=index_name):
            await clients.opensearch.indices.create(
                index=index_name, body=dynamic_index_body
            )
            logger.info(
                "OpenSearch インデックスを作成しました",
                index_name=index_name,
                embedding_model=embedding_model,
            )
            await TelemetryClient.send_event(Category.OPENSEARCH_INDEX, MessageId.ORB_OS_INDEX_CREATED)
        else:
            logger.info(
                "インデックスが既に存在するため作成をスキップします",
                index_name=index_name,
                embedding_model=embedding_model,
            )
            await TelemetryClient.send_event(Category.OPENSEARCH_INDEX, MessageId.ORB_OS_INDEX_EXISTS)

        # ナレッジフィルターインデックスを作成する
        knowledge_filter_index_name = "knowledge_filters"
        knowledge_filter_index_body = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text", "analyzer": "standard"},
                    "description": {"type": "text", "analyzer": "standard"},
                    "query_data": {"type": "text"},  # 検索用にテキストとして保存する
                    "owner": {"type": "keyword"},
                    "allowed_users": {"type": "keyword"},
                    "allowed_groups": {"type": "keyword"},
                    "subscriptions": {"type": "object"},  # サブスクリプションデータを保存する
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                }
            }
        }

        if not await clients.opensearch.indices.exists(index=knowledge_filter_index_name):
            await clients.opensearch.indices.create(
                index=knowledge_filter_index_name, body=knowledge_filter_index_body
            )
            logger.info(
                "ナレッジフィルターインデックスを作成しました", index_name=knowledge_filter_index_name
            )
            await TelemetryClient.send_event(Category.OPENSEARCH_INDEX, MessageId.ORB_OS_KF_INDEX_CREATED)
        else:
            logger.info(
                "ナレッジフィルターインデックスが既に存在するため作成をスキップします",
                index_name=knowledge_filter_index_name,
            )

        # パブリック API 認証用の API キーインデックスを作成する
        if not await clients.opensearch.indices.exists(index=API_KEYS_INDEX_NAME):
            await clients.opensearch.indices.create(
                index=API_KEYS_INDEX_NAME, body=API_KEYS_INDEX_BODY
            )
            logger.info(
                "API キーインデックスを作成しました", index_name=API_KEYS_INDEX_NAME
            )
        else:
            logger.info(
                "API キーインデックスが既に存在するため作成をスキップします",
                index_name=API_KEYS_INDEX_NAME,
            )

        # アラートプラグインのセキュリティ設定を行う
        await configure_alerting_security()

    except Exception as e:
        error_msg = str(e).lower()
        if "disk usage exceeded" in error_msg or "flood-stage watermark" in error_msg:
             logger.error("OpenSearch のディスク使用量がフラッドステージウォーターマークを超えました。インデックス作成に失敗しました。")
             raise Exception(
                 "OpenSearch のディスクが満杯です（フラッドステージウォーターマーク超過）。"
                 "継続するには Docker ボリュームまたはホストマシンのディスク空き容量を確保してください。"
             ) from e
        raise e


async def init_index_when_ready():
    """OpenSearch サービスの準備完了を待ってから OpenSearch インデックスを初期化する。"""
    await wait_for_opensearch()
    await init_index()


def generate_jwt_keys():
    """JWT 署名用の RSA キーが存在しない場合に生成する。"""
    keys_dir = "keys"
    private_key_path = os.path.join(keys_dir, "private_key.pem")
    public_key_path = os.path.join(keys_dir, "public_key.pem")

    # キーディレクトリが存在しない場合は作成する
    os.makedirs(keys_dir, exist_ok=True)

    # キーが存在しない場合は生成する
    if not os.path.exists(private_key_path):
        try:
            # 秘密鍵を生成する
            subprocess.run(
                ["openssl", "genrsa", "-out", private_key_path, "2048"],
                check=True,
                capture_output=True,
            )

            # 秘密鍵のパーミッションを制限する（オーナーのみ読み取り可）
            os.chmod(private_key_path, 0o600)

            # 公開鍵を生成する
            subprocess.run(
                [
                    "openssl",
                    "rsa",
                    "-in",
                    private_key_path,
                    "-pubout",
                    "-out",
                    public_key_path,
                ],
                check=True,
                capture_output=True,
            )

            # 公開鍵のパーミッションを設定する（全員読み取り可）
            os.chmod(public_key_path, 0o644)

            logger.info("JWT 署名用の RSA キーを生成しました")
        except subprocess.CalledProcessError as e:
            logger.error("RSA キーの生成に失敗しました", error=str(e))
            TelemetryClient.send_event_sync(Category.SERVICE_INITIALIZATION, MessageId.ORB_SVC_JWT_KEY_FAIL)
            raise
    else:
        # 既存のキーに正しいパーミッションが設定されていることを確認する
        try:
            os.chmod(private_key_path, 0o600)
            os.chmod(public_key_path, 0o644)
            logger.info("RSA キーが既に存在します。正しいパーミッションを確認しました")
        except OSError as e:
            logger.warning("既存のキーへのパーミッション設定に失敗しました", error=str(e))


def _get_documents_dir():
    """Docker とローカル環境の両方に対応したドキュメントディレクトリのパスを返す。"""
    # Docker では /app/openrag-documents にボリュームがマウントされる
    # ローカル環境では openrag-documents を使用する
    container_env = detect_container_environment()
    if container_env:
        path = os.path.abspath("/app/openrag-documents")
        logger.debug(f"{container_env} で実行中です。コンテナパスを使用します: {path}")
        return path
    else:
        path = os.path.abspath(os.path.join(os.getcwd(), "openrag-documents"))
        logger.debug(f"ローカル環境で実行中です。ローカルパスを使用します: {path}")
        return path


async def ingest_default_documents_when_ready(services):
    """ローカルのドキュメントフォルダをスキャンして、認証なしアップロードと同様にファイルを取り込む。"""
    try:
        logger.info(
            "デフォルトドキュメントの取り込みを開始します",
            disable_langflow_ingest=DISABLE_INGEST_WITH_LANGFLOW,
        )
        await TelemetryClient.send_event(Category.DOCUMENT_INGESTION, MessageId.ORB_DOC_DEFAULT_START)
        base_dir = _get_documents_dir()
        if not os.path.isdir(base_dir):
            raise FileNotFoundError(f"デフォルトドキュメントディレクトリが見つかりません: {base_dir}")

        # ウォームアップファイルを除外して再帰的にファイルを収集する
        file_paths = [
            os.path.join(root, fn)
            for root, _, files in os.walk(base_dir)
            for fn in files
            if fn not in EXCLUDED_INGESTION_FILES
        ]

        if not file_paths:
            raise FileNotFoundError(f"{base_dir} にデフォルトドキュメントが見つかりません")

        if DISABLE_INGEST_WITH_LANGFLOW:
            await _ingest_default_documents_openrag(services, file_paths)
        else:
            await _ingest_default_documents_langflow(services, file_paths)

        await TelemetryClient.send_event(Category.DOCUMENT_INGESTION, MessageId.ORB_DOC_DEFAULT_COMPLETE)

    except Exception as e:
        logger.error("デフォルトドキュメントの取り込みに失敗しました", error=str(e))
        await TelemetryClient.send_event(Category.DOCUMENT_INGESTION, MessageId.ORB_DOC_DEFAULT_FAILED)
        raise


async def _ingest_default_documents_langflow(services, file_paths):
    """Langflow のアップロード→取り込み→削除パイプラインでデフォルトドキュメントを取り込む。"""
    langflow_file_service = services["langflow_file_service"]
    session_manager = services["session_manager"]
    task_service = services["task_service"]

    logger.info(
        "デフォルトドキュメントに Langflow 取り込みパイプラインを使用します",
        file_count=len(file_paths),
    )

    # デフォルトドキュメントには匿名ユーザー情報を使用する
    from session_manager import AnonymousUser

    anonymous_user = AnonymousUser()

    # DocumentFileProcessor と同じロジックで JWT トークンを取得する
    # 匿名ユーザーに必要な場合は匿名 JWT の作成も処理する
    effective_jwt = None

    # セッションマネージャーに匿名 JWT の作成を任せる
    if session_manager:
        # DocumentFileProcessor と同様に、必要に応じて匿名 JWT を作成する
        session_manager.get_user_opensearch_client(
            anonymous_user.user_id, effective_jwt
        )
        # セッションマネージャーが作成した JWT を取得する
        if hasattr(session_manager, "_anonymous_jwt"):
            effective_jwt = session_manager._anonymous_jwt

    # 匿名ユーザーメタデータでデフォルトドキュメント用のツイークを準備する
    default_tweaks = {
        "OpenSearchVectorStoreComponentMultimodalMultiEmbedding-By9U4": {
            "docs_metadata": [
                {"key": "owner", "value": None},
                {"key": "owner_name", "value": anonymous_user.name},
                {"key": "owner_email", "value": anonymous_user.email},
                {"key": "connector_type", "value": "system_default"},
                {"key": "is_sample_data", "value": "true"},
            ]
        }
    }

    # 進捗追跡可能な Langflow アップロードタスクを作成する
    task_id = await task_service.create_langflow_upload_task(
        user_id=None,  # 匿名ユーザー
        file_paths=file_paths,
        langflow_file_service=langflow_file_service,
        session_manager=session_manager,
        jwt_token=effective_jwt,
        owner_name=anonymous_user.name,
        owner_email=anonymous_user.email,
        session_id=None,  # デフォルトドキュメントにはセッションなし
        tweaks=default_tweaks,
        settings=None,  # デフォルトの取り込み設定を使用する
        delete_after_ingest=True,  # 取り込み後にクリーンアップする
        replace_duplicates=True,
    )

    logger.info(
        "デフォルトドキュメント用 Langflow 取り込みタスクを開始しました",
        task_id=task_id,
        file_count=len(file_paths),
    )

async def health_check(request):
    """シンプルな生存確認プローブ: OpenRAG バックエンドサービスが稼働中であることを示す。"""
    return JSONResponse({"status": "ok"}, status_code=200)


async def opensearch_health_ready(request):
    """準備完了プローブ: OpenSearch 依存サービスへの接続を確認する。"""
    try:
        # クラスターへの到達性と認証を高速チェックする
        await asyncio.wait_for(clients.opensearch.info(), timeout=5.0)
        return JSONResponse(
            {"status": "ready", "dependencies": {"opensearch": "up"}},
            status_code=200,
        )
    except Exception as e:
        return JSONResponse(
            {
                "status": "not_ready",
                "dependencies": {"opensearch": "down"},
                "error": str(e),
            },
            status_code=503,
        )

async def _ingest_default_documents_openrag(services, file_paths):
    """従来の OpenRAG プロセッサーでデフォルトドキュメントを取り込む。"""
    logger.info(
        "デフォルトドキュメントに従来の OpenRAG 取り込みを使用します",
        file_count=len(file_paths),
    )

    # ドキュメントに 'owner' を設定しないプロセッサーを構築する（owner_user_id=None）
    from models.processors import DocumentFileProcessor

    processor = DocumentFileProcessor(
        services["document_service"],
        owner_user_id=None,
        jwt_token=None,
        owner_name=None,
        owner_email=None,
        is_sample_data=True,  # サンプルデータとしてマークする
    )

    task_id = await services["task_service"].create_custom_task(
        "anonymous", file_paths, processor
    )
    logger.info(
        "従来の OpenRAG 取り込みタスクを開始しました",
        task_id=task_id,
        file_count=len(file_paths),
    )


async def _update_mcp_servers_with_provider_credentials(services):
    """起動時にプロバイダー資格情報で MCP サーバーを更新する。

    通常の OAuth ログインフローを経ない認証なしモードで特に重要な処理。
    """
    try:
        auth_service = services.get("auth_service")
        session_manager = services.get("session_manager")

        if not auth_service or not auth_service.langflow_mcp_service:
            logger.debug("MCP サービスが利用できません。資格情報の更新をスキップします")
            return

        config = get_openrag_config()

        # ユーティリティ関数を使ってプロバイダー資格情報からグローバル変数を構築する
        from utils.langflow_headers import build_mcp_global_vars_from_config

        global_vars = build_mcp_global_vars_from_config(config)

        # 認証なしモードでは匿名 JWT トークンとユーザー詳細を追加する
        if is_no_auth_mode() and session_manager:
            from session_manager import AnonymousUser

            # 認証なしモード用の匿名 JWT を作成または取得する
            anonymous_jwt = session_manager.get_effective_jwt_token(None, None)
            if anonymous_jwt:
                global_vars["JWT"] = anonymous_jwt

            # 匿名ユーザーの詳細を追加する
            anonymous_user = AnonymousUser()
            global_vars["OWNER"] = anonymous_user.user_id  # "anonymous"
            global_vars["OWNER_NAME"] = f'"{anonymous_user.name}"'  # "Anonymous User"（スペースのためクォート）
            global_vars["OWNER_EMAIL"] = anonymous_user.email  # "anonymous@localhost"

            logger.info("認証なしモード用に匿名 JWT とユーザー詳細を MCP サーバーに追加しました")

        if global_vars:
            result = await auth_service.langflow_mcp_service.update_mcp_servers_with_global_vars(global_vars)
            logger.info("起動時にプロバイダー資格情報で MCP サーバーを更新しました", **result)
        else:
            logger.debug("プロバイダー資格情報が設定されていません。MCP サーバーの更新をスキップします")

    except Exception as e:
        logger.warning("起動時の MCP サーバーへのプロバイダー資格情報更新に失敗しました", error=str(e))
        # MCP の更新が失敗してもサーバー起動を妨げない


async def startup_tasks(services):
    """起動時タスクを実行する。"""
    logger.info("起動時タスクを開始します")
    await TelemetryClient.send_event(Category.APPLICATION_STARTUP, MessageId.ORB_APP_START_INIT)
    # 基本的な OpenSearch 接続のみ初期化する（インデックスはまだ作成しない）
    # インデックスはエンベディングモデルが確定するオンボーディング後に作成する
    await wait_for_opensearch()

    if DISABLE_INGEST_WITH_LANGFLOW:
        await _ensure_opensearch_index()

    # オンボーディング済みの場合は OpenSearch インデックスが存在することを確認する
    # - オンボーディング後に OpenSearch がリセット（例: ボリューム削除）された場合に対応する
    embedding_model = None
    try:
        config = get_openrag_config()
        embedding_model = config.knowledge.embedding_model

        if config.edited and embedding_model:
            logger.info(
                "OpenSearch インデックスが存在することを確認中です（オンボーディング後）...",
                embedding_model=embedding_model,
            )

            await init_index()

            logger.info(
                "OpenSearch インデックスの存在確認が完了しました（オンボーディング後）",
                embedding_model=embedding_model,
            )
    except Exception as e:
        logger.error(
            "OpenSearch インデックスの存在確認に失敗しました（オンボーディング後）",
            embedding_model=embedding_model,
            error=str(e),
        )
        raise

    # アラートセキュリティを設定する
    await configure_alerting_security()

    # プロバイダー資格情報で MCP サーバーを更新する（認証なしモードで特に重要）
    await _update_mcp_servers_with_provider_credentials(services)

    # フローがリセットされているか確認し、設定が編集済みであれば再適用する
    try:
        config = get_openrag_config()
        if config.edited:
            logger.info("Langflow フローがリセットされていないか確認します")
            flows_service = services["flows_service"]
            reset_flows = await flows_service.check_flows_reset()

            if reset_flows:
                logger.info(
                    f"リセットされたフローを検出しました: {', '.join(reset_flows)}。全設定を再適用します。"
                )
                await TelemetryClient.send_event(Category.FLOW_OPERATIONS, MessageId.ORB_FLOW_RESET_DETECTED)
                from api.settings import reapply_all_settings
                await reapply_all_settings(session_manager=services["session_manager"])
                logger.info("フローリセット検出後の設定再適用が完了しました")
                await TelemetryClient.send_event(Category.FLOW_OPERATIONS, MessageId.ORB_FLOW_SETTINGS_REAPPLIED)
            else:
                logger.info("リセットされたフローは検出されませんでした。設定の再適用をスキップします")
        else:
            logger.debug("設定がまだ編集されていません。フローリセット確認をスキップします")
    except Exception as e:
        logger.error(f"フローリセット確認または設定再適用に失敗しました: {str(e)}")
        await TelemetryClient.send_event(Category.FLOW_OPERATIONS, MessageId.ORB_FLOW_RESET_CHECK_FAIL)
        # この確認が失敗してもサーバー起動を妨げない

    # Watson News OpenSearch インデックスを初期化する（ノンブロッキング）
    try:
        from services.watson_news_service import ensure_indices
        await ensure_indices()
        logger.info("Watson News OpenSearch インデックスを確認しました")
    except Exception as exc:
        logger.warning("Watson News インデックスの初期化に失敗しました（致命的ではありません）", error=str(exc))


async def initialize_services():
    """全サービスとその依存関係を初期化する。"""
    await TelemetryClient.send_event(Category.SERVICE_INITIALIZATION, MessageId.ORB_SVC_INIT_START)
    # JWT キーが存在しない場合は生成する
    generate_jwt_keys()

    # クライアントを初期化する（Langflow API キー生成のため非同期）
    try:
        await clients.initialize()
    except Exception as e:
        logger.error("クライアントの初期化に失敗しました", error=str(e))
        await TelemetryClient.send_event(Category.SERVICE_INITIALIZATION, MessageId.ORB_SVC_OS_CLIENT_FAIL)
        raise

    # セッションマネージャーを初期化する
    session_manager = SessionManager(SESSION_SECRET)

    # 各サービスを初期化する
    document_service = DocumentService(session_manager=session_manager)
    search_service = SearchService(session_manager)
    task_service = TaskService(document_service, process_pool, ingestion_timeout=INGESTION_TIMEOUT)
    chat_service = ChatService()
    flows_service = FlowsService()
    knowledge_filter_service = KnowledgeFilterService(session_manager)
    models_service = ModelsService()
    monitor_service = MonitorService(session_manager)

    # ドキュメントサービスにプロセスプールを設定する
    document_service.process_pool = process_pool

    # コネクターサービスを初期化する

    # Langflow 用と OpenRAG 用の両コネクターサービスを初期化する
    langflow_connector_service = LangflowConnectorService(
        task_service=task_service,
        session_manager=session_manager,
    )
    openrag_connector_service = ConnectorService(
        patched_async_client=clients,  # クライアントオブジェクト自体を渡す
        process_pool=process_pool,
        embed_model=get_embedding_model(),
        index_name=get_index_name(),
        task_service=task_service,
        session_manager=session_manager,
    )

    # 設定に基づいてどちらかを選択するコネクタールーターを作成する
    connector_service = ConnectorRouter(
        langflow_connector_service=langflow_connector_service,
        openrag_connector_service=openrag_connector_service,
    )

    # 認証サービスを初期化する
    auth_service = AuthService(
        session_manager,
        connector_service,
        langflow_mcp_service=LangflowMCPService(),
    )

    # 起動時に永続化されたコネクター接続を読み込む
    # Webhook とSync がサーバー起動直後に既存サブスクリプションを解決できるようにする
    # コネクターは OAuth が必要なため、認証なしモードではスキップする

    if not is_no_auth_mode():
        try:
            await connector_service.initialize()
            loaded_count = len(connector_service.connection_manager.connections)
            logger.info(
                "起動時に永続化されたコネクター接続を読み込みました",
                loaded_count=loaded_count,
            )
        except Exception as e:
            logger.warning(
                "起動時の永続化接続の読み込みに失敗しました", error=str(e)
            )
            await TelemetryClient.send_event(Category.CONNECTOR_OPERATIONS, MessageId.ORB_CONN_LOAD_FAILED)
    else:
        logger.info("[コネクター] 認証なしモードのため接続読み込みをスキップします")

    await TelemetryClient.send_event(Category.SERVICE_INITIALIZATION, MessageId.ORB_SVC_INIT_SUCCESS)

    langflow_file_service = LangflowFileService()

    # パブリック API 認証用の API キーサービス
    api_key_service = APIKeyService(session_manager)

    return {
        "document_service": document_service,
        "search_service": search_service,
        "task_service": task_service,
        "chat_service": chat_service,
        "flows_service": flows_service,
        "langflow_file_service": langflow_file_service,
        "auth_service": auth_service,
        "connector_service": connector_service,
        "knowledge_filter_service": knowledge_filter_service,
        "models_service": models_service,
        "monitor_service": monitor_service,
        "session_manager": session_manager,
        "api_key_service": api_key_service,
    }


async def create_app():
    """Starlette アプリケーションを作成して設定する。"""
    services = await initialize_services()

    # サービス依存関係を注入したルートハンドラーを作成する
    routes = [
        # Langflow ファイルエンドポイント
        Route(
            "/langflow/files/upload",
            optional_auth(services["session_manager"])(
                partial(
                    langflow_files.upload_user_file,
                    langflow_file_service=services["langflow_file_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/langflow/ingest",
            require_auth(services["session_manager"])(
                partial(
                    langflow_files.run_ingestion,
                    langflow_file_service=services["langflow_file_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/langflow/files",
            require_auth(services["session_manager"])(
                partial(
                    langflow_files.delete_user_files,
                    langflow_file_service=services["langflow_file_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["DELETE"],
        ),
        Route(
            "/langflow/upload_ingest",
            require_auth(services["session_manager"])(
                partial(
                    langflow_files.upload_and_ingest_user_file,
                    langflow_file_service=services["langflow_file_service"],
                    session_manager=services["session_manager"],
                    task_service=services["task_service"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/upload_context",
            require_auth(services["session_manager"])(
                partial(
                    upload.upload_context,
                    document_service=services["document_service"],
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/upload_path",
            require_auth(services["session_manager"])(
                partial(
                    upload.upload_path,
                    task_service=services["task_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/upload_options",
            require_auth(services["session_manager"])(
                partial(
                    upload.upload_options, session_manager=services["session_manager"]
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/upload_bucket",
            require_auth(services["session_manager"])(
                partial(
                    upload.upload_bucket,
                    task_service=services["task_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/tasks/{task_id}",
            require_auth(services["session_manager"])(
                partial(
                    tasks.task_status,
                    task_service=services["task_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/tasks",
            require_auth(services["session_manager"])(
                partial(
                    tasks.all_tasks,
                    task_service=services["task_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/tasks/{task_id}/cancel",
            require_auth(services["session_manager"])(
                partial(
                    tasks.cancel_task,
                    task_service=services["task_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        # 検索エンドポイント
        Route(
            "/search",
            require_auth(services["session_manager"])(
                partial(
                    search.search,
                    search_service=services["search_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        # ナレッジフィルターエンドポイント
        Route(
            "/knowledge-filter",
            require_auth(services["session_manager"])(
                partial(
                    knowledge_filter.create_knowledge_filter,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/knowledge-filter/search",
            require_auth(services["session_manager"])(
                partial(
                    knowledge_filter.search_knowledge_filters,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/knowledge-filter/{filter_id}",
            require_auth(services["session_manager"])(
                partial(
                    knowledge_filter.get_knowledge_filter,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/knowledge-filter/{filter_id}",
            require_auth(services["session_manager"])(
                partial(
                    knowledge_filter.update_knowledge_filter,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["PUT"],
        ),
        Route(
            "/knowledge-filter/{filter_id}",
            require_auth(services["session_manager"])(
                partial(
                    knowledge_filter.delete_knowledge_filter,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["DELETE"],
        ),
        # ナレッジフィルターサブスクリプションエンドポイント
        Route(
            "/knowledge-filter/{filter_id}/subscribe",
            require_auth(services["session_manager"])(
                partial(
                    knowledge_filter.subscribe_to_knowledge_filter,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    monitor_service=services["monitor_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/knowledge-filter/{filter_id}/subscriptions",
            require_auth(services["session_manager"])(
                partial(
                    knowledge_filter.list_knowledge_filter_subscriptions,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/knowledge-filter/{filter_id}/subscribe/{subscription_id}",
            require_auth(services["session_manager"])(
                partial(
                    knowledge_filter.cancel_knowledge_filter_subscription,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    monitor_service=services["monitor_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["DELETE"],
        ),
        # ナレッジフィルター Webhook エンドポイント（認証不要 - OpenSearch から呼び出される）
        Route(
            "/knowledge-filter/{filter_id}/webhook/{subscription_id}",
            partial(
                knowledge_filter.knowledge_filter_webhook,
                knowledge_filter_service=services["knowledge_filter_service"],
                session_manager=services["session_manager"],
            ),
            methods=["POST"],
        ),
        # チャットエンドポイント
        Route(
            "/chat",
            require_auth(services["session_manager"])(
                partial(
                    chat.chat_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/langflow",
            require_auth(services["session_manager"])(
                partial(
                    chat.langflow_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        # チャット履歴エンドポイント
        Route(
            "/chat/history",
            require_auth(services["session_manager"])(
                partial(
                    chat.chat_history_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/langflow/history",
            require_auth(services["session_manager"])(
                partial(
                    chat.langflow_history_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        # セッション削除エンドポイント
        Route(
            "/sessions/{session_id}",
            require_auth(services["session_manager"])(
                partial(
                    chat.delete_session_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["DELETE"],
        ),
        # 認証エンドポイント
        Route(
            "/auth/init",
            optional_auth(services["session_manager"])(
                partial(
                    auth.auth_init,
                    auth_service=services["auth_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/auth/callback",
            partial(
                auth.auth_callback,
                auth_service=services["auth_service"],
                session_manager=services["session_manager"],
            ),
            methods=["POST"],
        ),
        Route(
            "/auth/me",
            optional_auth(services["session_manager"])(
                partial(
                    auth.auth_me,
                    auth_service=services["auth_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/auth/logout",
            require_auth(services["session_manager"])(
                partial(
                    auth.auth_logout,
                    auth_service=services["auth_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        # コネクターエンドポイント
        Route(
            "/connectors",
            require_auth(services["session_manager"])(
                partial(
                    connectors.list_connectors,
                    connector_service=services["connector_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/connectors/{connector_type}/sync",
            require_auth(services["session_manager"])(
                partial(
                    connectors.connector_sync,
                    connector_service=services["connector_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/connectors/sync-all",
            require_auth(services["session_manager"])(
                partial(
                    connectors.sync_all_connectors,
                    connector_service=services["connector_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/connectors/{connector_type}/status",
            require_auth(services["session_manager"])(
                partial(
                    connectors.connector_status,
                    connector_service=services["connector_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/connectors/{connector_type}/token",
            require_auth(services["session_manager"])(
                partial(
                    connectors.connector_token,
                    connector_service=services["connector_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/connectors/{connector_type}/disconnect",
            require_auth(services["session_manager"])(
                partial(
                    connectors.connector_disconnect,
                    connector_service=services["connector_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["DELETE"],
        ),
        Route(
            "/connectors/{connector_type}/webhook",
            partial(
                connectors.connector_webhook,
                connector_service=services["connector_service"],
                session_manager=services["session_manager"],
            ),
            methods=["POST", "GET"],
        ),
        # ドキュメントエンドポイント
        Route(
            "/documents/check-filename",
            require_auth(services["session_manager"])(
                partial(
                    documents.check_filename_exists,
                    document_service=services["document_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/documents/delete-by-filename",
            require_auth(services["session_manager"])(
                partial(
                    documents.delete_documents_by_filename,
                    document_service=services["document_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        # OIDC エンドポイント
        Route(
            "/.well-known/openid-configuration",
            partial(oidc.oidc_discovery, session_manager=services["session_manager"]),
            methods=["GET"],
        ),
        Route(
            "/auth/jwks",
            partial(oidc.jwks_endpoint, session_manager=services["session_manager"]),
            methods=["GET"],
        ),
        Route(
            "/auth/introspect",
            partial(
                oidc.token_introspection, session_manager=services["session_manager"]
            ),
            methods=["POST"],
        ),
        # 設定エンドポイント
        Route(
            "/settings",
            require_auth(services["session_manager"])(
                partial(
                    settings.get_settings, session_manager=services["session_manager"]
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/settings",
            require_auth(services["session_manager"])(
                partial(
                    settings.update_settings,
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/onboarding/state",
            require_auth(services["session_manager"])(
                settings.update_onboarding_state
            ),
            methods=["POST"],
        ),
        # プロバイダーヘルスチェックエンドポイント
        Route(
            "/provider/health",
            require_auth(services["session_manager"])(
                provider_health.check_provider_health
            ),
            methods=["GET"],
        ),
        # ヘルスチェックエンドポイント
        Route(
            "/health",
            health_check,
            methods=["GET"],
        ),
        Route(
            "/search/health",
            opensearch_health_ready,
            methods=["GET"],
        ),
        # モデルエンドポイント
        Route(
            "/models/openai",
            require_auth(services["session_manager"])(
                partial(
                    models.get_openai_models,
                    models_service=services["models_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/models/anthropic",
            require_auth(services["session_manager"])(
                partial(
                    models.get_anthropic_models,
                    models_service=services["models_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/models/ollama",
            require_auth(services["session_manager"])(
                partial(
                    models.get_ollama_models,
                    models_service=services["models_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/models/ibm",
            require_auth(services["session_manager"])(
                partial(
                    models.get_ibm_models,
                    models_service=services["models_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        # オンボーディングエンドポイント
        Route(
            "/onboarding",
            require_auth(services["session_manager"])(
                partial(
                    settings.onboarding,
                    flows_service=services["flows_service"],
                    session_manager=services["session_manager"]
                )
            ),
            methods=["POST"],
        ),
        # オンボーディングロールバックエンドポイント
        Route(
            "/onboarding/rollback",
            require_auth(services["session_manager"])(
                partial(
                    settings.rollback_onboarding,
                    session_manager=services["session_manager"],
                    task_service=services["task_service"],
                )
            ),
            methods=["POST"],
        ),
        # Docling プリセット更新エンドポイント
        Route(
            "/settings/docling-preset",
            require_auth(services["session_manager"])(
                partial(
                    settings.update_docling_preset,
                    session_manager=services["session_manager"],
                )
            ),
            methods=["PATCH"],
        ),
        Route(
            "/nudges",
            require_auth(services["session_manager"])(
                partial(
                    nudges.nudges_from_kb_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/nudges/{chat_id}",
            require_auth(services["session_manager"])(
                partial(
                    nudges.nudges_from_chat_id_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/reset-flow/{flow_type}",
            require_auth(services["session_manager"])(
                partial(
                    flows.reset_flow_endpoint,
                    chat_service=services["flows_service"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/router/upload_ingest",
            require_auth(services["session_manager"])(
                partial(
                    router.upload_ingest_router,
                    document_service=services["document_service"],
                    langflow_file_service=services["langflow_file_service"],
                    session_manager=services["session_manager"],
                    task_service=services["task_service"],
                )
            ),
            methods=["POST"],
        ),
        # Docling サービスプロキシ
        Route(
            "/docling/health",
            partial(docling.health),
            methods=["GET"],
        ),
        # ===== API キー管理エンドポイント（UI 向け JWT 認証） =====
        Route(
            "/keys",
            require_auth(services["session_manager"])(
                partial(
                    api_keys.list_keys_endpoint,
                    api_key_service=services["api_key_service"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/keys",
            require_auth(services["session_manager"])(
                partial(
                    api_keys.create_key_endpoint,
                    api_key_service=services["api_key_service"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/keys/{key_id}",
            require_auth(services["session_manager"])(
                partial(
                    api_keys.revoke_key_endpoint,
                    api_key_service=services["api_key_service"],
                )
            ),
            methods=["DELETE"],
        ),
        # ===== パブリック API v1 エンドポイント（API キー認証） =====
        # チャットエンドポイント
        Route(
            "/v1/chat",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_chat.chat_create_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/v1/chat",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_chat.chat_list_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/v1/chat/{chat_id}",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_chat.chat_get_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/v1/chat/{chat_id}",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_chat.chat_delete_endpoint,
                    chat_service=services["chat_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["DELETE"],
        ),
        # 検索エンドポイント
        Route(
            "/v1/search",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_search.search_endpoint,
                    search_service=services["search_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        # ドキュメントエンドポイント
        Route(
            "/v1/documents/ingest",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_documents.ingest_endpoint,
                    document_service=services["document_service"],
                    task_service=services["task_service"],
                    session_manager=services["session_manager"],
                    langflow_file_service=services["langflow_file_service"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/v1/tasks/{task_id}",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_documents.task_status_endpoint,
                    task_service=services["task_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/v1/documents",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_documents.delete_document_endpoint,
                    document_service=services["document_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["DELETE"],
        ),
        # 設定エンドポイント
        Route(
            "/v1/settings",
            require_api_key(services["api_key_service"])(
                partial(v1_settings.get_settings_endpoint)
            ),
            methods=["GET"],
        ),
        Route(
            "/v1/settings",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_settings.update_settings_endpoint,
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/v1/models/{provider}",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_models.list_models_endpoint,
                    models_service=services["models_service"],
                )
            ),
            methods=["GET"],
        ),
        # ナレッジフィルターエンドポイント
        Route(
            "/v1/knowledge-filters",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_knowledge_filters.create_endpoint,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/v1/knowledge-filters/search",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_knowledge_filters.search_endpoint,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["POST"],
        ),
        Route(
            "/v1/knowledge-filters/{filter_id}",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_knowledge_filters.get_endpoint,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["GET"],
        ),
        Route(
            "/v1/knowledge-filters/{filter_id}",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_knowledge_filters.update_endpoint,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["PUT"],
        ),
        Route(
            "/v1/knowledge-filters/{filter_id}",
            require_api_key(services["api_key_service"])(
                partial(
                    v1_knowledge_filters.delete_endpoint,
                    knowledge_filter_service=services["knowledge_filter_service"],
                    session_manager=services["session_manager"],
                )
            ),
            methods=["DELETE"],
        ),
        # ----------------------------------------------------------------
        # Watson News API エンドポイント
        # ----------------------------------------------------------------
        Route(
            "/api/watson-news/articles",
            watson_news_routes.get_articles,
            methods=["GET"],
        ),
        Route(
            "/api/watson-news/articles/{id}",
            watson_news_routes.get_article_detail,
            methods=["GET"],
        ),
        Route(
            "/api/watson-news/search",
            watson_news_routes.search_articles,
            methods=["POST"],
        ),
        Route(
            "/api/watson-news/box/files",
            watson_news_routes.get_box_files,
            methods=["GET"],
        ),
        Route(
            "/api/watson-news/box/files/{file_id}",
            watson_news_routes.get_box_file_detail,
            methods=["GET"],
        ),
        Route(
            "/api/watson-news/trends",
            watson_news_routes.get_trend_data,
            methods=["GET"],
        ),
        Route(
            "/api/watson-news/etl/status",
            watson_news_routes.etl_status,
            methods=["GET"],
        ),
        Route(
            "/api/watson-news/etl/trigger",
            watson_news_routes.etl_trigger,
            methods=["POST"],
        ),
    ]

    # 開発モード（APP_ENV=development）の場合は Starlette のデバッグモードを有効化する
    debug_mode = is_dev_mode()
    logger.info(
        "Starlette アプリケーションを作成します",
        debug=debug_mode,
        app_env="development" if debug_mode else "production",
    )
    app = Starlette(debug=debug_mode, routes=routes)
    app.state.services = services  # クリーンアップ用にサービスを保存する
    app.state.background_tasks = set()

    # 起動イベントハンドラーを追加する
    @app.on_event("startup")
    async def startup_event():
        await TelemetryClient.send_event(Category.APPLICATION_STARTUP, MessageId.ORB_APP_STARTED)
        # OIDC エンドポイントをブロックしないようインデックス初期化をバックグラウンドで開始する
        t1 = asyncio.create_task(startup_tasks(services))
        app.state.background_tasks.add(t1)
        t1.add_done_callback(app.state.background_tasks.discard)

        # 定期タスククリーンアップスケジューラーを開始する
        services["task_service"].start_cleanup_scheduler()

        # Watson News ETL スケジューラーを開始する
        try:
            from connectors.watson_news.scheduler import start_scheduler
            start_scheduler()
            logger.info("Watson News ETL スケジューラーを開始しました")
        except Exception as exc:
            logger.warning("Watson News スケジューラーを開始できませんでした（致命的ではありません）", error=str(exc))

        # 定期フローバックアップタスクを開始する（5分間隔）
        async def periodic_backup():
            """15分間隔で実行される定期バックアップタスク。"""
            while True:
                try:
                    await asyncio.sleep(5 * 60)  # 5分待機する

                    # オンボーディングが完了しているか確認する
                    config = get_openrag_config()
                    if not config.edited:
                        logger.debug("オンボーディングが未完了のため定期バックアップをスキップします")
                        continue

                    flows_service = services.get("flows_service")
                    if flows_service:
                        logger.info("定期フローバックアップを実行します")
                        backup_results = await flows_service.backup_all_flows(only_if_changed=True)
                        if backup_results["backed_up"]:
                            logger.info(
                                "定期バックアップが完了しました",
                                backed_up=len(backup_results["backed_up"]),
                                skipped=len(backup_results["skipped"]),
                            )
                        else:
                            logger.debug(
                                "定期バックアップ: 変更されたフローはありませんでした",
                                skipped=len(backup_results["skipped"]),
                            )
                except asyncio.CancelledError:
                    logger.info("定期バックアップタスクがキャンセルされました")
                    break
                except Exception as e:
                    logger.error(f"定期バックアップタスクでエラーが発生しました: {str(e)}")
                    # バックアップが失敗しても実行を継続する

        backup_task = asyncio.create_task(periodic_backup())
        app.state.background_tasks.add(backup_task)
        backup_task.add_done_callback(app.state.background_tasks.discard)

    # シャットダウンイベントハンドラーを追加する
    @app.on_event("shutdown")
    async def shutdown_event():
        await TelemetryClient.send_event(Category.APPLICATION_SHUTDOWN, MessageId.ORB_APP_SHUTDOWN)
        await cleanup_subscriptions_proper(services)
        # タスクサービスをクリーンアップする（バックグラウンドタスクとプロセスプールをキャンセル）
        await services["task_service"].shutdown()
        # Watson News ETL スケジューラーを停止する
        try:
            from connectors.watson_news.scheduler import stop_scheduler
            stop_scheduler()
        except Exception:
            pass
        # 非同期クライアントをクリーンアップする
        await clients.cleanup()
        # テレメトリクライアントをクリーンアップする
        from utils.telemetry.client import cleanup_telemetry_client
        await cleanup_telemetry_client()

    return app


def cleanup():
    """アプリケーション終了時のクリーンアップ処理。"""
    # プロセスプールのみクリーンアップする（Webhook は Starlette シャットダウンが処理）
    logger.info("アプリケーションをシャットダウンしています")
    pass


async def cleanup_subscriptions_proper(services):
    """全てのアクティブな Webhook サブスクリプションをキャンセルする。"""
    logger.info("アクティブな Webhook サブスクリプションをキャンセルしています")

    try:
        connector_service = services["connector_service"]
        await connector_service.connection_manager.load_connections()

        # Webhook サブスクリプションを持つ全アクティブ接続を取得する
        all_connections = await connector_service.connection_manager.list_connections()
        active_connections = [
            c
            for c in all_connections
            if c.is_active and c.config.get("webhook_channel_id")
        ]

        for connection in active_connections:
            try:
                logger.info(
                    "接続のサブスクリプションをキャンセルしています",
                    connection_id=connection.connection_id,
                )
                connector = await connector_service.get_connector(
                    connection.connection_id
                )
                if connector:
                    subscription_id = connection.config.get("webhook_channel_id")
                    await connector.cleanup_subscription(subscription_id)
                    logger.info(
                        "サブスクリプションをキャンセルしました", subscription_id=subscription_id
                    )
            except Exception as e:
                logger.error(
                    "サブスクリプションのキャンセルに失敗しました",
                    connection_id=connection.connection_id,
                    error=str(e),
                )

        logger.info(
            "サブスクリプションのキャンセルが完了しました",
            subscription_count=len(active_connections),
        )

    except Exception as e:
        logger.error("サブスクリプションのクリーンアップに失敗しました", error=str(e))


if __name__ == "__main__":
    import uvicorn

    # TUI チェックはファイル先頭で処理済み
    # クリーンアップ関数を登録する
    atexit.register(cleanup)

    # アプリケーションを非同期で作成する
    app = asyncio.run(create_app())

    # HTTP アクセスログの有効・無効を設定する
    access_log = os.getenv("ACCESS_LOG", "true").lower() == "true"

    # サーバーを起動する（起動タスクは Starlette の startup イベントで処理される）
    uvicorn.run(
        app,
        workers=1,
        host="0.0.0.0",
        port=8000,
        reload=False,  # main から実行するためリロードを無効化する
        access_log=access_log,
    )
