import asyncio
import os
import time

import httpx
import requests
from agentd.patch import patch_openai_with_mcp
from dotenv import load_dotenv
from openai import AsyncOpenAI
from opensearchpy import AsyncOpenSearch
from opensearchpy._async.http_aiohttp import AIOHttpConnection

from utils.container_utils import get_container_host
from utils.document_processing import create_document_converter
from utils.logging_config import get_logger

load_dotenv(override=False)
load_dotenv("../", override=False)

logger = get_logger(__name__)

# 設定マネージャーをインポートする
from .config_manager import config_manager

# ---------------------------------------------------------------
# 実行環境の判定
# APP_ENV=development (または dev) の場合は開発モードとして扱う
# ---------------------------------------------------------------
_APP_ENV = os.getenv("APP_ENV", "production").lower()


def is_dev_mode() -> bool:
    """アプリケーションが開発モードで動作しているかどうかを返す。

    APP_ENV 環境変数が "development" または "dev" のとき True を返す。
    未設定の場合はデフォルトで本番モード (False) となる。
    """
    return _APP_ENV in ("development", "dev")


# 環境変数の読み込み
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD")
LANGFLOW_URL = os.getenv("LANGFLOW_URL", "http://localhost:7860")
# ブラウザリンク用の公開URL（例: http://localhost:7860）。省略可
LANGFLOW_PUBLIC_URL = os.getenv("LANGFLOW_PUBLIC_URL")
# 後方互換性のためのレガシーフロー ID 処理（非推奨警告付き）
_legacy_flow_id = os.getenv("FLOW_ID")

LANGFLOW_CHAT_FLOW_ID = os.getenv("LANGFLOW_CHAT_FLOW_ID") or _legacy_flow_id
LANGFLOW_INGEST_FLOW_ID = os.getenv("LANGFLOW_INGEST_FLOW_ID")
LANGFLOW_URL_INGEST_FLOW_ID = os.getenv("LANGFLOW_URL_INGEST_FLOW_ID")
NUDGES_FLOW_ID = os.getenv("NUDGES_FLOW_ID")

if _legacy_flow_id and not os.getenv("LANGFLOW_CHAT_FLOW_ID"):
    logger.warning("FLOW_ID は非推奨です。LANGFLOW_CHAT_FLOW_ID を使用してください")
    LANGFLOW_CHAT_FLOW_ID = _legacy_flow_id


# Langflow スーパーユーザー資格情報（APIキー生成に使用）
LANGFLOW_AUTO_LOGIN = os.getenv("LANGFLOW_AUTO_LOGIN", "False").lower() in ("true", "1", "yes")
LANGFLOW_SUPERUSER = os.getenv("LANGFLOW_SUPERUSER")
LANGFLOW_SUPERUSER_PASSWORD = os.getenv("LANGFLOW_SUPERUSER_PASSWORD")
# 環境変数で明示的にキーを指定した場合は自動生成をスキップする
LANGFLOW_KEY = os.getenv("LANGFLOW_KEY")
SESSION_SECRET = os.getenv("SESSION_SECRET", "your-secret-key-change-in-production")
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
DOCLING_OCR_ENGINE = os.getenv("DOCLING_OCR_ENGINE")

# ドキュメント取り込み方式の設定
DISABLE_INGEST_WITH_LANGFLOW = os.getenv(
    "DISABLE_INGEST_WITH_LANGFLOW", "false"
).lower() in ("true", "1", "yes")

# サンプルデータの自動取り込み設定
INGEST_SAMPLE_DATA = os.getenv(
    "INGEST_SAMPLE_DATA", "true"
).lower() in ("true", "1", "yes")

# フォルダ経由でナレッジを追加する際の1タスクあたりの最大ファイル数（バッチサイズ）
UPLOAD_BATCH_SIZE = int(os.getenv("UPLOAD_BATCH_SIZE", "25"))

# Langflow HTTP タイムアウト設定（秒単位）
# 大容量ドキュメント（300ページ超）の取り込みには30分以上かかる場合がある
# デフォルト: 合計40分、読み取りタイムアウト40分
LANGFLOW_TIMEOUT = float(os.getenv("LANGFLOW_TIMEOUT", "2400"))  # 40分
LANGFLOW_CONNECT_TIMEOUT = float(os.getenv("LANGFLOW_CONNECT_TIMEOUT", "30"))  # 30秒

# ドキュメント取り込みタスクのファイル単位処理タイムアウト（秒単位）
# 長時間の取り込みを許容するため LANGFLOW_TIMEOUT 以上に設定すること
# デフォルト: 3600秒（60分）
INGESTION_TIMEOUT = int(os.getenv("INGESTION_TIMEOUT", "3600"))


def is_no_auth_mode():
    """OAuth認証資格情報が未設定の場合（認証なしモード）かどうかを返す。"""
    result = not (GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)
    return result


# Webhook 設定 - Webhook を有効化するには必ず設定が必要
WEBHOOK_BASE_URL = os.getenv(
    "WEBHOOK_BASE_URL"
)  # デフォルト値なし - 明示的な設定が必要

# OpenSearch の設定値
VECTOR_DIM = 1536
KNN_EF_CONSTRUCTION = 100
KNN_M = 16
EMBED_MODEL = "text-embedding-3-small"

OPENAI_EMBEDDING_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

WATSONX_EMBEDDING_DIMENSIONS = {
# IBM 製モデル
"ibm/granite-embedding-107m-multilingual": 384,
"ibm/granite-embedding-278m-multilingual": 1024,
"ibm/slate-125m-english-rtrvr": 768,
"ibm/slate-125m-english-rtrvr-v2": 768,
"ibm/slate-30m-english-rtrvr": 384,
"ibm/slate-30m-english-rtrvr-v2": 384,
# サードパーティモデル
"intfloat/multilingual-e5-large": 1024,
"sentence-transformers/all-minilm-l6-v2": 384,
}

INDEX_BODY = {
    "settings": {
        "index": {"knn": True},
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "document_id": {"type": "keyword"},
            "filename": {"type": "keyword"},
            "mimetype": {"type": "keyword"},
            "page": {"type": "integer"},
            "text": {"type": "text"},
            # レガシーフィールド - 後方互換性のために維持
            # 新規ドキュメントは chunk_embedding_{model_name} フィールドを使用する
            "chunk_embedding": {
                "type": "knn_vector",
                "dimension": VECTOR_DIM,
                "method": {
                    "name": "disk_ann",
                    "engine": "jvector",
                    "space_type": "l2",
                    "parameters": {"ef_construction": KNN_EF_CONSTRUCTION, "m": KNN_M},
                },
            },
            # このチャンクに使用されたエンベディングモデルを記録する
            "embedding_model": {"type": "keyword"},
            "source_url": {"type": "keyword"},
            "connector_type": {"type": "keyword"},
            "owner": {"type": "keyword"},
            "allowed_users": {"type": "keyword"},
            "allowed_groups": {"type": "keyword"},
            "user_permissions": {"type": "object"},
            "group_permissions": {"type": "object"},
            "created_time": {"type": "date"},
            "modified_time": {"type": "date"},
            "indexed_time": {"type": "date"},
            "metadata": {"type": "object"},
        }
    },
}

# パブリック API 認証用の APIキーインデックス
API_KEYS_INDEX_NAME = "api_keys"
API_KEYS_INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "key_id": {"type": "keyword"},
            "key_hash": {"type": "keyword"},  # SHA-256 ハッシュ値（平文は保存しない）
            "key_prefix": {"type": "keyword"},  # 表示用の先頭8文字（例: "orag_abc1"）
            "user_id": {"type": "keyword"},
            "user_email": {"type": "keyword"},
            "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "created_at": {"type": "date"},
            "last_used_at": {"type": "date"},
            "revoked": {"type": "boolean"},
        }
    },
}

# Langflow REST API のベースURL（利便性のための定数）
LANGFLOW_BASE_URL = f"{LANGFLOW_URL}/api/v1"


async def get_langflow_api_key(force_regenerate: bool = False):
    """Langflow の API キーを取得する。必要に応じて新規生成する。

    Args:
        force_regenerate: True の場合、キャッシュがあっても新しいキーを生成する。
                          401/403 エラー発生時にフレッシュなキーを取得するために使用する。
    """
    global LANGFLOW_KEY

    logger.debug(
        "get_langflow_api_key が呼び出されました",
        current_key_present=bool(LANGFLOW_KEY),
        force_regenerate=force_regenerate,
    )

    # キャッシュされたキーがあり、強制再生成でない場合はそのまま返す
    if LANGFLOW_KEY and not force_regenerate:
        return LANGFLOW_KEY

    # 強制再生成の場合、キャッシュをクリアする
    if force_regenerate and LANGFLOW_KEY:
        logger.info("認証失敗のため Langflow API キーを強制再生成します")
        LANGFLOW_KEY = None

    # AUTO_LOGIN が有効かつ資格情報が未設定の場合はデフォルト資格情報を使用する
    username = LANGFLOW_SUPERUSER
    password = LANGFLOW_SUPERUSER_PASSWORD

    if LANGFLOW_AUTO_LOGIN and (not username or not password):
        logger.info("LANGFLOW_AUTO_LOGIN が有効です。デフォルトの langflow/langflow 資格情報を使用します")
        username = username or "langflow"
        password = password or "langflow"

    if not username or not password:
        logger.warning(
            "LANGFLOW_SUPERUSER と LANGFLOW_SUPERUSER_PASSWORD が未設定です。API キーの生成をスキップします"
        )
        return None

    try:
        logger.info("スーパーユーザー資格情報を使用して Langflow API キーを生成します")
        max_attempts = int(os.getenv("LANGFLOW_KEY_RETRIES", "15"))
        delay_seconds = float(os.getenv("LANGFLOW_KEY_RETRY_DELAY", "2.0"))

        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    # アクセストークンを取得するためにログインする
                    login_response = await client.post(
                        f"{LANGFLOW_URL}/api/v1/login",
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        data={
                            "username": username,
                            "password": password,
                        },
                    )
                    login_response.raise_for_status()
                    access_token = login_response.json().get("access_token")
                    if not access_token:
                        raise KeyError("access_token")

                    # API キーを新規作成する
                    api_key_response = await client.post(
                        f"{LANGFLOW_URL}/api/v1/api_key/",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {access_token}",
                        },
                        json={"name": "openrag-auto-generated"},
                    )
                    api_key_response.raise_for_status()
                    api_key = api_key_response.json().get("api_key")
                    if not api_key:
                        raise KeyError("api_key")

                    # 生成した API キーが正しく機能するかを検証する
                    validation_response = await client.get(
                        f"{LANGFLOW_URL}/api/v1/users/whoami",
                        headers={"x-api-key": api_key},
                    )
                    if validation_response.status_code == 200:
                        LANGFLOW_KEY = api_key
                        logger.info(
                            "Langflow API キーの生成と検証が完了しました",
                            key_prefix=api_key[:8],
                        )
                        return api_key
                    else:
                        logger.error(
                            "生成した API キーの検証に失敗しました",
                            status_code=validation_response.status_code,
                        )
                        raise ValueError(
                            f"API key validation failed: {validation_response.status_code}"
                        )
                except (httpx.HTTPStatusError, httpx.RequestError, KeyError) as e:
                    logger.warning(
                        "Langflow API キーの生成試行が失敗しました",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error=str(e),
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(delay_seconds)
                    else:
                        raise

    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error("Langflow API キーの生成に失敗しました", error=str(e))
        return None
    except KeyError as e:
        logger.error("Langflow からの予期しないレスポンス形式です", missing_field=str(e))
        return None
    except Exception as e:
        logger.error("Langflow API キー生成中に予期しないエラーが発生しました", error=str(e))
        return None


class AppClients:
    def __init__(self):
        self.opensearch = None
        self.langflow_client = None
        self.langflow_http_client = None
        self._patched_async_client = None  # プライベート属性 - 全プロバイダー共通のシングルクライアント
        self._client_init_lock = __import__('threading').Lock()  # スレッドセーフな初期化のためのロック
        self.converter = None

    async def initialize(self):
        # OpenSearch クライアントを初期化する
        self.opensearch = AsyncOpenSearch(
            hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
            connection_class=AIOHttpConnection,
            scheme="https",
            use_ssl=True,
            verify_certs=False,
            ssl_assert_fingerprint=None,
            http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
            http_compress=True,
        )

        # パッチ済み OpenAI クライアントの初期化（APIキーが利用可能な場合）
        # OPENAI_API_KEY が未設定でもアプリを起動できるようにする
        # （例: オンボーディング時に設定される場合）
        # プロパティが初回アクセス時に HTTP/2 プローブ付きで遅延初期化を処理する
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            logger.info("環境変数に OpenAI API キーが見つかりました。HTTP/2 プローブ付きで初回使用時に遅延初期化します")
        else:
            logger.info("環境変数に OpenAI API キーが見つかりません。必要に応じて初回使用時に初期化します")

        # ドキュメントコンバーターを初期化する
        self.converter = create_document_converter(ocr_engine=DOCLING_OCR_ENGINE)

        # 大容量ドキュメント向けに拡張タイムアウトで Langflow HTTP クライアントを初期化する
        # wait_for_langflow / get_langflow_api_key より前に作成する必要がある
        # 大容量PDF取り込み（300ページ超）に対応するため明示的なタイムアウト設定を使用する
        self.langflow_http_client = httpx.AsyncClient(
            base_url=LANGFLOW_URL,
            timeout=httpx.Timeout(
                timeout=LANGFLOW_TIMEOUT,  # 合計タイムアウト
                connect=LANGFLOW_CONNECT_TIMEOUT,  # 接続タイムアウト
                read=LANGFLOW_TIMEOUT,  # 読み取りタイムアウト（大容量PDFで最重要）
                write=LANGFLOW_CONNECT_TIMEOUT,  # 書き込みタイムアウト
                pool=LANGFLOW_CONNECT_TIMEOUT,  # プールタイムアウト
            )
        )
        logger.info(
            "拡張タイムアウト設定で Langflow HTTP クライアントを初期化しました",
            timeout_seconds=LANGFLOW_TIMEOUT,
            connect_timeout_seconds=LANGFLOW_CONNECT_TIMEOUT,
        )

        # API キーを生成する前に Langflow が正常稼働していることを確認する
        from utils.langflow_utils import wait_for_langflow
        await wait_for_langflow(langflow_http_client=self.langflow_http_client)

        # Langflow の準備完了が確認できたので API キーを生成する
        await get_langflow_api_key()

        # 生成または指定された API キーを使って Langflow クライアントを初期化する
        if LANGFLOW_KEY and self.langflow_client is None:
            try:
                if not OPENSEARCH_PASSWORD:
                    raise ValueError("OPENSEARCH_PASSWORD が設定されていません")
                else:
                    await self.ensure_langflow_client()
                    # 注意: OPENSEARCH_PASSWORD グローバル変数は docker-compose の
                    # LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT 経由で自動作成される
                    logger.info(
                        "Langflow クライアントを初期化しました。OPENSEARCH_PASSWORD は環境変数経由で利用可能です"
                    )
            except Exception as e:
                logger.warning("Langflow クライアントの初期化に失敗しました", error=str(e))
                self.langflow_client = None
        if self.langflow_client is None:
            logger.warning(
                "Langflow クライアントがまだ初期化されていません。初回使用時に再試行します"
            )

        return self

    async def ensure_langflow_client(self):
        """Langflow クライアントが存在することを確認する。必要に応じてキーを生成してクライアントを遅延作成する。"""
        if self.langflow_client is not None:
            return self.langflow_client
        # リトライ付きで再度キーの生成を試みる
        await get_langflow_api_key()
        if LANGFLOW_KEY and self.langflow_client is None:
            try:
                self.langflow_client = AsyncOpenAI(
                    base_url=f"{LANGFLOW_URL}/api/v1", api_key=LANGFLOW_KEY
                )
                logger.info("Langflow クライアントをオンデマンドで初期化しました")
            except Exception as e:
                logger.error(
                    "Langflow クライアントのオンデマンド初期化に失敗しました", error=str(e)
                )
                self.langflow_client = None
        return self.langflow_client

    @property
    def patched_async_client(self):
        """
        初回アクセス時に OpenAI クライアントが初期化されていることを保証するプロパティ。
        APIキーなしでもアプリを起動できるよう遅延初期化を実現する。

        クライアントは複数プロバイダーに対応するため LiteLLM サポートでパッチされる。
        全プロバイダーの資格情報は LiteLLM ルーティング用に環境変数に読み込まれる。

        注意: このクライアントは長期稼働シングルトンであり、cleanup() で閉じる必要がある。
        並行初期化を防ぐためロックによるスレッドセーフを実現している。
        """
        # ロックなしで高速チェックする
        if self._patched_async_client is not None:
            return self._patched_async_client

        # 1スレッドのみが初期化を行うようにロックを使用する
        with self._client_init_lock:
            # ロック取得後に再チェックする（ダブルチェックロッキング）
            if self._patched_async_client is not None:
                return self._patched_async_client

            # LiteLLM 用に全プロバイダーの資格情報を環境変数に読み込む
            # LiteLLM はモデル名のプレフィックスでルーティングする（openai/, ollama/, watsonx/ など）
            try:
                config = get_openrag_config()

                # OpenAI の資格情報を設定する
                if config.providers.openai.api_key:
                    os.environ["OPENAI_API_KEY"] = config.providers.openai.api_key
                    logger.debug("設定ファイルから OpenAI API キーを読み込みました")

                # Anthropic の資格情報を設定する
                if config.providers.anthropic.api_key:
                    os.environ["ANTHROPIC_API_KEY"] = config.providers.anthropic.api_key
                    logger.debug("設定ファイルから Anthropic API キーを読み込みました")

                # WatsonX の資格情報を設定する
                if config.providers.watsonx.api_key:
                    os.environ["WATSONX_API_KEY"] = config.providers.watsonx.api_key
                if config.providers.watsonx.endpoint:
                    os.environ["WATSONX_ENDPOINT"] = config.providers.watsonx.endpoint
                    os.environ["WATSONX_API_BASE"] = config.providers.watsonx.endpoint  # LiteLLM が期待する名前
                if config.providers.watsonx.project_id:
                    os.environ["WATSONX_PROJECT_ID"] = config.providers.watsonx.project_id
                if config.providers.watsonx.api_key:
                    logger.debug("設定ファイルから WatsonX 資格情報を読み込みました")

                # Ollama のエンドポイントを設定する
                if config.providers.ollama.endpoint:
                    os.environ["OLLAMA_BASE_URL"] = config.providers.ollama.endpoint
                    os.environ["OLLAMA_ENDPOINT"] = config.providers.ollama.endpoint
                    logger.debug("設定ファイルから Ollama エンドポイントを読み込みました")

            except Exception as e:
                logger.debug("設定ファイルからプロバイダー資格情報を読み込めませんでした", error=str(e))

            # クライアントを初期化する - AsyncOpenAI() は環境変数から読み込む
            # まず HTTP/2 でプローブを試みて、タイムアウトした場合は HTTP/1.1 にフォールバックする
            import asyncio
            import concurrent.futures
            import threading

            async def probe_and_initialize():
                # まず HTTP/2（デフォルト）で試みる
                client_http2 = patch_openai_with_mcp(AsyncOpenAI())
                logger.info("HTTP/2 で OpenAI クライアントをプローブ中...")

                try:
                    # 小さなエンベディングと短いタイムアウトでプローブを実行する
                    await asyncio.wait_for(
                        client_http2.embeddings.create(
                            model='text-embedding-3-small',
                            input=['test']
                        ),
                        timeout=5.0
                    )
                    logger.info("HTTP/2 で OpenAI クライアントを初期化しました（プローブ成功）")
                    return client_http2
                except (asyncio.TimeoutError, Exception) as probe_error:
                    logger.warning("HTTP/2 プローブが失敗しました。HTTP/1.1 にフォールバックします", error=str(probe_error))
                    # HTTP/2 クライアントを閉じる
                    try:
                        await client_http2.close()
                    except Exception:
                        pass

                    # 明示的なタイムアウト設定で HTTP/1.1 にフォールバックする
                    http_client = httpx.AsyncClient(
                        http2=False,
                        timeout=httpx.Timeout(60.0, connect=10.0)
                    )
                    client_http1 = patch_openai_with_mcp(
                        AsyncOpenAI(http_client=http_client)
                    )
                    logger.info("HTTP/1.1 で OpenAI クライアントを初期化しました（フォールバック）")
                    return client_http1

            def run_probe_in_thread():
                """専用のイベントループを持つ新しいスレッドで非同期プローブを実行する。"""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(probe_and_initialize())
                finally:
                    loop.close()

            try:
                # 独自のイベントループを持つ別スレッドでプローブを実行する
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_probe_in_thread)
                    self._patched_async_client = future.result(timeout=15)
                logger.info("OpenAI クライアントの初期化が完了しました")
            except Exception as e:
                logger.error(f"OpenAI クライアントの初期化に失敗しました: {e.__class__.__name__}: {str(e)}")
                raise ValueError(f"Failed to initialize OpenAI client: {str(e)}. Please complete onboarding or set OPENAI_API_KEY environment variable.")

            return self._patched_async_client

    @property
    def patched_llm_client(self):
        """patched_async_client のエイリアス - 別クライアントを期待するコードとの後方互換性のため。"""
        return self.patched_async_client

    @property
    def patched_embedding_client(self):
        """patched_async_client のエイリアス - 別クライアントを期待するコードとの後方互換性のため。"""
        return self.patched_async_client

    async def refresh_patched_client(self):
        """パッチ済みクライアントをリセットして次回使用時に更新されたプロバイダー資格情報を反映させる。"""
        if self._patched_async_client is not None:
            try:
                await self._patched_async_client.close()
                logger.info("リフレッシュのためパッチ済みクライアントを閉じました")
            except Exception as e:
                logger.warning("リフレッシュ中にパッチ済みクライアントを閉じられませんでした", error=str(e))
            finally:
                self._patched_async_client = None

    async def cleanup(self):
        """リソースをクリーンアップする - アプリケーション終了時に呼び出すこと。"""
        # 作成されていた場合は AsyncOpenAI クライアントを閉じる
        if self._patched_async_client is not None:
            try:
                await self._patched_async_client.close()
                logger.info("AsyncOpenAI クライアントを閉じました")
            except Exception as e:
                logger.error("AsyncOpenAI クライアントを閉じられませんでした", error=str(e))
            finally:
                self._patched_async_client = None

        # 存在する場合は Langflow HTTP クライアントを閉じる
        if self.langflow_http_client is not None:
            try:
                await self.langflow_http_client.aclose()
                logger.info("Langflow HTTP クライアントを閉じました")
            except Exception as e:
                logger.error("Langflow HTTP クライアントを閉じられませんでした", error=str(e))
            finally:
                self.langflow_http_client = None

        # 存在する場合は OpenSearch クライアントを閉じる
        if self.opensearch is not None:
            try:
                await self.opensearch.close()
                logger.info("OpenSearch クライアントを閉じました")
            except Exception as e:
                logger.error("OpenSearch クライアントを閉じられませんでした", error=str(e))
            finally:
                self.opensearch = None

        # 存在する場合は Langflow クライアントを閉じる（AsyncOpenAI クライアントの一種）
        if self.langflow_client is not None:
            try:
                await self.langflow_client.close()
                logger.info("Langflow クライアントを閉じました")
            except Exception as e:
                logger.error("Langflow クライアントを閉じられませんでした", error=str(e))
            finally:
                self.langflow_client = None

    async def langflow_request(self, method: str, endpoint: str, **kwargs):
        """全 Langflow API リクエストの中央集権メソッド。

        認証失敗（401/403）時にフレッシュな API キーで1回リトライする。
        """
        api_key = await get_langflow_api_key()
        if not api_key:
            raise ValueError("Langflow API キーが利用できません")

        # ヘッダーを適切にマージする - 渡されたヘッダーがデフォルトより優先される
        default_headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        existing_headers = kwargs.pop("headers", {})
        headers = {**default_headers, **existing_headers}

        # Content-Type が明示的に None に設定されている場合は削除する（ファイルアップロード用）
        if headers.get("Content-Type") is None:
            headers.pop("Content-Type", None)

        url = f"{LANGFLOW_URL}{endpoint}"

        response = await self.langflow_http_client.request(
            method=method, url=url, headers=headers, **kwargs
        )

        # 認証失敗時はフレッシュな API キーで1回リトライする
        if response.status_code in (401, 403):
            logger.warning(
                "Langflow リクエストの認証に失敗しました。API キーを再生成してリトライします",
                status_code=response.status_code,
                endpoint=endpoint,
            )
            api_key = await get_langflow_api_key(force_regenerate=True)
            if api_key:
                headers["x-api-key"] = api_key
                response = await self.langflow_http_client.request(
                    method=method, url=url, headers=headers, **kwargs
                )

        return response

    async def _create_langflow_global_variable(
        self, name: str, value: str, modify: bool = False
    ):
        """Langflow の API 経由でグローバル変数を作成する。"""
        payload = {
            "name": name,
            "value": value,
            "default_fields": [],
            "type": "Credential",
        }

        try:
            response = await self.langflow_request(
                "POST", "/api/v1/variables/", json=payload
            )

            if response.status_code in [200, 201]:
                logger.info(
                    "Langflow グローバル変数の作成が完了しました",
                    variable_name=name,
                )
            elif response.status_code == 400 and "already exists" in response.text:
                if modify:
                    logger.info(
                        "Langflow グローバル変数が既に存在します。更新を試みます",
                        variable_name=name,
                    )
                    await self._update_langflow_global_variable(name, value)
                else:
                    logger.info(
                        "Langflow グローバル変数が既に存在します",
                        variable_name=name,
                    )
            else:
                logger.warning(
                    "Langflow グローバル変数の作成に失敗しました",
                    variable_name=name,
                    status_code=response.status_code,
                )
        except Exception as e:
            logger.error(
                "Langflow グローバル変数の作成中に例外が発生しました",
                variable_name=name,
                error=str(e),
            )

    async def _update_langflow_global_variable(self, name: str, value: str):
        """Langflow の API 経由で既存のグローバル変数を更新する。"""
        try:
            # 一致する名前の変数を見つけるため全変数を取得する
            get_response = await self.langflow_request("GET", "/api/v1/variables/")

            if get_response.status_code != 200:
                logger.error(
                    "更新用の変数一覧の取得に失敗しました",
                    variable_name=name,
                    status_code=get_response.status_code,
                )
                return

            variables = get_response.json()
            target_variable = None

            # 名前が一致する変数を探す
            for variable in variables:
                if variable.get("name") == name:
                    target_variable = variable
                    break

            if not target_variable:
                logger.error("更新対象の変数が見つかりませんでした", variable_name=name)
                return

            variable_id = target_variable.get("id")
            if not variable_id:
                logger.error("更新対象の変数 ID が見つかりませんでした", variable_name=name)
                return

            # PATCH を使用して変数を更新する
            update_payload = {
                "id": variable_id,
                "name": name,
                "value": value,
                "default_fields": target_variable.get("default_fields", []),
            }

            patch_response = await self.langflow_request(
                "PATCH", f"/api/v1/variables/{variable_id}", json=update_payload
            )

            if patch_response.status_code == 200:
                logger.info(
                    "Langflow グローバル変数の更新が完了しました",
                    variable_name=name,
                    variable_id=variable_id,
                )
            else:
                logger.warning(
                    "Langflow グローバル変数の更新に失敗しました",
                    variable_name=name,
                    variable_id=variable_id,
                    status_code=patch_response.status_code,
                    response_text=patch_response.text,
                )

        except Exception as e:
            logger.error(
                "Langflow グローバル変数の更新中に例外が発生しました",
                variable_name=name,
                error=str(e),
            )

    def create_user_opensearch_client(self, jwt_token: str):
        """ユーザーの JWT トークンを使って OIDC 認証用の OpenSearch クライアントを作成する。"""
        headers = {"Authorization": f"Bearer {jwt_token}"}

        return AsyncOpenSearch(
            hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
            connection_class=AIOHttpConnection,
            scheme="https",
            use_ssl=True,
            verify_certs=False,
            ssl_assert_fingerprint=None,
            headers=headers,
            http_compress=True,
            timeout=30,  # 30秒タイムアウト
            max_retries=3,
            retry_on_timeout=True,
        )


# コンポーネントテンプレートのパス設定
WATSONX_LLM_COMPONENT_PATH = os.getenv(
    "WATSONX_LLM_COMPONENT_PATH", "flows/components/watsonx_llm.json"
)
WATSONX_LLM_TEXT_COMPONENT_PATH = os.getenv(
    "WATSONX_LLM_TEXT_COMPONENT_PATH", "flows/components/watsonx_llm_text.json"
)
WATSONX_EMBEDDING_COMPONENT_PATH = os.getenv(
    "WATSONX_EMBEDDING_COMPONENT_PATH", "flows/components/watsonx_embedding.json"
)
OLLAMA_LLM_COMPONENT_PATH = os.getenv(
    "OLLAMA_LLM_COMPONENT_PATH", "flows/components/ollama_llm.json"
)
OLLAMA_LLM_TEXT_COMPONENT_PATH = os.getenv(
    "OLLAMA_LLM_TEXT_COMPONENT_PATH", "flows/components/ollama_llm_text.json"
)
OLLAMA_EMBEDDING_COMPONENT_PATH = os.getenv(
    "OLLAMA_EMBEDDING_COMPONENT_PATH", "flows/components/ollama_embedding.json"
)

# フロー内のコンポーネント表示名設定

OPENAI_EMBEDDING_COMPONENT_DISPLAY_NAME = os.getenv(
    "OPENAI_EMBEDDING_COMPONENT_DISPLAY_NAME", "Embedding Model"
)
OPENAI_LLM_COMPONENT_DISPLAY_NAME = os.getenv(
    "OPENAI_LLM_COMPONENT_DISPLAY_NAME", "Language Model"
)

AGENT_COMPONENT_DISPLAY_NAME = os.getenv(
    "AGENT_COMPONENT_DISPLAY_NAME", "Agent"
)

# プロバイダー固有のコンポーネント表示名設定
WATSONX_EMBEDDING_COMPONENT_DISPLAY_NAME = os.getenv(
    "WATSONX_EMBEDDING_COMPONENT_DISPLAY_NAME", "IBM watsonx.ai Embeddings"
)
WATSONX_LLM_COMPONENT_DISPLAY_NAME = os.getenv(
    "WATSONX_LLM_COMPONENT_DISPLAY_NAME", "IBM watsonx.ai"
)

OLLAMA_EMBEDDING_COMPONENT_DISPLAY_NAME = os.getenv(
    "OLLAMA_EMBEDDING_COMPONENT_DISPLAY_NAME", "Ollama Embeddings"
)
OLLAMA_LLM_COMPONENT_DISPLAY_NAME = os.getenv("OLLAMA_LLM_COMPONENT_DISPLAY_NAME", "Ollama")

# 取り込みフロー用の Docling コンポーネント表示名
DOCLING_COMPONENT_DISPLAY_NAME = os.getenv("DOCLING_COMPONENT_DISPLAY_NAME", "Docling Serve")

LOCALHOST_URL = get_container_host() or "localhost"

# グローバルクライアントインスタンス
clients = AppClients()


# 設定へのアクセス関数
def get_openrag_config():
    """現在の OpenRAG 設定を取得する。"""
    return config_manager.get_config()


# 後方互換性と利便性のために設定を公開するヘルパー関数
def get_provider_config():
    """プロバイダー設定を取得する。"""
    return get_openrag_config().provider


def get_knowledge_config():
    """ナレッジ設定を取得する。"""
    return get_openrag_config().knowledge


def get_agent_config():
    """エージェント設定を取得する。"""
    return get_openrag_config().agent


def get_embedding_model() -> str:
    """現在設定されているエンベディングモデル名を返す。"""
    return get_openrag_config().knowledge.embedding_model or EMBED_MODEL if DISABLE_INGEST_WITH_LANGFLOW else ""


def get_index_name() -> str:
    """現在設定されているインデックス名を返す。"""
    return get_openrag_config().knowledge.index_name
