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

## バックエンド API への置き換え手順

`_hooks/use-watson-news.ts` 内の各フックにコメントでAPI エンドポイントを明記している。

```typescript
// バックエンド実装後は POST /api/watson-news/search に差し替える
// バックエンド実装後は GET /api/watson-news/articles/:id に差し替える
// バックエンド実装後は GET /api/watson-news/box/files/:file_id に差し替える
// バックエンド実装後は /api/watson-news/stats に差し替える
```

各 `setTimeout` ブロックを `fetch()` / React Query の `useQuery` に置き換えることで
実際の API と接続できる。

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

## 残タスク（Phase 2 以降）

- [ ] バックエンド API（Week 7-8）完成後にモックデータを実 API に置き換え
- [ ] Trend Analytics 画面（`/watson-news/trends`）— `@carbon/charts` で時系列グラフ
- [ ] Alerts & Reports 画面（`/watson-news/alerts`）
- [ ] React Query (`useSWR` / `useQuery`) への移行でキャッシュ管理を最適化
- [ ] ページネーション対応（検索結果・記事一覧）
- [ ] `@carbon/charts-react` 導入によるダッシュボードグラフのインタラクティブ化
