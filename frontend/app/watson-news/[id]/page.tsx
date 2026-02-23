"use client";

// Article Detail 画面
// ニュース記事の詳細情報（本文・NLP解析結果・エンティティ・センチメントなど）を表示する

import {
  ArrowLeft,
  Calendar,
  ExternalLink,
  Globe,
  Tag,
} from "lucide-react";
import Link from "next/link";
import { use } from "react";
import { ProtectedRoute } from "@/components/protected-route";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useArticleDetail } from "../_hooks/use-watson-news";
import { SOURCE_TYPE_CONFIG } from "../_types/types";
import { SentimentBadge } from "../_components/sentiment-badge";
import { cn } from "@/lib/utils";

interface ArticleDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function ArticleDetailPage({ params }: ArticleDetailPageProps) {
  // Next.js 15 では params が Promise になった
  const { id } = use(params);
  const { article, isLoading, error } = useArticleDetail(id);

  return (
    <ProtectedRoute>
      <div className="h-full overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
          {/* 戻るリンク */}
          <Link
            href="/watson-news/search"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            検索結果に戻る
          </Link>

          {/* ローディング表示 */}
          {isLoading && (
            <div className="space-y-4">
              <div className="h-8 w-3/4 rounded bg-muted/50 animate-pulse" />
              <div className="h-4 w-1/2 rounded bg-muted/50 animate-pulse" />
              <div className="h-32 rounded bg-muted/50 animate-pulse" />
            </div>
          )}

          {/* エラー表示 */}
          {error && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              {error.message}
            </div>
          )}

          {/* 記事詳細コンテンツ */}
          {article && !isLoading && (
            <>
              {/* ヘッダー: タイトルとメタ情報 */}
              <div className="space-y-3">
                {/* バッジ群 */}
                <div className="flex flex-wrap gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                      SOURCE_TYPE_CONFIG[article.source_type].className,
                    )}
                  >
                    {SOURCE_TYPE_CONFIG[article.source_type].label}
                  </span>
                  <SentimentBadge
                    sentiment={article.sentiment_label}
                    score={article.sentiment_score}
                  />
                  <Badge variant="outline" className="text-xs">
                    {article.language === "ja" ? "日本語" : "English"}
                  </Badge>
                </div>

                {/* 記事タイトル */}
                <h1 className="text-xl font-bold leading-snug">
                  {article.title}
                </h1>

                {/* メタ情報 */}
                <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Globe className="h-3.5 w-3.5" />
                    {article.source_name}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5" />
                    {new Date(article.published).toLocaleDateString("ja-JP", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Tag className="h-3.5 w-3.5" />
                    {article.topic}
                  </span>
                </div>

                {/* 原文リンク */}
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  原文を読む
                </a>
              </div>

              <Separator />

              {/* AI生成サマリー */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      AI サマリー
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-relaxed">{article.summary}</p>
                </CardContent>
              </Card>

              {/* 記事本文（存在する場合） */}
              {article.clean_body && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">記事本文</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-relaxed whitespace-pre-line">
                      {article.clean_body}
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* NLP解析結果セクション */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* センチメント詳細 */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">センチメント分析</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <SentimentBadge
                      sentiment={article.sentiment_label}
                      score={article.sentiment_score}
                    />
                    {/* スコアの視覚的なバー表示 */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>スコア</span>
                        <span>
                          {article.sentiment_score > 0 ? "+" : ""}
                          {article.sentiment_score.toFixed(2)}
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            article.sentiment_label === "positive"
                              ? "bg-green-500"
                              : article.sentiment_label === "negative"
                                ? "bg-red-500"
                                : "bg-gray-400",
                          )}
                          style={{
                            // スコアを 0〜1 の範囲に正規化して幅に変換
                            width: `${Math.min(100, Math.abs(article.sentiment_score) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* エンティティ一覧 */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">
                      抽出エンティティ
                      <span className="ml-1.5 text-xs text-muted-foreground font-normal">
                        ({article.entities.length}件)
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {article.entities.length > 0 ? (
                      <div className="space-y-1.5">
                        {article.entities.map((entity) => (
                          <div
                            key={`${entity.type}-${entity.name}`}
                            className="flex items-center justify-between"
                          >
                            <span className="text-sm">{entity.name}</span>
                            <Badge
                              variant="outline"
                              className="text-xs px-1.5 py-0 font-mono"
                            >
                              {entity.type}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        エンティティが検出されませんでした
                      </p>
                    )}
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
