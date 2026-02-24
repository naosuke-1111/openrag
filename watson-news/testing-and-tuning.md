# Watson News — テスト・チューニング 実装記録（Week 11-12）

> 作成日: 2026-02-24
> ブランチ: `claude/watson-news-frontend-mvp-HcjMG`
> 対象タスク: `implementation-strategy.md` § Week 11-12 テスト・チューニング

---

## 実装概要

Week 9-10 で完成したフロントエンド MVP に続き、Week 11-12 では以下を実施した。

| 内容 | 結果 |
|---|---|
| バックエンド単体テスト全通過 | **46 tests passed** |
| REST API 統合テスト追加 | `test_api_routes.py`（19 tests） |
| クロール倫理テスト追加 | `test_crawler_ethics.py`（10 tests） |
| フロントエンドフックの実 API 接続 | `use-watson-news.ts` をモックから `fetch()` に置き換え |

---

## 作成・変更ファイル一覧

### バックエンドテスト

| ファイル | 説明 |
|---|---|
| `conftest.py`（プロジェクトルート） | torch / langdetect / docling などの重量パッケージをスタブ化。CI環境で依存なしに実行可能にする |
| `tests/watson_news/conftest.py` | langdetect スタブ適用 + `onboard_system` autouse フィクスチャを no-op で上書き（Langflow 依存を回避） |
| `tests/watson_news/test_api_routes.py` | 全 REST API エンドポイントの統合テスト（19 テスト）|
| `tests/watson_news/test_crawler_ethics.py` | robots.txt 遵守・インターバル確認のクロール倫理テスト（10 テスト） |

### フロントエンドフック

| ファイル | 変更内容 |
|---|---|
| `frontend/app/watson-news/_hooks/use-watson-news.ts` | `setTimeout` + モックデータ → 実 API `fetch()` 呼び出しに全面置き換え |

---

## バックエンドテスト詳細

### テストファイル構成（`tests/watson_news/`）

```
tests/
├── conftest.py                     ← ルート: 重量パッケージのスタブ定義
└── watson_news/
    ├── conftest.py                 ← Langflow 依存の無効化
    ├── test_api_routes.py          ← REST API 統合テスト (19)
    ├── test_box_connector.py       ← Box コネクタ単体テスト
    ├── test_cleaner.py             ← HTML クリーニング単体テスト
    ├── test_crawler_ethics.py      ← クロール倫理テスト (10)
    ├── test_etl_pipeline.py        ← ETL パイプライン単体テスト
    ├── test_gdelt_connector.py     ← GDELT コネクタ単体テスト
    └── test_ibm_crawl_connector.py ← IBM クローラ単体テスト
```

### test_api_routes.py — REST API 統合テスト（19 テスト）

Starlette `TestClient` + `unittest.mock.AsyncMock` でサービス層をモックし、
外部サービス（OpenSearch・watsonx.ai）不要で REST ルートのリクエスト/レスポンスを検証する。

| テストクラス | 検証内容 |
|---|---|
| `TestGetArticles` | 記事一覧取得・クエリパラメータ反映・空リスト返却 |
| `TestGetArticleDetail` | 記事詳細取得・404 ハンドリング |
| `TestSearchArticles` | POST 検索・フィルタパラメータ渡し・不正 JSON エラー |
| `TestGetBoxFiles` | Box ファイル一覧取得 |
| `TestGetBoxFileDetail` | Box ファイル詳細取得・404 ハンドリング |
| `TestGetTrendData` | トレンドデータ取得・空トレンド返却 |
| `TestEtlStatus` | ETL ステータス取得 |
| `TestEtlTrigger` | ETL トリガー POST・レスポンス検証 |

### test_crawler_ethics.py — クロール倫理テスト（10 テスト）

IBM 公式サイトクローラーが倫理要件を満たすことを `respx` で HTTP をモックして検証する。

| テスト名 | 検証内容 |
|---|---|
| `test_allows_url_when_robots_txt_permits` | `Disallow` 対象外 URL は許可される |
| `test_blocks_url_when_robots_txt_disallows` | `Disallow` 対象 URL はスキップされる |
| `test_allows_all_when_robots_txt_returns_non_200` | robots.txt が 404 → fail-open（許可） |
| `test_allows_all_when_robots_txt_fetch_fails` | robots.txt 取得失敗 → fail-open（許可） |
| `test_caches_robots_txt_and_does_not_refetch` | 2回目のアクセスはキャッシュを使い再取得しない |
| `test_skips_disallowed_urls` | 禁止 URL を含む記事リストを処理するとスキップされる |
| `test_crawls_allowed_urls` | 許可 URL は実際にクロールされる |
| `test_skips_robots_check_when_disabled` | `respect_robots_txt=False` なら robots.txt をチェックしない |
| `test_respects_request_interval_between_articles` | `asyncio.sleep` が記事ごとに呼ばれる |
| `test_known_urls_are_skipped` | 既知 URL は差分検知でスキップされる |

---

## バックエンドテスト実行方法

### 1. 事前準備

```bash
# プロジェクトルートに移動
cd /home/user/openrag

# 依存パッケージをインストール（初回のみ）
pip install pytest pytest-asyncio pytest-mock respx starlette httpx structlog aiofiles msal opensearch-py python-dotenv agentd
```

> **注意:** `torch`・`langdetect`・`docling` はビルドが重いためインストール不要。
> ルートの `conftest.py` がスタブを自動注入するため CI 環境でもそのまま動作する。

### 2. 全テスト実行

```bash
# プロジェクトルートで実行
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/ -v
```

**期待結果:**

```
===================== 46 passed in X.XXs =====================
```

### 3. テスト種別ごとの実行

```bash
# REST API 統合テストのみ
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/test_api_routes.py -v

# クロール倫理テストのみ
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/test_crawler_ethics.py -v

# GDELT コネクタのみ
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/test_gdelt_connector.py -v

# IBM クローラのみ
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/test_ibm_crawl_connector.py -v

# ETL パイプラインのみ
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/test_etl_pipeline.py -v
```

### 4. カバレッジ計測

```bash
pip install pytest-cov

PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/ \
  --cov=connectors.watson_news \
  --cov=api.watson_news \
  --cov=models.watson_news \
  --cov-report=term-missing
```

**目標:** 新規コード 80% 以上

### 5. テスト収集確認（実行せずにテスト一覧を確認）

```bash
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/ --collect-only -q
```

---

## フロントエンドフック — 実 API 接続

### 変更概要

`frontend/app/watson-news/_hooks/use-watson-news.ts` のすべてのフックを
`setTimeout` + モックデータ方式から実バックエンド API への `fetch()` 呼び出しに置き換えた。

| フック | 変更前 | 変更後 |
|---|---|---|
| `useDashboardStats` | `setTimeout` + ハードコード値 | `/api/watson-news/articles`・`/box/files`・`/trends` への並列 fetch でリアルタイム集計 |
| `useWatsonNewsSearch` | `setTimeout` + ローカルフィルタ | `POST /api/watson-news/search` にフィルタ条件を送信 |
| `useArticleDetail` | `setTimeout` + 配列検索 | `GET /api/watson-news/articles/{id}` |
| `useBoxDocumentDetail` | `setTimeout` + 配列検索 | `GET /api/watson-news/box/files/{file_id}` |

### 追加した変換ヘルパー

バックエンドのレスポンス（`Record<string, unknown>`）をフロントエンドの型（`NewsArticle` / `BoxDocument`）に安全に変換する。

```typescript
// バックエンドレスポンス → NewsArticle 型
function toNewsArticle(hit: Record<string, unknown>): NewsArticle

// バックエンドレスポンス → BoxDocument 型
function toBoxDocument(raw: Record<string, unknown>): BoxDocument
```

### キャンセルフラグによる安全なクリーンアップ

`useEffect` 内で `cancelled` フラグを使い、コンポーネントアンマウント後の state 更新を防止する。

```typescript
useEffect(() => {
  let cancelled = false;
  async function fetch() {
    const data = await ...;
    if (!cancelled) setState(data);  // アンマウント後は無視
  }
  fetch();
  return () => { cancelled = true; };
}, [id]);
```

---

## フロントエンドテスト実行方法（実 API 接続後）

バックエンドを起動した状態で以下の URL にアクセスし動作を確認する。

### 1. 事前準備

```bash
# バックエンドを起動（別ターミナル）
cd /home/user/openrag
python -m uvicorn main:app --reload

# フロントエンド開発サーバーを起動
cd frontend
npm install   # 初回のみ
npm run dev
```

### 2. Dashboard（`/watson-news`）— 実データ確認

| 確認項目 | 期待動作 |
|---|---|
| ページ読み込み時にローディング表示 | スケルトンまたはスピナーが表示される |
| 統計カードに実データが表示される | OpenSearch のインデックス件数が反映される |
| トピック・エンティティランキングが表示される | `/api/watson-news/trends` のデータが反映される |
| バックエンド未起動の場合 | エラーメッセージが表示される（クラッシュしない） |

### 3. Search & Filter（`/watson-news/search`）— 実 API 検索

| 確認項目 | 期待動作 |
|---|---|
| 検索バーに入力して Enter | `POST /api/watson-news/search` が呼ばれる |
| ネットワークタブで確認 | リクエストボディにクエリ・フィルタが含まれる |
| 検索結果が表示される | バックエンドの OpenSearch 検索結果が表示される |
| フィルタを変更して再検索 | フィルタ条件が API に正しく渡される |
| 検索結果 0 件 | 「結果が見つかりませんでした」と表示される |

### 4. Article Detail（`/watson-news/{id}`）— 実データ確認

| 確認項目 | 期待動作 |
|---|---|
| 実在する記事 ID でアクセス | `GET /api/watson-news/articles/{id}` が呼ばれ記事が表示される |
| 存在しない ID でアクセス | 404 エラーメッセージ「記事が見つかりませんでした」が表示される |
| エンティティ・センチメントが表示される | AI 解析結果が反映される |

### 5. Box Document View（`/watson-news/box/{fileId}`）— 実データ確認

| 確認項目 | 期待動作 |
|---|---|
| 実在する Box File ID でアクセス | `GET /api/watson-news/box/files/{file_id}` が呼ばれ文書が表示される |
| 存在しない ID でアクセス | 404 エラーメッセージ「Box文書が見つかりませんでした」が表示される |
| チャンク一覧が表示される | OpenSearch に保存されたチャンクデータが表示される |

### 6. 型チェック・リント・ビルド

```bash
cd frontend

# TypeScript 型チェック
npx tsc --noEmit

# リント・フォーマット
npm run check-format
npm run lint

# プロダクションビルド
npm run build
```

**期待結果:** `npm run build` が成功し、以下のルートが含まれること

```
○ /watson-news
○ /watson-news/search
○ /watson-news/[id]
○ /watson-news/box/[fileId]
```

---

## トラブルシューティング

### `No module named 'torch'` / `'langdetect'` / `'docling'`

CI・開発環境でインストール不要。ルートの `conftest.py` が自動スタブ化する。
もし pytest が `conftest.py` を読み込まずにエラーが出る場合は以下を確認:

```bash
# conftest.py がプロジェクトルートにあるか確認
ls /home/user/openrag/conftest.py

# プロジェクトルートから pytest を実行しているか確認
cd /home/user/openrag
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/ -v
```

### `LangflowNotReadyError` が出る

`tests/watson_news/conftest.py` の `onboard_system` no-op フィクスチャが
ルートの autouse フィクスチャより先に読み込まれていない可能性がある。

```bash
# フィクスチャの適用確認
PYTHONPATH=/home/user/openrag/src python -m pytest tests/watson_news/ --fixtures -v | grep onboard
```

### respx でモックが効かない

テスト内の HTTP モックに `with respx.mock():` コンテキストマネージャではなく
`@respx.mock` デコレーターを使うこと。

```python
# NG（コンテキストマネージャ内のルートが有効にならない場合がある）
def test_example():
    with respx.mock:
        respx.get("https://example.com").mock(...)

# OK（デコレーターを使う）
@respx.mock
def test_example():
    respx.get("https://example.com").mock(...)
```

---

## 残タスク（バックエンド接続後に実施）

- [ ] パフォーマンステスト（検索レイテンシ 1 秒以内を確認）
- [ ] E2E テスト（Playwright）— 実バックエンド接続後に導入
- [ ] フロントエンドのページネーション対応（検索結果・記事一覧）
- [ ] Trend Analytics 画面（`/watson-news/trends`）実装
- [ ] Alerts & Reports 画面（`/watson-news/alerts`）実装
