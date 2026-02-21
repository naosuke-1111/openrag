# Watson News (IBM版) — 実装方針書

> 作成日: 2026-02-21
> 最終更新: 2026-02-21
> ブランチ: `claude/plan-implementation-strategy-zt707`
> 要件定義書: `watson-news/requirements.md`

---

## 1. 基本方針

### 1.1 openRAGの既存資産を最大活用する

Watson News は新規プロダクトを一から構築するのではなく、**openRAGの既存インフラ上に機能を積み上げる**形で実装する。

| openRAG既存資産 | Watson Newsでの活用 |
|---|---|
| `BaseConnector` | `GdeltConnector`・`IbmCrawlConnector`・`BoxConnector` を派生クラスとして実装 |
| OneDrive / SharePoint コネクタ | **Box コネクタの実装パターン参照**（OAuth 2.0 フロー・`ConnectorDocument` 変換） |
| Document Store（OpenSearch） | ニュース記事・Box文書の統合インデックスとして活用 |
| `document_service.py` | Embedding・チャンク処理のユーティリティを再利用 |
| `search_service.py` | RAG検索クエリエンジンをそのまま活用 |
| Next.js + Carbon Design System | 既存UIフレームワーク上にWatson News画面を追加 |
| Starlette バックエンド | 新規APIルートを追加する形で拡張 |

### 1.2 段階的デリバリー（Phase 1 優先）

Phase 1（3ヶ月）のMVPに集中し、動くものを早期に届ける。
Phase 2・3は Phase 1 完成後にバックログとして管理する。

### 1.3 既存コードへの影響を最小化する

- 既存の `src/` ディレクトリへの変更は最小限にとどめる
- Watson News 固有のコードは `src/connectors/watson_news/` 配下にカプセル化する
- Box コネクタは `src/connectors/box/` に独立配置し、Watson News 以外からも再利用可能にする
- 既存テストが壊れないことを CI で保証する

---

## 2. ディレクトリ構成

```
openrag/
├── src/
│   ├── connectors/
│   │   ├── box/                        ← 新規追加（独立コネクタ）
│   │   │   ├── __init__.py
│   │   │   ├── connector.py            # BoxConnector（BaseConnector継承）
│   │   │   └── oauth.py                # Box OAuth 2.0 / JWT 認証
│   │   ├── watson_news/                ← 新規追加
│   │   │   ├── __init__.py
│   │   │   ├── gdelt_connector.py      # GDELT API取得
│   │   │   ├── ibm_crawl_connector.py  # IBM公式サイト クローラ（差分検知）
│   │   │   ├── etl_pipeline.py         # ETLオーケストレーション
│   │   │   ├── cleaner.py              # HTMLタグ除去・重複排除・テキスト抽出
│   │   │   ├── enricher.py             # AI解析（要約・センチメント・エンティティ）
│   │   │   └── scheduler.py            # 定期実行スケジューラ
│   ├── api/
│   │   ├── watson_news/                ← 新規追加
│   │   │   ├── __init__.py
│   │   │   ├── routes.py               # REST APIルート定義
│   │   │   └── schemas.py              # Pydantic スキーマ
│   ├── models/
│   │   └── watson_news.py              ← 新規追加（データモデル）
│   └── services/
│       └── watson_news_service.py      ← 新規追加
├── frontend/
│   └── src/
│       └── pages/
│           └── watson-news/            ← 新規追加
│               ├── index.tsx           # Dashboard
│               ├── search.tsx          # Search & Filter
│               ├── [id].tsx            # Article Detail
│               ├── box/
│               │   └── [fileId].tsx    # Box Document View
│               ├── trends.tsx          # Trend Analytics
│               └── alerts.tsx          # Alerts & Reports
├── watson-news/
│   ├── requirements.md                 ← 要件定義書
│   └── implementation-strategy.md     ← 本ファイル
└── tests/
    └── watson_news/                    ← 新規追加
        ├── test_gdelt_connector.py
        ├── test_ibm_crawl_connector.py
        ├── test_box_connector.py
        └── test_etl_pipeline.py
```

---

## 3. バックエンド実装方針

### 3.1 GDELT コネクタ

`BaseConnector` を継承。GDELT は公開 API のため OAuth 不要。

```python
# src/connectors/watson_news/gdelt_connector.py
class GdeltConnector(BaseConnector):
    CONNECTOR_NAME = "gdelt_news"
    CONNECTOR_DESCRIPTION = "GDELT News Connector for IBM-related articles"

    async def fetch_articles(
        self,
        query: str = "IBM",
        max_records: int = 250,
        timespan: str = "15min"
    ) -> list[ConnectorDocument]:
        url = (
            "https://api.gdeltproject.org/api/v2/doc/doc"
            f"?query={query}&mode=ArtList&maxrecords={max_records}"
            f"&format=json&timespan={timespan}"
        )
        ...
```

---

### 3.2 IBM公式サイト クローラ（差分検知方式）

RSS は存在しないため、**インデックスページを巡回して新規URLを検出**する方式を採用する。

#### クロール対象サイトと設定

```python
# src/connectors/watson_news/ibm_crawl_connector.py
IBM_CRAWL_TARGETS = [
    {
        "name": "announcements",
        "index_url": "https://www.ibm.com/new/announcements",
        "language": "en",
        "interval_hours": 2,
    },
    {
        "name": "research_blog",
        "index_url": "https://research.ibm.com/blog",
        "language": "en",
        "interval_hours": 4,
    },
    {
        "name": "newsroom",
        "index_url": "https://newsroom.ibm.com/announcements",
        "language": "en",
        "interval_hours": 2,
    },
    {
        "name": "annual_report",
        "index_url": "https://www.ibm.com/investor/services/annual-report",
        "language": "en",
        "interval_hours": 24,
    },
    {
        "name": "case_studies_en",
        "index_url": "https://www.ibm.com/case-studies?lnk=flatitem",
        "language": "en",
        "interval_hours": 24,
    },
    {
        "name": "think_insights_jp",
        "index_url": "https://www.ibm.com/jp-ja/think/insights",
        "language": "ja",
        "interval_hours": 4,
    },
    {
        "name": "case_studies_jp",
        "index_url": "https://www.ibm.com/case-studies/jp-ja/",
        "language": "ja",
        "interval_hours": 24,
    },
]
```

#### 差分検知ロジック

```python
async def crawl_index_page(target: dict) -> list[str]:
    """インデックスページから記事URLリストを抽出する"""
    html = await fetch_with_retry(target["index_url"])
    soup = BeautifulSoup(html, "html.parser")
    urls = extract_article_urls(soup, base_domain="ibm.com")
    return urls

async def detect_new_urls(urls: list[str], index_name: str) -> list[str]:
    """OpenSearch の既知URLセットと差分を計算し新規URLを返す"""
    known = await opensearch_client.get_known_urls(index_name)
    return [u for u in urls if u not in known]

async def crawl_article(url: str, target: dict) -> ConnectorDocument:
    """記事本文をクロールして ConnectorDocument に変換する"""
    # robots.txt 遵守・5秒以上のインターバルを確保
    await asyncio.sleep(CRAWL_INTERVAL_SECONDS)
    html = await fetch_with_retry(url, respect_robots=True)
    ...
```

**robots.txt 対応:**
- `robotparser.RobotFileParser` で各サイトの `robots.txt` を取得・キャッシュ（1時間有効）
- クロール前に `can_fetch()` で許可確認
- 禁止 URL はスキップし、ログ記録のみ行う

---

### 3.3 Box コネクタ

既存の OneDrive / SharePoint コネクタと**同一パターン**で実装する。

#### 認証方式

Box は以下の2方式をサポートする。Phase 1 は OAuth 2.0 を採用し、Phase 2 以降でサーバー間の JWT 方式を検討する。

| 方式 | 用途 | Phase |
|---|---|---|
| OAuth 2.0 (Authorization Code) | ユーザー個人の Box アカウント連携 | Phase 1 |
| JWT (Server Authentication) | サービスアカウントによる一括取得 | Phase 2 以降 |

```python
# src/connectors/box/connector.py
class BoxConnector(BaseConnector):
    """Box connector using OAuth 2.0 for authentication.
    Follows the same pattern as OneDriveConnector / SharePointConnector.
    """

    CLIENT_ID_ENV_VAR = "BOX_OAUTH_CLIENT_ID"
    CLIENT_SECRET_ENV_VAR = "BOX_OAUTH_CLIENT_SECRET"  # pragma: allowlist secret

    CONNECTOR_NAME = "Box"
    CONNECTOR_DESCRIPTION = "Add knowledge from Box"
    CONNECTOR_ICON = "box"

    # Box API エンドポイント
    AUTH_ENDPOINT = "https://account.box.com/api/oauth2/authorize"
    TOKEN_ENDPOINT = "https://api.box.com/oauth2/token"
    API_BASE = "https://api.box.com/2.0"

    # 必要スコープ（最小権限原則）
    SCOPES = ["root_readonly"]

    async def authenticate(self) -> bool:
        """Box OAuth 2.0 認証フロー（OneDriveOAuth と同じ構造）"""
        ...

    async def list_files(self, folder_id: str = "0") -> list[dict]:
        """指定フォルダ配下のファイル一覧を再帰取得"""
        ...

    async def download_file(self, file_id: str) -> ConnectorDocument:
        """ファイルをダウンロードして ConnectorDocument に変換"""
        ...

    async def get_updated_files(
        self,
        folder_id: str,
        since: datetime
    ) -> list[dict]:
        """updated_at > since のファイルのみを返す（差分取得）"""
        ...
```

```python
# src/connectors/box/oauth.py
class BoxOAuth:
    """Box OAuth 2.0 認証ハンドラー（OneDriveOAuth と同構造）"""

    AUTH_ENDPOINT = "https://account.box.com/api/oauth2/authorize"
    TOKEN_ENDPOINT = "https://api.box.com/oauth2/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_file: str = "box_token.json",
        redirect_uri: str = "http://localhost",
    ):
        ...

    async def get_access_token(self) -> str:
        """トークンキャッシュがあればそれを使用、期限切れなら refresh"""
        ...

    async def refresh_token(self) -> None:
        """Box refresh_token を使ってアクセストークンを更新"""
        ...
```

#### Box ファイルのテキスト抽出

既存の `document_service.py` が docling を使ってPDF・Office形式を処理しているため、そのまま流用する。

```python
from services.document_service import process_document_sync

async def process_box_file(doc: ConnectorDocument) -> list[BoxChunk]:
    # docling でテキスト抽出（既存ユーティリティ）
    text = process_document_sync(doc.content, doc.mimetype)
    # チャンク分割（既存ユーティリティ）
    chunks = chunk_texts_for_embeddings([text], max_tokens=8192)
    return [BoxChunk(box_file_id=doc.id, chunk_index=i, text=c)
            for i, c in enumerate(chunks[0])]
```

---

### 3.4 ETLパイプライン統合

```
                          ┌─ GDELT fetch ──────────────────────┐
                          │                                     │
ETLオーケストレーター ────┤─ IBM crawl（差分検知→記事クロール）├─→ clean → enrich → embed → index
                          │                                     │
                          └─ Box diff fetch ────────────────────┘
```

各ステップは独立した非同期関数として実装し、単体テストを容易にする。

#### Step 1: fetch / crawl / diff-fetch

- **GDELT**: HTTP GET → JSON パース → `ConnectorDocument` に変換
- **IBM クローラ**: インデックスページ巡回 → 差分URL検出 → 記事クロール → `ConnectorDocument` に変換
- **Box**: `updated_at > last_run` のファイルのみダウンロード → `ConnectorDocument` に変換

取得結果は Raw Layer（OpenSearch）に保存。

#### Step 2: clean

```python
# cleaner.py
def clean_news_article(doc: ConnectorDocument) -> NewsClean | None:
    body = html2text(doc.content.decode())     # HTML除去
    body = normalize_whitespace(body)           # 正規化
    if is_duplicate(doc.source_url):            # URL重複チェック
        return None
    if not is_target_language(body):            # 言語フィルタ（en/ja）
        return None
    return NewsClean(...)

def clean_box_document(doc: ConnectorDocument) -> list[BoxChunk]:
    # docling でテキスト抽出 → チャンク分割
    return process_box_file(doc)
```

#### Step 3: enrich

watsonx.ai Granite モデルを利用し、以下を並列実行。ニュース・Box文書共通の処理。

| 処理 | モデル | 出力 |
|---|---|---|
| 要約 | `ibm/granite-13b-instruct-v2` | `summary` |
| センチメント分析 | `ibm/granite-13b-instruct-v2` | `sentiment_label`, `sentiment_score` |
| エンティティ抽出 | `ibm/granite-13b-instruct-v2` | `entities` |
| トピック分類 | `ibm/granite-13b-instruct-v2` | `topic` |

Box文書はチャンク単位でエンリッチメントを実行する（センチメント分析は省略可）。

#### Step 4: embed

既存 `document_service.py` の `chunk_texts_for_embeddings()` を再利用。
ニュース記事と Box文書チャンクを同一の Embedding モデル・インデックスで処理し、**横断検索を可能にする**。

```python
from services.document_service import chunk_texts_for_embeddings

# ニュース記事
texts = [f"{a.title}\n{a.clean_body}" for a in articles]
# Box文書チャンク
texts += [chunk.clean_text for chunk in box_chunks]

batches = chunk_texts_for_embeddings(texts, max_tokens=8192)
```

Embedding モデル: `ibm/granite-embedding-125m-english`（watsonx.ai）

#### Step 5: index

OpenSearch の各インデックスへ upsert（`_id` = UUID）。
`source_type` フィールドで検索時のフィルタリングが可能。

---

### 3.5 スケジューラ

`APScheduler` で定期実行を管理する（既存の `task_service.py` パターンに合わせる）。

```python
# scheduler.py
scheduler.add_job(fetch_gdelt,            "interval", minutes=15)
scheduler.add_job(crawl_announcements,    "interval", hours=2)
scheduler.add_job(crawl_research_blog,    "interval", hours=4)
scheduler.add_job(crawl_newsroom,         "interval", hours=2)
scheduler.add_job(crawl_annual_report,    "interval", hours=24)
scheduler.add_job(crawl_case_studies_en,  "interval", hours=24)
scheduler.add_job(crawl_think_insights_jp,"interval", hours=4)
scheduler.add_job(crawl_case_studies_jp,  "interval", hours=24)
scheduler.add_job(fetch_box_diff,         "interval", hours=1)
scheduler.add_job(run_clean_enrich_embed, "interval", hours=1)
```

---

### 3.6 REST API設計

`src/api/watson_news/routes.py` に以下のエンドポイントを追加:

| Method | Path | 説明 |
|---|---|---|
| `GET` | `/api/watson-news/articles` | 記事一覧取得（ページネーション・フィルタ対応） |
| `GET` | `/api/watson-news/articles/{id}` | 記事詳細取得（NLP解析結果込み） |
| `POST` | `/api/watson-news/search` | RAG検索（ニュース + Box文書 横断） |
| `GET` | `/api/watson-news/box/files` | Box文書一覧取得 |
| `GET` | `/api/watson-news/box/files/{file_id}` | Box文書詳細・チャンク一覧 |
| `GET` | `/api/watson-news/trends` | トレンドデータ取得 |
| `GET` | `/api/watson-news/alerts` | アラート一覧 |
| `POST` | `/api/watson-news/reports` | レポート生成リクエスト |

**検索エンドポイントのリクエスト例:**

```json
POST /api/watson-news/search
{
  "query": "IBMのAI戦略",
  "source_types": ["gdelt", "ibm_crawl", "box"],
  "date_from": "2026-01-01",
  "language": "ja",
  "top_k": 10
}
```

既存の Starlette ルーターに `watson_news_router` をマウントする:

```python
# main.py への追加
from api.watson_news.routes import watson_news_router
app.mount("/api/watson-news", watson_news_router)
```

---

## 4. フロントエンド実装方針

### 4.1 技術スタック

既存の Next.js + IBM Carbon Design System v11 を継続使用。
新規ライブラリは最小限にとどめる（`@carbon/charts` のみ追加予定）。

### 4.2 画面別実装優先順位（Phase 1）

1. **Search & Filter**（最優先）: ニュース + Box文書 横断RAG検索
2. **Article Detail**: ニュース記事のNLP解析結果表示
3. **Box Document View**: Box文書のチャンク・エンティティ表示
4. **Dashboard**: トップページ（静的なサマリーから始める）

Phase 2 以降:
5. Trend Analytics（`@carbon/charts` で時系列グラフ）
6. Alerts & Reports

### 4.3 Search & Filter の設計

```
┌─────────────────────────────────────────────────┐
│  検索バー（自然言語クエリ）           [検索]    │
├──────────────────┬──────────────────────────────┤
│  フィルタパネル  │  検索結果リスト               │
│                  │                               │
│  ソース種別      │  [ニュース記事カード]          │
│  ☑ GDELT         │   タイトル / ソース / 日付     │
│  ☑ IBM公式       │   要約 / センチメントバッジ    │
│  ☑ Box文書       │                               │
│                  │  [Box文書カード]               │
│  言語            │   ファイル名 / オーナー / 更新 │
│  ☑ 日本語        │   チャンクプレビュー           │
│  ☑ English       │                               │
│                  │  ...                           │
│  センチメント    │                               │
│  ○ すべて        │                               │
│  ○ ポジティブ    │                               │
│  ○ ニュートラル  │                               │
│  ○ ネガティブ    │                               │
│                  │                               │
│  日付範囲        │                               │
│  [from] [to]     │                               │
└──────────────────┴──────────────────────────────┘
```

### 4.4 状態管理

既存のパターンに合わせ React Context + SWR（`useSWR`）で実装。
グローバルストアは導入しない（過剰設計を避ける）。

---

## 5. データストア設計

### 5.1 OpenSearchインデックス

| インデックス名 | 用途 | 主要フィールド |
|---|---|---|
| `watson_news_raw` | Raw Layer（ニュース生データ） | id, url, title, body, source_type, crawled_at |
| `watson_news_clean` | Clean Layer（ニュース前処理済み） | id, url, clean_body, published, language, source_type |
| `watson_news_enriched` | Enriched Layer（ニュースAI解析済み） | id, summary, sentiment_label, entities, topic, vector, source_type |
| `watson_box_raw` | Raw Layer（Boxファイル） | id, box_file_id, filename, mimetype, updated_at |
| `watson_box_enriched` | Enriched Layer（Boxチャンク+ベクトル） | id, box_file_id, chunk_index, clean_text, entities, topic, vector |

ベクトルフィールドは OpenSearch の `knn_vector` 型を使用（既存設定を踏襲）。

### 5.2 インデックスマッピング（`watson_news_enriched` / `watson_box_enriched` 共通ベクトル設定）

```json
{
  "mappings": {
    "properties": {
      "vector": {
        "type": "knn_vector",
        "dimension": 768,
        "method": { "name": "hnsw", "engine": "faiss" }
      },
      "source_type": { "type": "keyword" },
      "language":    { "type": "keyword" },
      "published":   { "type": "date" },
      "entities":    { "type": "nested" }
    }
  }
}
```

ニュース・Box文書の **横断検索** は `source_type` フィルタの有無で制御し、
同一の knn_vector 空間でコサイン類似度検索を実行する。

---

## 6. 環境変数・設定

既存 `config/settings.py` に以下を追加:

```python
# Watson News — GDELT
GDELT_QUERY_KEYWORD   = os.getenv("GDELT_QUERY_KEYWORD", "IBM")
GDELT_MAX_RECORDS     = int(os.getenv("GDELT_MAX_RECORDS", "250"))

# Watson News — IBM公式サイト クローラ
IBM_CRAWL_INTERVAL_SECONDS = int(os.getenv("IBM_CRAWL_INTERVAL_SECONDS", "5"))
IBM_CRAWL_USER_AGENT       = os.getenv("IBM_CRAWL_USER_AGENT", "WatsonNewsBot/1.0")

# Watson News — Box
BOX_OAUTH_CLIENT_ID     = os.getenv("BOX_OAUTH_CLIENT_ID", "")
BOX_OAUTH_CLIENT_SECRET = os.getenv("BOX_OAUTH_CLIENT_SECRET", "")  # pragma: allowlist secret
BOX_TARGET_FOLDER_ID    = os.getenv("BOX_TARGET_FOLDER_ID", "0")    # 0 = ルート
BOX_TOKEN_FILE          = os.getenv("BOX_TOKEN_FILE", "box_token.json")

# Watson News — watsonx.ai
WATSONX_AI_URL            = os.getenv("WATSONX_AI_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_API_KEY           = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT_ID        = os.getenv("WATSONX_PROJECT_ID", "")
WATSON_NEWS_ENRICH_MODEL  = os.getenv("WATSON_NEWS_ENRICH_MODEL", "ibm/granite-13b-instruct-v2")
WATSON_NEWS_EMBED_MODEL   = os.getenv("WATSON_NEWS_EMBED_MODEL", "ibm/granite-embedding-125m-english")
```

`.env.example` に上記変数を追記する。

---

## 7. 依存パッケージ

`pyproject.toml` に以下を追加:

```toml
[project.dependencies]
# IBM公式サイト クローラ
beautifulsoup4 = ">=4.12"    # HTMLパース
httpx          = ">=0.27"    # 非同期HTTPクライアント（既存使用済み、バージョン確認のみ）
playwright     = ">=1.44"    # JavaScript レンダリングが必要なページ対応（オプション）

# Box コネクタ
boxsdk = ">=3.9"             # Box Python SDK（OAuth 2.0 サポート）

# 共通
html2text    = ">=2020.1"   # HTML→テキスト変換
apscheduler  = ">=3.10"     # 定期実行スケジューラ
ibm-watsonx-ai = ">=1.0"   # watsonx.ai SDK
langdetect   = ">=1.0"      # 言語検出
```

> **注意:** `playwright` は JavaScript レンダリングが必要な IBM ページのみで使用する。
> 静的 HTML で取得可能なページは `httpx` + `BeautifulSoup` のみで処理し、依存を最小化する。

フロントエンド（`package.json`）:

```json
"@carbon/charts": "^1.x",
"@carbon/charts-react": "^1.x"
```

---

## 8. テスト方針

- **ユニットテスト**: `cleaner.py`・`enricher.py`・差分検知ロジック・Box OAuth のトークンリフレッシュを単体でテスト
- **統合テスト**: GDELT API・IBM サイト・Box API への実際のHTTPリクエストはモック化（`respx`）
- **クローラテスト**: robots.txt 取得・`can_fetch()` 判定・インターバル確認
- **E2Eテスト**: Phase 2 以降で検討
- **カバレッジ目標**: 新規コード 80%以上

---

## 9. Phase 1 実装タスク詳細

### Week 1-2: 基盤構築

- [ ] `watson_news/` / `box/` ディレクトリ構造作成
- [ ] OpenSearch インデックスマッピング定義・作成スクリプト（5インデックス）
- [ ] 設定変数の追加（`config/settings.py`）
- [ ] 依存パッケージ追加（`pyproject.toml`）
- [ ] `.env.example` 更新

### Week 3-4: ETL（取得・クリーニング）

- [ ] `GdeltConnector` 実装
- [ ] `IbmCrawlConnector` 実装（差分検知・robots.txt 対応・7サイト設定）
- [ ] `BoxConnector` 実装（OAuth 2.0 認証・差分取得）
- [ ] `BoxOAuth` 実装（トークンキャッシュ・リフレッシュ）
- [ ] `cleaner.py` 実装（ニュース HTML除去 / Box docling テキスト抽出・チャンク分割）
- [ ] Raw Layer への保存実装
- [ ] ユニットテスト・クローラテスト作成

### Week 5-6: AI解析・Embedding

- [ ] `enricher.py` 実装（watsonx.ai 連携・ニュース/Box共通）
- [ ] Embedding パイプライン実装（既存 `document_service.py` 活用）
- [ ] OpenSearch への upsert 実装（ニュース / Box 各インデックス）
- [ ] バッチ処理・エラーハンドリング・レートリミット対応

### Week 7-8: スケジューラ・API

- [ ] `scheduler.py` 実装（APScheduler・9ジョブ）
- [ ] REST API エンドポイント実装（`routes.py`・8エンドポイント）
- [ ] Starlette へのルート登録

### Week 9-10: フロントエンド（MVP）

- [ ] Search & Filter 画面実装（ニュース + Box文書 横断検索・フィルタ）
- [ ] Article Detail 画面実装
- [ ] Box Document View 画面実装
- [ ] Dashboard（静的サマリー）実装

### Week 11-12: テスト・チューニング

- [ ] 統合テスト（全コネクタ・全APIエンドポイント）
- [ ] パフォーマンステスト（検索1秒以内を確認）
- [ ] クロール倫理テスト（robots.txt 遵守・インターバル確認）
- [ ] バグ修正・ドキュメント整備

---

## 10. リスクと対策

| リスク | 影響度 | 対策 |
|---|---|---|
| GDELT APIのレートリミット | 中 | 15分間隔での取得、エクスポネンシャルバックオフ |
| IBM公式サイトのHTML構造変更 | 中 | URLリスト抽出ロジックをサイト別に分離・アラートで検知 |
| IBM公式サイトのJavaScript依存 | 中 | `playwright` をフォールバックとして用意。静的取得可能なサイトは httpx 優先 |
| robots.txt による巡回禁止 | 低 | 事前確認済み。禁止になった場合はスキップ+ログ記録 |
| watsonx.ai APIのレイテンシ | 高 | バッチ処理化、非同期実行、結果キャッシュ |
| Box OAuthトークン期限切れ | 中 | refresh_token 自動更新・キャッシュファイル管理（OneDrive と同方式） |
| Box フォルダ権限変更 | 低 | アクセス拒否時はスキップ+ログ記録、ACL-aware search は Phase 3 で対応 |
| 記事の重複爆発 | 中 | URL正規化＋OpenSearch term クエリで排除 |
| 多言語記事のノイズ | 低 | `langdetect` で言語フィルタ（Phase 1は en/ja のみ） |
