# Watson News (IBM版) — 要件定義書

> 作成日: 2026-02-21
> 最終更新: 2026-02-21
> ブランチ: `claude/plan-implementation-strategy-zt707`

---

## 1. プロダクト概要

IBM向けニュース自動収集・AI解析・RAG検索プラットフォーム。
GDELT・IBM公式サイトのクローリング・**Box社内ドキュメント**を統合し、watsonx.ai + openRAG による高度なインテリジェント検索を提供する。

### 1.1 主要機能

| 機能カテゴリ | 詳細 |
|---|---|
| ニュース収集 | GDELT API、IBM公式サイト クローリング（7サイト） |
| 社内文書取り込み | Box ファイル Embedding（PDF・Word・Excel・PowerPoint 等） |
| AI解析 | 要約（LLM）、センチメント分析、エンティティ抽出、トピック分類 |
| トレンド分析 | 時系列トレンド検出、異常検知 |
| 競合比較 | 他社ニュースとの比較分析 |
| レポート生成 | 自動レポート（PDF / HTML） |
| RAG検索 | openRAG + watsonx.ai Granite による自然言語検索（ニュース＋社内文書を横断） |

---

## 2. データソース定義

### 2.1 GDELT（外部ニュース）

GDELT 2.0 API で `IBM` に言及する外部メディア記事をリアルタイム取得。

```
https://api.gdeltproject.org/api/v2/doc/doc
  ?query=IBM&mode=ArtList&maxrecords=250&format=json&timespan=15min
```

### 2.2 IBM公式サイト クローリング（Webクローラ方式）

RSS フィードは提供されていないため、以下の**インデックスページを定期巡回し、新規記事URLを検出**した上で本文クロールを行う。

| サイト | URL | クロール対象 | 頻度 |
|---|---|---|---|
| IBM Announcements | `https://www.ibm.com/new/announcements` | 製品・サービスの新着発表 | 毎2時間 |
| IBM Research Blog | `https://research.ibm.com/blog` | 研究・技術ブログ | 毎4時間 |
| IBM Newsroom | `https://newsroom.ibm.com/announcements` | プレスリリース | 毎2時間 |
| IBM Annual Report | `https://www.ibm.com/investor/services/annual-report` | 投資家向け年次報告 | 毎日 |
| IBM Case Studies (Global) | `https://www.ibm.com/case-studies?lnk=flatitem` | 導入事例（英語） | 毎日 |
| IBM Think Insights (JP) | `https://www.ibm.com/jp-ja/think/insights` | 日本語インサイト記事 | 毎4時間 |
| IBM Case Studies (JP) | `https://www.ibm.com/case-studies/jp-ja/` | 導入事例（日本語） | 毎日 |

**新規記事検出の仕組み:**

1. インデックスページを取得し、掲載記事URLリストを抽出する
2. OpenSearch 既知URLセット（`watson_news_raw` インデックス）と差分を計算する
3. 差分（新規URL）のみ本文クロールを実行する
4. robots.txt を遵守し、クロール間隔はサイトごとに制御する

### 2.3 Box 社内ドキュメント

Box OAuth 2.0 / JWT 認証を用いて指定フォルダ配下のファイルを定期取得し、Embedding・ベクトルインデックスへ登録する。

**対象ファイル種別:**

| 種別 | MIME Type |
|---|---|
| PDF | `application/pdf` |
| Word | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| PowerPoint | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| Excel | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| テキスト | `text/plain` |

**差分検知:**
Box API の `updated_at` フィールドを保存し、前回取得時刻以降に更新されたファイルのみを再処理する。

---

## 3. データ統合スキーマ

### 3.1 Raw Layer

#### `news_raw_gdelt` — GDELT取得データ

| カラム | 型 | 説明 |
|---|---|---|
| id | string (UUID) | 一意識別子 |
| title | string | 記事タイトル |
| url | string | 記事URL |
| body | string | 本文（HTML含む） |
| domain | string | メディアドメイン名 |
| seendate | timestamp | GDELT検知日時 |
| language | string | 言語コード (ISO 639-1) |
| tone | float | GDELTトーンスコア |
| socialimage | string | 代表画像URL |
| source_type | string | 固定値: `"gdelt"` |

#### `news_raw_ibm` — IBM公式サイト クロールデータ

| カラム | 型 | 説明 |
|---|---|---|
| id | string (UUID) | 一意識別子 |
| title | string | 記事タイトル |
| url | string | クロール元URL |
| body | string | 本文（HTML） |
| domain | string | 固定値: `"ibm.com"` |
| crawled_at | timestamp | クロール実行日時 |
| site_category | string | サイト種別（`announcements` / `research` / `newsroom` / `annual_report` / `case_study` / `insights`） |
| language | string | 言語コード（`en` / `ja`） |
| source_type | string | 固定値: `"ibm_crawl"` |

#### `box_raw` — Box ドキュメントデータ

| カラム | 型 | 説明 |
|---|---|---|
| id | string (UUID) | 一意識別子（openRAG内） |
| box_file_id | string | Box ファイルID |
| box_folder_id | string | Box フォルダID |
| filename | string | ファイル名 |
| mimetype | string | MIMEタイプ |
| content | bytes | ファイルバイナリ |
| owner | string | ファイルオーナー（Box ユーザーID） |
| box_url | string | Box 共有リンクURL |
| updated_at | timestamp | Box 上の最終更新日時 |
| fetched_at | timestamp | 取得日時 |
| source_type | string | 固定値: `"box"` |

#### `news_raw` — 統合ビュー（ニュース系）

```sql
CREATE VIEW news_raw AS
  SELECT * FROM news_raw_gdelt
  UNION ALL
  SELECT * FROM news_raw_ibm;
```

---

### 3.2 Clean Layer

#### `news_clean` — ニュース前処理済みデータ

**処理内容:**
- HTMLタグ除去（`html2text`）
- 重複排除（URL ベースの deduplication）
- 言語フィルタ（対象言語: `en`, `ja`）
- 本文正規化（空白・改行の統一）

| カラム | 型 | 説明 |
|---|---|---|
| id | string (UUID) | 一意識別子 |
| title | string | タイトル |
| clean_body | string | 整形済み本文 |
| url | string | URL |
| domain | string | メディア名 |
| published | timestamp | 公開日時（クロール日時で代替） |
| language | string | 言語コード |
| source_type | string | `gdelt` / `ibm_crawl` |

#### `box_clean` — Box ドキュメント前処理済みデータ

**処理内容:**
- PDF・Office ファイルのテキスト抽出（docling / pdfminer）
- 長文のチャンク分割（8,192 トークン以内）
- メタデータ付与

| カラム | 型 | 説明 |
|---|---|---|
| id | string (UUID) | 一意識別子（チャンク単位） |
| box_file_id | string | 元ファイルの Box ID |
| chunk_index | int | チャンク連番 |
| clean_text | string | 抽出テキスト |
| filename | string | ファイル名 |
| owner | string | オーナー |
| updated_at | timestamp | 最終更新日時 |
| source_type | string | 固定値: `"box"` |

---

### 3.3 Enriched Layer — AI解析済みデータ

#### `news_enriched`

| カラム | 型 | 説明 |
|---|---|---|
| id | string (UUID) | 一意識別子 |
| title | string | タイトル |
| clean_body | string | 本文 |
| summary | string | 要約（LLM生成） |
| sentiment_label | string | `Positive` / `Neutral` / `Negative` |
| sentiment_score | float | -1.0〜1.0 |
| entities | array\<struct\> | 抽出エンティティ（名前・種別・信頼度） |
| topic | string | トピック分類ラベル |
| vector | array\<float\> | 埋め込みベクトル（Granite Embedding） |
| domain | string | メディア名 |
| published | timestamp | 公開日時 |
| source_type | string | `gdelt` / `ibm_crawl` |

#### `box_enriched`

| カラム | 型 | 説明 |
|---|---|---|
| id | string (UUID) | 一意識別子（チャンク単位） |
| box_file_id | string | 元ファイルの Box ID |
| chunk_index | int | チャンク連番 |
| clean_text | string | テキスト |
| summary | string | チャンク要約（LLM生成） |
| entities | array\<struct\> | 抽出エンティティ |
| topic | string | トピック分類 |
| vector | array\<float\> | 埋め込みベクトル |
| filename | string | ファイル名 |
| owner | string | オーナー |
| updated_at | timestamp | 最終更新日時 |
| source_type | string | 固定値: `"box"` |

**エンティティ struct 定義:**

```json
{
  "text": "IBM",
  "type": "ORG",
  "confidence": 0.98
}
```

---

## 4. システムアーキテクチャ

### 4.1 データフロー

```
┌─────────────────────────────────────────────┐
│              データ収集レイヤー               │
│                                             │
│  GDELT API          IBM公式サイト            │
│  (15分間隔)          クローリング（7サイト）   │
│                      (2〜24時間間隔)          │
│                                             │
│             Box（社内文書）                  │
│              (差分検知・毎時)                 │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│            ETLパイプライン（Python）          │
│  fetch → crawl/diff → clean → enrich        │
│                    → embed → index           │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│         openRAG Document Store              │
│       OpenSearch（Raw / Clean / Enriched）   │
│       + knn_vector インデックス               │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│     RAG Query Engine（watsonx.ai Granite）   │
│  ニュース記事 × Box文書 横断検索             │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│     UI（React + IBM Carbon Design System）   │
└─────────────────────────────────────────────┘
```

### 4.2 openRAGとの統合ポイント

現行 openRAG は以下の機能を持つ:
- Document Store（OpenSearch ベース）
- OpenSearch によるベクトルインデックス（knn_vector）
- Langflow によるドキュメント取り込み・検索ワークフロー
- 既存コネクタ: Google Drive / OneDrive / SharePoint（OAuth 2.0 ベース）
- `document_service.py`：Embedding・チャンク処理ユーティリティ
- `search_service.py`：RAG検索クエリエンジン
- Starlette バックエンド + Next.js フロントエンド

Watson News は openRAG の既存インフラを拡張活用する。
特に **Box コネクタは OneDrive / SharePoint と同様のパターン**（`BaseConnector` 継承 + OAuth 2.0）で実装する。

---

## 5. ETLフロー詳細

| ステップ | 処理内容 | 頻度 |
|---|---|---|
| 1. GDELT取得 | GDELT 2.0 API で `IBM` 関連記事を取得 | 毎15分 |
| 2. IBM公式サイト巡回 | 7インデックスページを巡回し新規URLを検出 | サイト別（2〜24時間） |
| 3. IBM記事クロール | 差分URLのみ本文クロールを実行 | ステップ2完了後即時 |
| 4. Box差分取得 | Box APIで更新ファイルを取得 | 毎時 |
| 5. Document Store保存 | Raw データを OpenSearch へ保存 | 各ステップ完了後即時 |
| 6. クリーニング | HTMLタグ除去・重複排除・テキスト抽出・正規化 | バッチ（毎時） |
| 7. AI解析 | 要約・センチメント・エンティティ・トピック分類 | バッチ（毎時） |
| 8. Embedding | Granite Embedding でベクトル化 | バッチ（毎時） |
| 9. Vector Index更新 | OpenSearch knn_vector インデックスへ upsert | バッチ（毎時） |

---

## 6. UI要件

### 6.1 画面一覧

| 画面 | 概要 |
|---|---|
| Dashboard | 最新ニュースの概要・センチメントサマリー・トレンドスナップショット |
| Search & Filter | 自然言語 RAG 検索 + フィルタ（日付・ソース・言語・センチメント・ニュース/Box文書切替） |
| Article Detail | 記事本文 + NLP 解析結果（要約・エンティティ・センチメント・トピック） |
| Box Document View | Box文書の内容・チャンク・エンティティ・参照元リンク |
| Trend Analytics | 時系列グラフ・トピックトレンド・異常検知アラート |
| Alerts & Reports | アラート一覧・自動レポート生成・ダウンロード |

### 6.2 デザイン要件

- **デザインシステム:** IBM Carbon Design System v11
- **レイアウト:** 12カラムグリッド
- **コンポーネント:** カードUI、データテーブル、チャート
- **カラースキーム:** IBM Blue (#0f62fe)・White・Gray スケール
- **レスポンシブ:** ブレークポイント sm/md/lg/xlg 対応

---

## 7. 非機能要件

| 要件 | 目標値 |
|---|---|
| 検索レスポンス | 1秒以内（P95） |
| トレンド分析表示 | 3秒以内（P95） |
| ベクトル検索スケール | 100万件以上のインデックス対応 |
| データ鮮度（GDELT） | 取得から検索可能まで最大30分 |
| データ鮮度（IBM公式） | 記事公開から検索可能まで最大3時間 |
| データ鮮度（Box） | ファイル更新から検索可能まで最大2時間 |
| クロール倫理 | robots.txt 遵守・リクエスト間隔 ≥ 5秒 |
| セキュリティ | IAM認証、通信TLS暗号化、保存データ暗号化、Box OAuth スコープ最小化 |
| 監査ログ | 全検索・分析・Box アクセス操作のログ記録（90日保持） |
| 可用性 | 99.5%以上（月次） |

---

## 8. KPI

### 8.1 プロダクトKPI

| KPI | 測定方法 |
|---|---|
| 検索利用回数 | 月次クエリ数（ニュース/Box別） |
| トレンド分析利用回数 | 月次ページビュー |
| アラートクリック率 | CTR (クリック数 / 表示数) |
| レポート生成数 | 月次生成件数 |
| Box文書ヒット率 | 全検索結果に占めるBox文書の割合 |

### 8.2 ビジネスKPI

| KPI | 測定方法 |
|---|---|
| 契約社数 | 累計契約企業数 |
| MAU | 月次アクティブユーザー数 |
| 継続率 | 月次チャーン率の逆数 |

---

## 9. ロードマップ

### Phase 1（〜3ヶ月）— MVP

- [ ] GDELT ingestion パイプライン実装
- [ ] IBM公式サイト クローラ実装（7サイト・差分検知）
- [ ] Box コネクタ実装（OAuth 2.0 + 差分取得）
- [ ] openRAG Document Store 連携
- [ ] Embedding & Vector Index 構築（ニュース + Box文書の横断インデックス）
- [ ] 基本検索UI（Search & Filter, Article Detail, Box Document View）

### Phase 2（〜6ヶ月）— 機能拡張

- [ ] トレンド分析ダッシュボード
- [ ] アラート機能
- [ ] 自動レポート生成

### Phase 3（〜9ヶ月）— 高度化

- [ ] 競合比較機能
- [ ] 多言語対応（ja / zh / de / fr）
- [ ] 高度RAG（再ランキング・要約生成・ハイブリッド検索）
- [ ] Box フォルダ権限連動アクセス制御（ACL-aware search）
