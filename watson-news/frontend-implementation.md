# Watson News フロントエンド実装記録（Week 9-10 MVP）

> 作成日: 2026-02-23
> ブランチ: `claude/watson-news-frontend-mvp-HcjMG`
> 対象タスク: `implementation-strategy.md` § Week 9-10 フロントエンド（MVP）

---

## 実装概要

`frontend/app/watson-news/` 配下に以下の4画面を新規実装した。
バックエンド API（Week 7-8 実装予定）が未実装のため、**モックデータ**でUIを動作させており、
API が完成した際にフックの API コール部分を差し替えるだけで本番動作するよう設計している。

---

## 作成ファイル一覧

### 型定義

| ファイル | 説明 |
|---|---|
| `frontend/app/watson-news/_types/types.ts` | `NewsArticle`・`BoxDocument`・`SearchFilters`・`DashboardStats` など全型定義 |

### カスタムフック

| ファイル | 説明 |
|---|---|
| `frontend/app/watson-news/_hooks/use-watson-news.ts` | `useDashboardStats` / `useWatsonNewsSearch` / `useArticleDetail` / `useBoxDocumentDetail` の4フック |

### 共通コンポーネント

| ファイル | 説明 |
|---|---|
| `frontend/app/watson-news/_components/sentiment-badge.tsx` | センチメントラベルを色分けバッジで表示 |
| `frontend/app/watson-news/_components/article-card.tsx` | ニュース記事一覧カード（タイトル・ソース・センチメント・エンティティ表示） |
| `frontend/app/watson-news/_components/box-document-card.tsx` | Box文書一覧カード（ファイル名・オーナー・チャンクプレビュー表示） |
| `frontend/app/watson-news/_components/filter-panel.tsx` | フィルタパネル（ソース種別・言語・センチメント・日付範囲） |
| `frontend/app/watson-news/_components/search-bar.tsx` | 自然言語クエリ入力バー（Enter キー対応・クリアボタン付き） |
| `frontend/app/watson-news/_components/stats-card.tsx` | ダッシュボード用統計サマリーカード |

### ページ

| ファイル | 説明 |
|---|---|
| `frontend/app/watson-news/page.tsx` | Dashboard（静的サマリー） |
| `frontend/app/watson-news/search/page.tsx` | Search & Filter 画面 |
| `frontend/app/watson-news/[id]/page.tsx` | Article Detail 画面 |
| `frontend/app/watson-news/box/[fileId]/page.tsx` | Box Document View 画面 |

### ナビゲーション変更

| ファイル | 変更内容 |
|---|---|
| `frontend/components/navigation.tsx` | サイドバーに「Watson News」リンク（`Newspaper` アイコン）を追加 |

---

## 各画面へのアクセス URL

開発サーバー起動後（`npm run dev` — デフォルトポート: 3000）は以下の URL でアクセスできる。

| 画面名 | URL | 説明 |
|---|---|---|
| **Dashboard** | `http://localhost:3000/watson-news` | ニュース収集状況の静的サマリー |
| **Search & Filter** | `http://localhost:3000/watson-news/search` | ニュース + Box文書 横断検索・フィルタリング |
| **Article Detail** | `http://localhost:3000/watson-news/{article-id}` | 記事詳細（NLP解析結果・エンティティ表示） |
| **Box Document View** | `http://localhost:3000/watson-news/box/{file-id}` | Box文書詳細・チャンク一覧 |

### モックデータでアクセスできるURL例

| 画面 | URL |
|---|---|
| 記事詳細 (article-001) | `http://localhost:3000/watson-news/article-001` |
| 記事詳細 (article-002) | `http://localhost:3000/watson-news/article-002` |
| Box文書詳細 (f_12345) | `http://localhost:3000/watson-news/box/f_12345` |
| Box文書詳細 (f_23456) | `http://localhost:3000/watson-news/box/f_23456` |

---

## 画面別機能詳細

### Dashboard（`/watson-news`）

- 集計統計カード × 4（総記事数・Box文書数・24時間新着・ポジティブ率）
- センチメント分布：積み上げバーグラフ（静的・Phase 2 でインタラクティブ化予定）
- 上位トピックランキング（水平バー付き）
- 頻出エンティティランキング（エンティティタイプバッジ付き）
- 検索画面・Box文書検索へのクイックリンク

### Search & Filter（`/watson-news/search`）

- 自然言語クエリ入力バー（Enter キー対応）
- 左フィルタパネル：
  - ソース種別（GDELT / IBM公式 / Box文書）チェックボックス
  - 言語（日本語 / English）チェックボックス
  - センチメント（すべて / ポジティブ / ニュートラル / ネガティブ）ラジオボタン
  - 日付範囲（開始日 / 終了日）
- 検索結果：ニュース記事セクション + Box文書セクションを分けて表示
- 結果件数サマリーバッジ表示
- ローディングスケルトン・エラー・空状態表示

### Article Detail（`/watson-news/[id]`）

- 記事タイトル・ソース種別・センチメント・言語バッジ
- 公開日時・ソース名・トピック表示
- 原文リンク（外部タブで開く）
- AI生成サマリーカード
- 記事本文（存在する場合）
- センチメント分析詳細（スコアバー付き）
- 抽出エンティティ一覧（タイプバッジ付き）

### Box Document View（`/watson-news/box/[fileId]`）

- ファイル名・Box文書バッジ・ファイル形式バッジ
- オーナー・更新日時・トピック表示
- Box File ID（参照用）
- 文書レベルエンティティ一覧
- 文書統計（チャンク数・MIMEタイプ・トピック）
- チャンク一覧（アコーディオン式展開/折りたたみ）
  - チャンク番号・トピック表示
  - 折りたたみ時はテキストプレビュー表示
  - 展開時は全文 + チャンク内エンティティ表示
  - 全展開 / 全折りたたみボタン

---

## バックエンド API への置き換え（Week 11-12 完了済み）

`_hooks/use-watson-news.ts` の全フックを実 API 接続に置き換え済み（Week 11-12）。

| フック | 接続先エンドポイント |
|---|---|
| `useDashboardStats` | `GET /api/watson-news/articles`・`/box/files`・`/trends`（並列） |
| `useWatsonNewsSearch` | `POST /api/watson-news/search` |
| `useArticleDetail` | `GET /api/watson-news/articles/{id}` |
| `useBoxDocumentDetail` | `GET /api/watson-news/box/files/{file_id}` |

詳細は `watson-news/testing-and-tuning.md` を参照。

---

## 技術スタック

| カテゴリ | 使用技術 |
|---|---|
| フレームワーク | Next.js 15 (App Router) |
| UIコンポーネント | shadcn/ui (Radix UI ベース) |
| スタイリング | Tailwind CSS v3 |
| 状態管理 | React useState / useCallback / useEffect |
| アイコン | Lucide React |
| 型安全性 | TypeScript (strict mode) |

---

## テスト手順

> **前提**: テストフレームワーク（Vitest / Playwright）は未導入。
> 現時点では **手動テスト・型チェック・リント・ビルド確認** で品質を担保する。
> 自動テストの導入手順は「将来の自動テスト導入」セクションを参照。

### 1. 事前準備

```bash
# frontend ディレクトリに移動
cd frontend

# 依存パッケージをインストール（初回のみ）
npm install
```

---

### 2. 開発サーバーで手動テスト

```bash
# 開発サーバーを起動（ホットリロード有効）
npm run dev
```

起動後、ブラウザで以下の URL を順番に確認する。

#### Dashboard（`/watson-news`）

| 確認項目 | 期待動作 |
|---|---|
| 統計カード × 4 が表示される | 総記事数 1,284 / Box文書 47 / 24h新着 38 / ポジティブ率 42% |
| センチメント分布バーが表示される | 緑(42%) / グレー(40%) / 赤(18%) の積み上げバー |
| 上位トピックランキングが表示される | 5件・水平バー付き |
| 頻出エンティティランキングが表示される | 5件・タイプバッジ付き |
| 「ニュースを検索する」ボタンをクリック | `/watson-news/search` に遷移する |

#### Search & Filter（`/watson-news/search`）

| 確認項目 | 期待動作 |
|---|---|
| 初期表示で記事・Box文書が全件表示される | ニュース5件 + Box文書2件 |
| 検索バーに `Watson` と入力して Enter | Watson に関連する記事のみに絞り込まれる |
| 検索バーの「×」ボタンをクリック | 入力がクリアされる |
| ソース種別「IBM公式」のみチェック | ibm_crawl のみ表示される |
| センチメント「ネガティブ」を選択 | ネガティブ記事のみ表示される |
| フィルター「クリア」をクリック | 全件表示に戻る |
| 記事カードのタイトルをクリック | Article Detail 画面に遷移する |
| Box文書カードのファイル名をクリック | Box Document View 画面に遷移する |

#### Article Detail（`/watson-news/article-001`）

| 確認項目 | 期待動作 |
|---|---|
| 記事タイトルが表示される | 「IBM、watsonx.ai の新モデルを発表…」 |
| ソース種別バッジが表示される | 「IBM公式」（紫） |
| センチメントバッジが表示される | 「ポジティブ (+0.82)」（緑） |
| AI サマリーカードが表示される | 要約テキストが表示 |
| センチメントスコアバーが表示される | 82% 幅の緑バー |
| エンティティ一覧が表示される | IBM / watsonx.ai / Granite 3.0 |
| 「原文を読む」リンクが別タブで開く | `target="_blank"` で外部URL |
| 「検索結果に戻る」をクリック | `/watson-news/search` に戻る |

```
# テスト用 URL（モックデータ）
http://localhost:3000/watson-news/article-001  # ポジティブ記事
http://localhost:3000/watson-news/article-003  # ネガティブ記事
http://localhost:3000/watson-news/article-999  # 存在しないID → エラー表示
```

#### Box Document View（`/watson-news/box/f_12345`）

| 確認項目 | 期待動作 |
|---|---|
| ファイル名が表示される | `IBM_AI_Strategy_2026.pdf` |
| Box文書バッジが表示される | 「Box文書」（黄） |
| チャンク #1 がデフォルトで展開されている | テキスト本文が表示される |
| チャンク #2 のヘッダーをクリック | アコーディオンで展開する |
| 「すべて展開」をクリック | 全チャンクが展開される |
| 「すべて折りたたむ」をクリック | 全チャンクが折りたたまれる |
| 折りたたみ時にプレビューテキストが表示される | 1行の省略テキスト |

```
# テスト用 URL（モックデータ）
http://localhost:3000/watson-news/box/f_12345  # PDFファイル（チャンク2件）
http://localhost:3000/watson-news/box/f_23456  # PPTXファイル（チャンク1件）
http://localhost:3000/watson-news/box/f_99999  # 存在しないID → エラー表示
```

---

### 3. 静的解析（TypeScript 型チェック）

```bash
cd frontend

# TypeScript の型エラーがないかチェック（ビルドなし）
npx tsc --noEmit
```

**期待結果**: エラー出力なし（exit code 0）

---

### 4. リント・フォーマットチェック

```bash
cd frontend

# Biome によるリント + フォーマット一括チェック
npm run check-format

# 自動修正（フォーマットのみ）
npm run format

# Next.js 組み込み ESLint
npm run lint
```

**期待結果**: `check-format` / `lint` ともにエラーなし

---

### 5. プロダクションビルド確認

```bash
cd frontend

# 本番ビルドを実行（型エラー・import エラーがあれば失敗する）
npm run build
```

**期待結果**: `✓ Compiled successfully` または `Route (app)` の一覧に以下が含まれること

```
○ /watson-news
○ /watson-news/search
○ /watson-news/[id]
○ /watson-news/box/[fileId]
```

---

### 6. 将来の自動テスト導入（参考）

現時点では未導入だが、Phase 2 以降で以下の構成を推奨する。

#### ユニットテスト: Vitest + React Testing Library

```bash
# インストール
npm install -D vitest @vitejs/plugin-react @testing-library/react @testing-library/user-event jsdom

# テスト実行
npx vitest
```

主なテスト対象:
- `_hooks/use-watson-news.ts` — フィルタリングロジックのテスト
- `_components/filter-panel.tsx` — チェックボックス・ラジオの状態変化
- `_components/search-bar.tsx` — Enter キー・クリアボタンの動作
- `_types/types.ts` — `SENTIMENT_CONFIG` / `SOURCE_TYPE_CONFIG` の値検証

#### E2E テスト: Playwright

```bash
# インストール
npm install -D @playwright/test
npx playwright install

# テスト実行
npx playwright test
```

主なテストシナリオ:
- Dashboard → 「ニュースを検索する」ボタン → Search 画面に遷移
- Search 画面でキーワード入力 → 記事カードタイトルクリック → Article Detail 画面に遷移
- Article Detail の「検索結果に戻る」→ Search 画面に戻る
- Box文書カードクリック → Box Document View でチャンクアコーディオン操作

---

## 残タスク（Phase 2 以降）

- [x] バックエンド API（Week 7-8）完成後にモックデータを実 API に置き換え（Week 11-12 完了）
- [ ] Trend Analytics 画面（`/watson-news/trends`）— `@carbon/charts` で時系列グラフ
- [ ] Alerts & Reports 画面（`/watson-news/alerts`）
- [ ] React Query (`useSWR` / `useQuery`) への移行でキャッシュ管理を最適化
- [ ] ページネーション対応（検索結果・記事一覧）
- [ ] `@carbon/charts-react` 導入によるダッシュボードグラフのインタラクティブ化
