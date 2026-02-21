import os
import sys
from typing import Any, Dict
import structlog
from structlog import processors


LOC_WIDTH_SHORT = 30
LOC_WIDTH_LONG = 60

# ログレベルごとのANSIカラーコード
LEVEL_COLORS = {
    "DEBUG": "\033[36m",       # シアン
    "INFO": "\033[32m",        # 緑
    "WARNING": "\033[33m",     # 黄
    "ERROR": "\033[31m",       # 赤
    "CRITICAL": "\033[1;31m",  # 太字赤
}
DIM = "\033[38;5;244m"  # 中間グレー
RESET = "\033[0m"


def configure_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    include_timestamps: bool = True,
    service_name: str = "openrag",
) -> None:
    """アプリケーションの structlog を設定する。"""

    # 文字列のログレベルを実際のレベル定数に変換する
    level = getattr(
        structlog.stdlib.logging, log_level.upper(), structlog.stdlib.logging.INFO
    )

    # 全プロセッサ共通のベース設定
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if include_timestamps:
        shared_processors.append(structlog.processors.TimeStamper(fmt="iso"))

    # サービス名とファイル位置を全ログに付与する
    shared_processors.append(
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.PATHNAME,
            ]
        )
    )

    # コンソール出力フォーマットの設定
    if json_logs or os.getenv("LOG_FORMAT", "").lower() == "json":
        # 本番環境・コンテナ向けのJSON出力
        shared_processors.append(structlog.processors.JSONRenderer())
        console_renderer = structlog.processors.JSONRenderer()
    else:
        # カスタム整形フォーマット: タイムスタンプ パス/ファイル:行番号 ログ内容
        use_colors = "NO_COLOR" not in os.environ and hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

        def custom_formatter(logger, log_method, event_dict):
            timestamp = event_dict.pop("timestamp", "")
            pathname = event_dict.pop("pathname", "")
            filename = event_dict.pop("filename", "")
            lineno = event_dict.pop("lineno", "")
            level = event_dict.pop("level", "").upper()

            if filename and lineno:
                location = f"{filename}:{lineno}"
                loc_width = LOC_WIDTH_SHORT
            elif pathname and lineno:
                location = f"{pathname}:{lineno}"
                loc_width = LOC_WIDTH_LONG
            elif filename:
                location = filename
                loc_width = LOC_WIDTH_SHORT
            elif pathname:
                location = pathname
                loc_width = LOC_WIDTH_LONG
            else:
                location = "unknown"
                loc_width = LOC_WIDTH_SHORT

            # メインメッセージを組み立てる
            message_parts = []
            event = event_dict.pop("event", "")
            if event:
                message_parts.append(event)

            if use_colors:
                colored_timestamp = f"{DIM}{timestamp}{RESET}"
                color = LEVEL_COLORS.get(level, "")
                colored_level = f"{color}{level:<7}{RESET}"
            else:
                colored_timestamp = timestamp
                colored_level = f"{level:<7}"

            header = f"[{colored_timestamp}] [{colored_level}] [{location:<{loc_width}}] "
            # パディング計算のためANSIエスケープコードを除いた可視幅を使用する
            visible_header = f"[{timestamp}] [{level:<7}] [{location:<{loc_width}}] "

            # 残りのコンテキスト情報をインデント付きの複数行フィールドとして追加する
            extra = {k: v for k, v in event_dict.items() if k not in ["service", "func_name"]}
            if extra:
                padding = " " * len(visible_header)
                for key, value in extra.items():
                    message_parts.append(f"\n{padding}- {key}: {value}")

            message = "".join(message_parts)

            return f"{header}{message}"

        console_renderer = custom_formatter

    # structlog の設定を確定する
    structlog.configure(
        processors=shared_processors + [console_renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )

    # グローバルコンテキストを設定する
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """設定済みのロガーインスタンスを取得する。"""
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


def configure_from_env() -> None:
    """環境変数からログ設定を読み込んで適用する。

    APP_ENV=development の場合はデフォルトのログレベルを DEBUG に設定する。
    LOG_LEVEL が明示的に指定されている場合はその値を優先する。
    """
    app_env = os.getenv("APP_ENV", "production").lower()
    is_dev = app_env in ("development", "dev")

    # LOG_LEVEL が未設定の場合、開発環境は DEBUG、本番環境は INFO をデフォルトとする
    default_log_level = "DEBUG" if is_dev else "INFO"
    log_level = os.getenv("LOG_LEVEL", default_log_level)

    json_logs = os.getenv("LOG_FORMAT", "").lower() == "json"
    service_name = os.getenv("SERVICE_NAME", "openrag")

    configure_logging(
        log_level=log_level, json_logs=json_logs, service_name=service_name
    )
