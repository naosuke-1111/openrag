// ニュース記事を一覧表示するカードコンポーネント

import { Calendar, ExternalLink, Globe, Tag } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { SOURCE_TYPE_CONFIG, type NewsArticle } from "../_types/types";
import { SentimentBadge } from "./sentiment-badge";

interface ArticleCardProps {
  article: NewsArticle;
  /** 検索結果スコア（0〜1）。指定時は右上に表示 */
  score?: number;
  className?: string;
}

export function ArticleCard({ article, score, className }: ArticleCardProps) {
  const sourceConfig = SOURCE_TYPE_CONFIG[article.source_type];

  // 公開日時を日本語ロケールでフォーマット
  const publishedDate = new Date(article.published).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <Card
      className={cn(
        "hover:border-primary/50 transition-colors cursor-pointer",
        className,
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap gap-1.5">
            {/* ソース種別バッジ */}
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                sourceConfig.className,
              )}
            >
              {sourceConfig.label}
            </span>
            {/* センチメントバッジ */}
            <SentimentBadge sentiment={article.sentiment_label} />
            {/* 言語バッジ */}
            <Badge variant="outline" className="text-xs">
              {article.language === "ja" ? "日本語" : "English"}
            </Badge>
          </div>
          {/* 検索スコア（検索結果表示時のみ） */}
          {score !== undefined && (
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              スコア: {(score * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {/* 記事タイトル — クリックで詳細ページへ遷移 */}
        <CardTitle className="text-sm leading-snug mt-1.5">
          <Link
            href={`/watson-news/${article.id}`}
            className="hover:underline hover:text-primary"
          >
            {article.title}
          </Link>
        </CardTitle>
      </CardHeader>

      <CardContent>
        {/* 記事サマリー（AI生成） */}
        <CardDescription className="text-sm line-clamp-3 mb-3">
          {article.summary}
        </CardDescription>

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-3">
            {/* ソース名 */}
            <span className="flex items-center gap-1">
              <Globe className="h-3 w-3" />
              {article.source_name}
            </span>
            {/* 公開日時 */}
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {publishedDate}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* トピックタグ */}
            <span className="flex items-center gap-1">
              <Tag className="h-3 w-3" />
              {article.topic}
            </span>
            {/* 元記事リンク */}
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 hover:text-primary"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="h-3 w-3" />
              原文
            </a>
          </div>
        </div>

        {/* エンティティ一覧（最大3件表示） */}
        {article.entities.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {article.entities.slice(0, 3).map((entity) => (
              <Badge
                key={`${entity.type}-${entity.name}`}
                variant="secondary"
                className="text-xs px-1.5 py-0"
              >
                {entity.name}
              </Badge>
            ))}
            {article.entities.length > 3 && (
              <Badge variant="outline" className="text-xs px-1.5 py-0">
                +{article.entities.length - 3}
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
