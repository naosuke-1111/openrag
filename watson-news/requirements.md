# Watson News (IBM版) — 要件定義書

> 作成日: 2026-02-21
> ブランチ: `claude/plan-implementation-strategy-zt707`

---

## 1. プロダクト概要

IBM向けニュース自動収集・AI解析・RAG検索プラットフォーム。
GDELT と IBM公式ニュースを統合し、watsonx.ai + openRAG による高度なインテリジェント検索を提供する。

### 1.1 主要機能

| 機能カテゴリ | 詳細 |
|---|---|
| ニュース収集 | GDELT API、IBM公式ニュース（RSS / クローラ） |
| AI解析 | 要約（LLM）、センチメント分析、エンティティ抽出、トピック分類 |
| トレンド分析 | 時系列トレンド検出、異常検知 |
| 競合比較 | 他社ニュースとの比較分析 |
| レポート生成 | 自動レポート（PDF / HTML） |
| RAG検索 | openRAG + watsonx.ai Granite による自然言語検索 |

---

## 2. データ統合スキーマ

### 2.1 Raw Layer

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

#### `news_raw_ibm` — IBM公式ニュースデータ

| カラム | 型 | 説明 |
|---|---|---|
| id | string (UUID) | 一意識別子 |
| title | string | 記事タイトル |
| url | string | IBM公式ニュースURL |
| body | string | 本文 |
| domain | string | 固定値: `"ibm.com"` |
| published | timestamp | 公開日時 |
| category | string | IBMニュースカテゴリ |
| language | string | 言語コード |
| source_type | string | 固定値: `"ibm_official"` |

#### `news_raw` — 統合ビュー

```sql
CREATE VIEW news_raw AS
  SELECT * FROM news_raw_gdelt
  UNION ALL
  SELECT * FROM news_raw_ibm;
```

---

### 2.2 Clean Layer

#### `news_clean` — 前処理済みデータ

**処理内容:**
- HTMLタグ除去（BeautifulSoup / html2text）
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
| published | timestamp | 公開日時 |
| language | string | 言語コード |
| source_type | string | `gdelt` / `ibm_official` |

---

### 2.3 Enriched Layer — AI解析済みデータ

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
| source_type | string | `gdelt` / `ibm_official` |

**エンティティ struct 定義:**

```json
{
  "text": "IBM",
  "type": "ORG",
  "confidence": 0.98
}
```

---

## 3. システムアーキテクチャ

### 3.1 データフロー

```
GDELT API
IBM公式ニュース（RSS / クローラ）
        ↓
ETL（Python）
        ↓
openRAG Document Store（JSON / Parquet / S3互換）
        ↓
Embedding Pipeline（Granite Embedding）
        ↓
Vector Index（FAISS / Milvus / Chroma）
        ↓
RAG Query Engine（watsonx.ai Granite）
        ↓
UI（React + IBM Carbon Design System）
```

### 3.2 openRAGとの統合ポイント

現行 openRAG は以下の機能を持つ:
- Document Store（JSON / Parquet ベース）
- OpenSearch によるベクトルインデックス
- Langflow によるドキュメント取り込み・検索ワークフロー
- Starlette (Python) バックエンド + Next.js フロントエンド

Watson News は openRAG の Document Store・Vector Index・Query Engine を拡張・活用する形で実装する。

---

## 4. ETLフロー詳細

| ステップ | 処理内容 | 頻度 |
|---|---|---|
| 1. GDELT取得 | GDELT 2.0 API で `IBM` 関連記事を取得 | 毎15分 |
| 2. IBM公式ニュース取得 | RSS フィード + クローラで公式ニュースを取得 | 毎時 |
| 3. Document Store保存 | Raw データを openRAG Document Store へ保存 | リアルタイム |
| 4. クリーニング | HTMLタグ除去・重複排除・正規化 | バッチ（毎時） |
| 5. AI解析 | 要約・センチメント・エンティティ・トピック分類 | バッチ（毎時） |
| 6. Embedding | Granite Embedding でベクトル化 | バッチ（毎時） |
| 7. Vector Index更新 | OpenSearch / FAISS への upsert | バッチ（毎時） |

---

## 5. UI要件

### 5.1 画面一覧

| 画面 | 概要 |
|---|---|
| Dashboard | 最新ニュースの概要・センチメントサマリー・トレンドスナップショット |
| Search & Filter | 自然言語 RAG 検索 + フィルタ（日付・ソース・言語・センチメント） |
| Article Detail | 記事本文 + NLP 解析結果（要約・エンティティ・センチメント・トピック） |
| Trend Analytics | 時系列グラフ・トピックトレンド・異常検知アラート |
| Alerts & Reports | アラート一覧・自動レポート生成・ダウンロード |

### 5.2 デザイン要件

- **デザインシステム:** IBM Carbon Design System v11
- **レイアウト:** 12カラムグリッド
- **コンポーネント:** カードUI、データテーブル、チャート
- **カラースキーム:** IBM Blue (#0f62fe)・White・Gray スケール
- **レスポンシブ:** ブレークポイント sm/md/lg/xlg 対応

---

## 6. 非機能要件

| 要件 | 目標値 |
|---|---|
| 検索レスポンス | 1秒以内（P95） |
| トレンド分析表示 | 3秒以内（P95） |
| ベクトル検索スケール | 100万件以上のインデックス対応 |
| データ鮮度 | ニュース取得から検索可能まで最大30分 |
| セキュリティ | IAM認証、通信TLS暗号化、保存データ暗号化 |
| 監査ログ | 全検索・分析操作のログ記録（90日保持） |
| 可用性 | 99.5%以上（月次） |

---

## 7. KPI

### 7.1 プロダクトKPI

| KPI | 測定方法 |
|---|---|
| 検索利用回数 | 月次クエリ数 |
| トレンド分析利用回数 | 月次ページビュー |
| アラートクリック率 | CTR (クリック数 / 表示数) |
| レポート生成数 | 月次生成件数 |

### 7.2 ビジネスKPI

| KPI | 測定方法 |
|---|---|
| 契約社数 | 累計契約企業数 |
| MAU | 月次アクティブユーザー数 |
| 継続率 | 月次チャーン率の逆数 |

---

## 8. ロードマップ

### Phase 1（〜3ヶ月）— MVP

- [ ] GDELT ingestion パイプライン実装
- [ ] IBM公式ニュース ingestion（RSS + クローラ）実装
- [ ] openRAG Document Store 連携
- [ ] Embedding & Vector Index 構築
- [ ] 基本検索UI（Search & Filter, Article Detail）

### Phase 2（〜6ヶ月）— 機能拡張

- [ ] トレンド分析ダッシュボード
- [ ] アラート機能
- [ ] 自動レポート生成

### Phase 3（〜9ヶ月）— 高度化

- [ ] 競合比較機能
- [ ] 多言語対応（ja / zh / de / fr）
- [ ] 高度RAG（再ランキング・要約生成・ハイブリッド検索）
