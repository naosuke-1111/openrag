"use client";

// Watson News API との通信を担うカスタムフック群

import { useCallback, useEffect, useState } from "react";
import type {
  BoxDocument,
  DashboardStats,
  NewsArticle,
  SearchFilters,
  SearchResultItem,
} from "../_types/types";

// ----------------------------------------
// 型変換ヘルパー
// ----------------------------------------
function toNewsArticle(hit: Record<string, unknown>): NewsArticle {
  return {
    id: String(hit.id ?? ""),
    title: String(hit.title ?? ""),
    url: String(hit.url ?? ""),
    source_type: (hit.source_type as NewsArticle["source_type"]) ?? "gdelt",
    source_name: String(hit.source_name ?? hit.source_type ?? ""),
    published: String(hit.published ?? ""),
    language: (hit.language as NewsArticle["language"]) ?? "en",
    summary: String(hit.summary ?? ""),
    clean_body: hit.clean_body ? String(hit.clean_body) : undefined,
    sentiment_label:
      (hit.sentiment_label as NewsArticle["sentiment_label"]) ?? "neutral",
    sentiment_score: Number(hit.sentiment_score ?? 0),
    entities: Array.isArray(hit.entities)
      ? (hit.entities as NewsArticle["entities"])
      : [],
    topic: String(hit.topic ?? ""),
  };
}

function toBoxDocument(raw: Record<string, unknown>): BoxDocument {
  return {
    id: String(raw.id ?? ""),
    box_file_id: String(raw.box_file_id ?? raw.id ?? ""),
    filename: String(raw.filename ?? ""),
    mimetype: String(raw.mimetype ?? ""),
    owner: String(raw.owner ?? ""),
    updated_at: String(raw.updated_at ?? ""),
    topic: String(raw.topic ?? ""),
    entities: Array.isArray(raw.entities)
      ? (raw.entities as BoxDocument["entities"])
      : [],
    chunks: Array.isArray(raw.chunks)
      ? (raw.chunks as BoxDocument["chunks"])
      : [],
  };
}

// ----------------------------------------
// ダッシュボード統計取得フック
// ----------------------------------------
export function useDashboardStats() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchStats() {
      try {
        const [articlesRes, boxRes, trendsRes] = await Promise.all([
          fetch("/api/watson-news/articles?size=0"),
          fetch("/api/watson-news/box/files?size=0"),
          fetch("/api/watson-news/trends"),
        ]);

        if (!articlesRes.ok || !boxRes.ok || !trendsRes.ok) {
          throw new Error("統計データの取得に失敗しました");
        }

        const [articlesData, boxData, trendsData] = await Promise.all([
          articlesRes.json(),
          boxRes.json(),
          trendsRes.json(),
        ]);

        if (cancelled) return;

        // センチメント集計
        const sentimentCounts = { positive: 0, negative: 0, neutral: 0 };
        const articles: Record<string, unknown>[] = Array.isArray(
          articlesData.articles,
        )
          ? articlesData.articles
          : [];
        for (const a of articles) {
          const label = String(a.sentiment_label ?? "neutral") as
            | "positive"
            | "negative"
            | "neutral";
          if (label in sentimentCounts) sentimentCounts[label]++;
        }
        const total = articles.length || 1;

        setStats({
          total_articles: articlesData.total ?? articles.length,
          total_box_documents: boxData.total ?? 0,
          articles_last_24h: articlesData.articles_last_24h ?? 0,
          positive_ratio: sentimentCounts.positive / total,
          negative_ratio: sentimentCounts.negative / total,
          neutral_ratio: sentimentCounts.neutral / total,
          top_topics: Array.isArray(trendsData.top_topics)
            ? trendsData.top_topics
            : [],
          top_entities: Array.isArray(trendsData.top_entities)
            ? trendsData.top_entities
            : [],
        });
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err
              : new Error("統計データの取得に失敗しました"),
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchStats();
    return () => {
      cancelled = true;
    };
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
      const response = await fetch("/api/watson-news/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: filters.query,
          source_types:
            filters.source_types.length > 0 ? filters.source_types : undefined,
          languages:
            filters.languages.length > 0 ? filters.languages : undefined,
          sentiment:
            filters.sentiment && filters.sentiment !== "all"
              ? filters.sentiment
              : undefined,
          date_from: filters.date_from ?? undefined,
          date_to: filters.date_to ?? undefined,
          size: 50,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(
          (err as { error?: string }).error ?? "検索に失敗しました",
        );
      }

      const data = await response.json();

      const mapped: SearchResultItem[] = (
        (data.results ?? []) as Record<string, unknown>[]
      ).map((item) => {
        if (item.type === "box") {
          return {
            type: "box" as const,
            score: Number(item.score ?? 0),
            box_document: toBoxDocument(
              (item.box_document as Record<string, unknown>) ?? {},
            ),
          };
        }
        return {
          type: "news" as const,
          score: Number(item.score ?? 0),
          article: toNewsArticle(
            (item.article as Record<string, unknown>) ?? {},
          ),
        };
      });

      setResults(mapped);
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

    let cancelled = false;

    async function fetchArticle() {
      try {
        const response = await fetch(`/api/watson-news/articles/${id}`);

        if (response.status === 404) {
          throw new Error("記事が見つかりませんでした");
        }
        if (!response.ok) {
          throw new Error("記事の取得に失敗しました");
        }

        const data = await response.json();
        if (!cancelled) {
          setArticle(toNewsArticle(data as Record<string, unknown>));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err : new Error("記事の取得に失敗しました"),
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchArticle();
    return () => {
      cancelled = true;
    };
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

    let cancelled = false;

    async function fetchDocument() {
      try {
        const response = await fetch(`/api/watson-news/box/files/${fileId}`);

        if (response.status === 404) {
          throw new Error("Box文書が見つかりませんでした");
        }
        if (!response.ok) {
          throw new Error("Box文書の取得に失敗しました");
        }

        const data = await response.json();
        if (!cancelled) {
          setDocument(toBoxDocument(data as Record<string, unknown>));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err
              : new Error("Box文書の取得に失敗しました"),
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchDocument();
    return () => {
      cancelled = true;
    };
  }, [fileId]);

  return { document, isLoading, error };
}
