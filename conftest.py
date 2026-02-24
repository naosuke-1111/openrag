"""
プロジェクトルートの conftest。

テスト環境にインストールされていない重量パッケージ（torch / langdetect / docling 等）を
スタブに差し替え、conftest.py チェーン全体が正常にロードされるようにする。
"""
import sys
import types


def _stub(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# torch（GPU 検出モジュールで参照）
try:
    import torch  # noqa: F401
except ImportError:
    torch_mod = _stub("torch")
    torch_mod.cuda = types.SimpleNamespace(is_available=lambda: False, device_count=lambda: 0)
    torch_mod.backends = types.SimpleNamespace(
        mps=types.SimpleNamespace(is_available=lambda: False)
    )
    torch_mod.version = types.SimpleNamespace(cuda=None)


# langdetect: ビルドに失敗するためスタブを用意する
try:
    import langdetect  # noqa: F401
except (ImportError, Exception):
    ld = _stub("langdetect")
    ld.LangDetectException = Exception
    ld.detect = lambda text: "en"


# docling: 重量パッケージのため最小限のスタブを用意する
try:
    import docling  # noqa: F401
except ImportError:
    class _FakeDocumentConverter:
        def __init__(self, *args, **kwargs):
            pass

        def convert(self, *args, **kwargs):
            return types.SimpleNamespace(
                document=types.SimpleNamespace(export_to_markdown=lambda: "")
            )

    class _FakeInputFormat:
        PDF = "pdf"
        DOCX = "docx"

    class _FakePipelineOptions:
        def __init__(self, *args, **kwargs):
            self.do_ocr = False

    _stub("docling")
    dc_mod = _stub("docling.document_converter")
    dc_mod.DocumentConverter = _FakeDocumentConverter
    dc_mod.InputFormat = _FakeInputFormat
    dc_mod.PdfFormatOption = lambda **kw: kw

    _stub("docling.datamodel")
    dpo_mod = _stub("docling.datamodel.pipeline_options")
    dpo_mod.PdfPipelineOptions = _FakePipelineOptions
    dpo_mod.EasyOcrOptions = _FakePipelineOptions
    dpo_mod.TesseractOcrOptions = _FakePipelineOptions
    _stub("docling.datamodel.base_models")

    # docling_core stubs
    _stub("docling_core")
    _stub("docling_core.types")
    io_mod = _stub("docling_core.types.io")

    class _FakeDocumentStream:
        def __init__(self, *args, **kwargs):
            pass

    io_mod.DocumentStream = _FakeDocumentStream
