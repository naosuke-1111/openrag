"""
Watson News テスト専用の conftest。

1. テスト環境にインストールできないパッケージ（langdetect 等）をスタブに差し替える。
2. グローバルの `onboard_system` autouse fixture（Langflow 接続が必要）を
   no-op でオーバーライドし、Watson News 単体テストが外部サービスなしで動くようにする。
"""
import sys
import types

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Module stubs
# ---------------------------------------------------------------------------

def _stub(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# langdetect: ビルドに失敗するため最小限のスタブを用意する
try:
    import langdetect  # noqa: F401
except (ImportError, Exception):
    ld = _stub("langdetect")
    ld.LangDetectException = Exception
    ld.detect = lambda text: "en"


# ---------------------------------------------------------------------------
# Fixture overrides
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", autouse=True)
async def onboard_system():
    """グローバルの onboard_system を Watson News テスト用に no-op でオーバーライド。
    Watson News の単体テストは Langflow / OpenSearch などの外部サービス不要。
    """
    yield
