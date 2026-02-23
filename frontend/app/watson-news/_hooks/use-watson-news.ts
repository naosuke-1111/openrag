"use client";

// Watson News API との通信を担うカスタムフック群
// バックエンド (Week 7-8) 実装後、MOCK_DATA を実際の API コールに置き換える

import { useCallback, useEffect, useState } from "react";
import type {
  BoxDocument,
  DashboardStats,
  NewsArticle,
  SearchFilters,
  SearchResultItem,
} from "../_types/types";

// ----------------------------------------
// モックデータ: ダッシュボード統計
// ----------------------------------------
const MOCK_DASHBOARD_STATS: DashboardStats = {
  total_articles: 1284,
  total_box_documents: 47,
  articles_last_24h: 38,
  positive_ratio: 0.42,
  negative_ratio: 0.18,
  neutral_ratio: 0.40,
  top_topics: [
    { topic: "AI / Watson", count: 312 },
    { topic: "クラウド", count: 245 },
    { topic: "セキュリティ", count: 198 },
    { topic: "量子コンピュータ", count: 134 },
    { topic: "半導体", count: 98 },
  ],
  top_entities: [
    { name: "IBM", type: "ORG", count: 956 },
    { name: "Arvind Krishna", type: "PERSON", count: 143 },
    { name: "watsonx", type: "PRODUCT", count: 287 },
    { name: "Red Hat", type: "ORG", count: 201 },
    { name: "HashiCorp", type: "ORG", count: 89 },
  ],
};

// ----------------------------------------
// モックデータ: ニュース記事一覧
// ----------------------------------------
const MOCK_ARTICLES: NewsArticle[] = [
  {
    id: "article-001",
    title: "IBM、watsonx.ai の新モデルを発表 — Granite 3.0 正式リリース",
    url: "https://newsroom.ibm.com/announcements/2026/granite-3",
    source_type: "ibm_crawl",
    source_name: "IBM Newsroom",
    published: "2026-02-22T09:00:00Z",
    language: "en",
    summary:
      "IBMはwatsonx.aiプラットフォーム向けの新世代AIモデル Granite 3.0 を正式にリリースした。マルチリンガル対応と推論性能が大幅に強化されており、エンタープライズ向けのユースケースに最適化されている。",
    sentiment_label: "positive",
    sentiment_score: 0.82,
    entities: [
      { name: "IBM", type: "ORG" },
      { name: "watsonx.ai", type: "PRODUCT" },
      { name: "Granite 3.0", type: "PRODUCT" },
    ],
    topic: "AI / Watson",
  },
  {
    id: "article-002",
    title: "IBM Research が量子コンピュータの新エラー訂正技術を発表",
    url: "https://research.ibm.com/blog/quantum-error-correction-2026",
    source_type: "ibm_crawl",
    source_name: "IBM Research Blog",
    published: "2026-02-21T14:30:00Z",
    language: "en",
    summary:
      "IBM Research は量子コンピューティングにおけるエラー訂正の新手法を発表した。実用的な量子優位性の実現に向けた重要なマイルストーンとして業界から注目を集めている。",
    sentiment_label: "positive",
    sentiment_score: 0.75,
    entities: [
      { name: "IBM Research", type: "ORG" },
      { name: "IBM Quantum", type: "PRODUCT" },
    ],
    topic: "量子コンピュータ",
  },
  {
    id: "article-003",
    title: "IBM、AI規制強化に伴うコンプライアンスコスト増大の懸念を表明",
    url: "https://www.ibm.com/policy/ai-regulation",
    source_type: "gdelt",
    source_name: "GDELT News",
    published: "2026-02-20T11:00:00Z",
    language: "en",
    summary:
      "EU・米国のAI規制強化に対し、IBMがコンプライアンス対応コストの増大に懸念を示した。規制の整合性確保と企業の競争力維持のバランスについて議論が続いている。",
    sentiment_label: "negative",
    sentiment_score: -0.45,
    entities: [
      { name: "IBM", type: "ORG" },
      { name: "EU", type: "ORG" },
    ],
    topic: "セキュリティ",
  },
  {
    id: "article-004",
    title: "IBMクラウド、ハイブリッドクラウド戦略の強化を発表",
    url: "https://www.ibm.com/cloud/hybrid",
    source_type: "ibm_crawl",
    source_name: "IBM Announcements",
    published: "2026-02-19T08:00:00Z",
    language: "en",
    summary:
      "IBMはハイブリッドクラウド・AI戦略の一環として、Red Hatとの統合強化を発表した。エンタープライズ顧客向けのマルチクラウド対応ソリューションが拡充される。",
    sentiment_label: "positive",
    sentiment_score: 0.68,
    entities: [
      { name: "IBM", type: "ORG" },
      { name: "Red Hat", type: "ORG" },
    ],
    topic: "クラウド",
  },
  {
    id: "article-005",
    title: "IBM Japan、watsonx導入事例 — 大手製造業でのAI活用事例を公開",
    url: "https://www.ibm.com/jp-ja/think/insights/manufacturing-ai",
    source_type: "ibm_crawl",
    source_name: "IBM Think Insights JP",
    published: "2026-02-18T10:00:00Z",
    language: "ja",
    summary:
      "IBM Japanが大手製造業でのwatsonx活用事例を公開。生産ラインの異常検知にAIを適用することで、ダウンタイムを30%削減することに成功した事例が紹介された。",
    sentiment_label: "positive",
    sentiment_score: 0.77,
    entities: [
      { name: "IBM Japan", type: "ORG" },
      { name: "watsonx", type: "PRODUCT" },
    ],
    topic: "AI / Watson",
  },
];

// ----------------------------------------
// モックデータ: Box文書
// ----------------------------------------
const MOCK_BOX_DOCUMENTS: BoxDocument[] = [
  {
    id: "box-001",
    box_file_id: "f_12345",
    filename: "IBM_AI_Strategy_2026.pdf",
    mimetype: "application/pdf",
    owner: "strategy@ibm.com",
    updated_at: "2026-02-15T09:00:00Z",
    topic: "AI / Watson",
    entities: [
      { name: "IBM", type: "ORG" },
      { name: "watsonx", type: "PRODUCT" },
    ],
    chunks: [
      {
        chunk_index: 0,
        clean_text:
          "IBMのAI戦略2026では、watsonxプラットフォームを中心としたエンタープライズAIの民主化を推進します。",
        entities: [{ name: "IBM", type: "ORG" }],
        topic: "AI / Watson",
      },
      {
        chunk_index: 1,
        clean_text:
          "主要な注力領域は、生成AI・自動化・セキュリティの3つであり、2026年末までに売上の30%をAI関連製品で構成することを目標とします。",
        entities: [{ name: "watsonx", type: "PRODUCT" }],
        topic: "AI / Watson",
      },
    ],
  },
  {
    id: "box-002",
    box_file_id: "f_23456",
    filename: "Quarterly_Review_Q4_2025.pptx",
    mimetype:
      "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    owner: "finance@ibm.com",
    updated_at: "2026-01-20T14:00:00Z",
    topic: "クラウド",
    entities: [
      { name: "IBM", type: "ORG" },
      { name: "Red Hat", type: "ORG" },
    ],
    chunks: [
      {
        chunk_index: 0,
        clean_text:
          "Q4 2025の売上は前年同期比8%増。クラウド・AIセグメントが全体成長を牽引した。",
        entities: [{ name: "IBM", type: "ORG" }],
        topic: "クラウド",
      },
    ],
  },
];

// ----------------------------------------
// ダッシュボード統計取得フック
// ----------------------------------------
export function useDashboardStats() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // バックエンド実装後は /api/watson-news/stats に差し替える
    const timer = setTimeout(() => {
      setStats(MOCK_DASHBOARD_STATS);
      setIsLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  return { stats, isLoading, error };
}

// ----------------------------------------
// 横断検索フック
// ----------------------------------------
export function useWatsonNewsSearch() {
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const search = useCallback(async (filters: SearchFilters) => {
    setIsLoading(true);
    setError(null);

    try {
      // バックエンド実装後は POST /api/watson-news/search に差し替える
      await new Promise((r) => setTimeout(r, 800));

      // クエリとフィルターでモックデータを絞り込む
      const query = filters.query.toLowerCase();

      const articleResults: SearchResultItem[] = MOCK_ARTICLES.filter(
        (article) => {
          // ソース種別フィルター
          if (
            filters.source_types.length > 0 &&
            !filters.source_types.includes(article.source_type)
          ) {
            return false;
          }
          // 言語フィルター
          if (
            filters.languages.length > 0 &&
            !filters.languages.includes(article.language)
          ) {
            return false;
          }
          // センチメントフィルター
          if (
            filters.sentiment &&
            filters.sentiment !== "all" &&
            article.sentiment_label !== filters.sentiment
          ) {
            return false;
          }
          // キーワード検索（タイトル・サマリー）
          if (
            query &&
            !article.title.toLowerCase().includes(query) &&
            !article.summary.toLowerCase().includes(query)
          ) {
            return false;
          }
          return true;
        },
      ).map((article) => ({
        type: "news" as const,
        score: 0.9,
        article,
      }));

      const boxResults: SearchResultItem[] = MOCK_BOX_DOCUMENTS.filter(
        (doc) => {
          // Boxソースが選択されているかチェック
          if (
            filters.source_types.length > 0 &&
            !filters.source_types.includes("box")
          ) {
            return false;
          }
          // キーワード検索（ファイル名・チャンクテキスト）
          if (
            query &&
            !doc.filename.toLowerCase().includes(query) &&
            !doc.chunks.some((c) => c.clean_text.toLowerCase().includes(query))
          ) {
            return false;
          }
          return true;
        },
      ).map((doc) => ({
        type: "box" as const,
        score: 0.75,
        box_document: doc,
      }));

      setResults([...articleResults, ...boxResults]);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("検索に失敗しました"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { results, isLoading, error, search };
}

// ----------------------------------------
// 記事詳細取得フック
// ----------------------------------------
export function useArticleDetail(id: string) {
  const [article, setArticle] = useState<NewsArticle | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!id) return;

    // バックエンド実装後は GET /api/watson-news/articles/:id に差し替える
    const timer = setTimeout(() => {
      const found = MOCK_ARTICLES.find((a) => a.id === id) ?? null;
      if (found) {
        setArticle(found);
      } else {
        setError(new Error("記事が見つかりませんでした"));
      }
      setIsLoading(false);
    }, 400);

    return () => clearTimeout(timer);
  }, [id]);

  return { article, isLoading, error };
}

// ----------------------------------------
// Box文書詳細取得フック
// ----------------------------------------
export function useBoxDocumentDetail(fileId: string) {
  const [document, setDocument] = useState<BoxDocument | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!fileId) return;

    // バックエンド実装後は GET /api/watson-news/box/files/:file_id に差し替える
    const timer = setTimeout(() => {
      const found =
        MOCK_BOX_DOCUMENTS.find((d) => d.box_file_id === fileId) ?? null;
      if (found) {
        setDocument(found);
      } else {
        setError(new Error("Box文書が見つかりませんでした"));
      }
      setIsLoading(false);
    }, 400);

    return () => clearTimeout(timer);
  }, [fileId]);

  return { document, isLoading, error };
}
