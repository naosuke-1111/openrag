# Watson News (IBM版) — 実装方針書

> 作成日: 2026-02-21
> ブランチ: `claude/plan-implementation-strategy-zt707`
> 要件定義書: `watson-news/requirements.md`

---

## 1. 基本方針

### 1.1 openRAGの既存資産を最大活用する

Watson News は新規プロダクトを一から構築するのではなく、**openRAGの既存インフラ上に機能を積み上げる**形で実装する。

| openRAG既存資産 | Watson Newsでの活用 |
|---|---|
| `BaseConnector` | `GdeltConnector`・`IbmNewsConnector` を派生クラスとして実装 |
| Document Store（Langflow連携） | ニュース記事の取り込みパイプラインとして流用 |
| OpenSearch（ベクトルインデックス） | ニュース記事の Vector Index として活用 |
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
- 既存テストが壊れないことを CI で保証する

---

## 2. ディレクトリ構成

```
openrag/
├── src/
│   ├── connectors/
│   │   ├── watson_news/           ← 新規追加
│   │   │   ├── __init__.py
│   │   │   ├── gdelt_connector.py      # GDELT API取得
│   │   │   ├── ibm_news_connector.py   # IBM公式ニュース取得
│   │   │   ├── etl_pipeline.py         # ETLオーケストレーション
│   │   │   ├── cleaner.py              # HTMLタグ除去・重複排除
│   │   │   ├── enricher.py             # AI解析（要約・センチメント・エンティティ）
│   │   │   └── scheduler.py            # 定期実行スケジューラ
│   ├── api/
│   │   ├── watson_news/           ← 新規追加
│   │   │   ├── __init__.py
│   │   │   ├── routes.py               # REST APIルート定義
│   │   │   └── schemas.py              # Pydantic スキーマ
│   ├── models/
│   │   └── watson_news.py         ← 新規追加（データモデル）
│   └── services/
│       └── watson_news_service.py ← 新規追加
├── frontend/
│   └── src/
│       └── pages/
│           └── watson-news/       ← 新規追加
│               ├── index.tsx           # Dashboard
│               ├── search.tsx          # Search & Filter
│               ├── [id].tsx            # Article Detail
│               ├── trends.tsx          # Trend Analytics
│               └── alerts.tsx          # Alerts & Reports
├── watson-news/
│   ├── requirements.md            ← 要件定義書
│   └── implementation-strategy.md ← 本ファイル
└── tests/
    └── watson_news/               ← 新規追加
        ├── test_gdelt_connector.py
        ├── test_ibm_news_connector.py
        └── test_etl_pipeline.py
```

---

## 3. バックエンド実装方針

### 3.1 コネクタ設計

`BaseConnector` を継承し、既存の認証フレームワークに乗る形で実装する。
ただし GDELT は API Key 不要（公開API）のため、OAuth フローは不要。IBM公式ニュースは RSS のため同様。

```python
# src/connectors/watson_news/gdelt_connector.py の骨格
class GdeltConnector(BaseConnector):
    CONNECTOR_NAME = "gdelt_news"
    CONNECTOR_DESCRIPTION = "GDELT News Connector for IBM-related articles"

    async def fetch_articles(
        self,
        query: str = "IBM",
        max_records: int = 250,
        timespan: str = "15min"
    ) -> list[ConnectorDocument]:
        ...
```

**GDELT APIエンドポイント:**
```
https://api.gdeltproject.org/api/v2/doc/doc
  ?query=IBM&mode=ArtList&maxrecords=250&format=json&timespan=15min
```

**IBM公式ニュース RSSフィード:**
```
https://newsroom.ibm.com/rss/news-releases.htm
https://www.ibm.com/blogs/feed/
```

---

### 3.2 ETLパイプライン

```
fetch() → clean() → enrich() → embed() → index()
```

各ステップは独立した関数として実装し、単体テストを容易にする。

#### Step 1: fetch（取得）

- GDELT: HTTP GET → JSON パース → `ConnectorDocument` に変換
- IBM RSS: `feedparser` で XML パース → `ConnectorDocument` に変換
- 取得結果は Raw Layer（OpenSearch `news_raw` インデックス）に保存

#### Step 2: clean（クリーニング）

```python
# cleaner.py
def clean_article(doc: ConnectorDocument) -> NewsClean:
    body = html2text(doc.content.decode())    # HTML除去
    body = normalize_whitespace(body)          # 正規化
    if is_duplicate(doc.url):                  # URL重複チェック
        return None
    if not is_target_language(body):           # 言語フィルタ
        return None
    return NewsClean(...)
```

重複チェックは OpenSearch の URL フィールドに対する `term` クエリで実施。

#### Step 3: enrich（AI解析）

watsonx.ai Granite モデルを利用し、以下を並列実行:

| 処理 | モデル / 手法 | 出力 |
|---|---|---|
| 要約 | `ibm/granite-13b-instruct-v2` | `summary` (string) |
| センチメント分析 | `ibm/granite-13b-instruct-v2` | `sentiment_label`, `sentiment_score` |
| エンティティ抽出 | `ibm/granite-13b-instruct-v2` | `entities` (array) |
| トピック分類 | `ibm/granite-13b-instruct-v2` | `topic` (string) |

バッチサイズ: 10件/リクエスト、レートリミット対応あり。

#### Step 4: embed（ベクトル化）

既存 `document_service.py` の `chunk_texts_for_embeddings()` を再利用。

```python
from services.document_service import chunk_texts_for_embeddings

texts = [f"{article.title}\n{article.clean_body}" for article in articles]
batches = chunk_texts_for_embeddings(texts, max_tokens=8192)
```

Embedding モデル: `ibm/granite-embedding-125m-english`（watsonx.ai）

#### Step 5: index（インデックス更新）

OpenSearch の `news_enriched` インデックスへ upsert（`_id` = UUID）。
既存 `search_service.py` のインデックス操作ユーティリティを活用。

---

### 3.3 スケジューラ

`APScheduler` で定期実行を管理する（既存の `task_service.py` パターンに合わせる）。

```python
# scheduler.py
scheduler.add_job(fetch_gdelt, "interval", minutes=15)
scheduler.add_job(fetch_ibm_news, "interval", hours=1)
scheduler.add_job(run_clean_enrich_embed, "interval", hours=1)
```

---

### 3.4 REST API設計

`src/api/watson_news/routes.py` に以下のエンドポイントを追加:

| Method | Path | 説明 |
|---|---|---|
| `GET` | `/api/watson-news/articles` | 記事一覧取得（ページネーション・フィルタ対応） |
| `GET` | `/api/watson-news/articles/{id}` | 記事詳細取得（NLP解析結果込み） |
| `POST` | `/api/watson-news/search` | RAG検索（自然言語クエリ） |
| `GET` | `/api/watson-news/trends` | トレンドデータ取得 |
| `GET` | `/api/watson-news/alerts` | アラート一覧 |
| `POST` | `/api/watson-news/reports` | レポート生成リクエスト |

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

1. **Search & Filter**（最優先）: RAG検索の核心機能
2. **Article Detail**: 検索結果からドリルダウン
3. **Dashboard**: トップページ（静的なサマリーから始める）

Phase 2 以降:
4. Trend Analytics（`@carbon/charts` で時系列グラフ）
5. Alerts & Reports

### 4.3 状態管理

既存のパターンに合わせ React Context + SWR（`useSWR`）で実装。
グローバルストアは導入しない（過剰設計を避ける）。

---

## 5. データストア設計

### 5.1 OpenSearchインデックス

| インデックス名 | 用途 | 主要フィールド |
|---|---|---|
| `watson_news_raw` | Raw Layer（取得生データ） | id, url, title, body, source_type, seendate |
| `watson_news_clean` | Clean Layer（前処理済み） | id, url, clean_body, published, language |
| `watson_news_enriched` | Enriched Layer（AI解析済み） | id, summary, sentiment_label, entities, topic, vector |

ベクトルフィールドは OpenSearch の `knn_vector` 型を使用（既存設定を踏襲）。

### 5.2 インデックスマッピング（`watson_news_enriched` 抜粋）

```json
{
  "mappings": {
    "properties": {
      "vector": {
        "type": "knn_vector",
        "dimension": 768,
        "method": { "name": "hnsw", "engine": "faiss" }
      },
      "sentiment_score": { "type": "float" },
      "published": { "type": "date" },
      "entities": { "type": "nested" }
    }
  }
}
```

---

## 6. 環境変数・設定

既存 `config/settings.py` に以下を追加:

```python
# Watson News 設定
GDELT_QUERY_KEYWORD = os.getenv("GDELT_QUERY_KEYWORD", "IBM")
GDELT_MAX_RECORDS = int(os.getenv("GDELT_MAX_RECORDS", "250"))
IBM_NEWS_RSS_URLS = os.getenv("IBM_NEWS_RSS_URLS", "https://newsroom.ibm.com/rss/news-releases.htm")
WATSONX_AI_URL = os.getenv("WATSONX_AI_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_API_KEY = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
WATSON_NEWS_ENRICH_MODEL = os.getenv("WATSON_NEWS_ENRICH_MODEL", "ibm/granite-13b-instruct-v2")
WATSON_NEWS_EMBED_MODEL = os.getenv("WATSON_NEWS_EMBED_MODEL", "ibm/granite-embedding-125m-english")
```

`.env.example` に上記変数を追記する。

---

## 7. 依存パッケージ

`pyproject.toml` に以下を追加:

```toml
[project.dependencies]
feedparser = ">=6.0"       # IBM RSS パース
html2text = ">=2020.1"     # HTML→テキスト変換
apscheduler = ">=3.10"     # 定期実行スケジューラ
ibm-watsonx-ai = ">=1.0"  # watsonx.ai SDK
langdetect = ">=1.0"       # 言語検出
```

フロントエンド（`package.json`）:

```json
"@carbon/charts": "^1.x",
"@carbon/charts-react": "^1.x"
```

---

## 8. テスト方針

- **ユニットテスト**: `cleaner.py`・`enricher.py` の各関数を単体でテスト
- **統合テスト**: GDELT API / IBM RSS への実際のHTTPリクエストはモック化（`respx`）
- **E2Eテスト**: Phase 2 以降で検討
- **カバレッジ目標**: 新規コード 80%以上

---

## 9. Phase 1 実装タスク詳細

### Week 1-2: 基盤構築

- [ ] `watson_news/` ディレクトリ構造作成
- [ ] OpenSearch インデックスマッピング定義・作成スクリプト
- [ ] 設定変数の追加（`config/settings.py`）
- [ ] 依存パッケージ追加（`pyproject.toml`）

### Week 3-4: ETL（取得・クリーニング）

- [ ] `GdeltConnector` 実装
- [ ] `IbmNewsConnector` 実装
- [ ] `cleaner.py` 実装（HTML除去・重複排除・言語フィルタ）
- [ ] Raw Layer への保存実装
- [ ] ユニットテスト作成

### Week 5-6: AI解析・Embedding

- [ ] `enricher.py` 実装（watsonx.ai 連携）
- [ ] Embedding パイプライン実装（既存 `document_service.py` 活用）
- [ ] OpenSearch への upsert 実装
- [ ] バッチ処理・エラーハンドリング

### Week 7-8: スケジューラ・API

- [ ] `scheduler.py` 実装（APScheduler）
- [ ] REST API エンドポイント実装（`routes.py`）
- [ ] Starlette へのルート登録

### Week 9-10: フロントエンド（MVP）

- [ ] Search & Filter 画面実装
- [ ] Article Detail 画面実装
- [ ] Dashboard（静的サマリー）実装

### Week 11-12: テスト・チューニング

- [ ] 統合テスト
- [ ] パフォーマンステスト（検索1秒以内を確認）
- [ ] バグ修正・ドキュメント整備

---

## 10. リスクと対策

| リスク | 影響度 | 対策 |
|---|---|---|
| GDELT APIのレートリミット | 中 | 15分間隔での取得、エラー時はエクスポネンシャルバックオフ |
| watsonx.ai APIのレイテンシ | 高 | バッチ処理化、非同期実行、結果キャッシュ |
| IBM RSSフォーマット変更 | 低 | `feedparser` の標準パーサーで吸収、異常時アラート |
| 記事の重複爆発 | 中 | URL正規化＋OpenSearch term クエリで排除 |
| 多言語記事のノイズ | 低 | `langdetect` で言語フィルタ（Phase 1は en/ja のみ） |
