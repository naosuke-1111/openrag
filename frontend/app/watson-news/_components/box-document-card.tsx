// Box文書を一覧表示するカードコンポーネント

import { Calendar, FileText, Tag, User } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SOURCE_TYPE_CONFIG, type BoxDocument } from "../_types/types";
import { cn } from "@/lib/utils";

interface BoxDocumentCardProps {
  document: BoxDocument;
  /** 検索でマッチしたチャンクのプレビューテキスト */
  matchedChunkText?: string;
  /** 検索結果スコア（0〜1） */
  score?: number;
  className?: string;
}

export function BoxDocumentCard({
  document,
  matchedChunkText,
  score,
  className,
}: BoxDocumentCardProps) {
  const sourceConfig = SOURCE_TYPE_CONFIG.box;

  // 更新日時を日本語ロケールでフォーマット
  const updatedDate = new Date(document.updated_at).toLocaleDateString(
    "ja-JP",
    {
      year: "numeric",
      month: "short",
      day: "numeric",
    },
  );

  // ファイル拡張子からアイコン用のラベルを取得
  const fileExtension = document.filename.split(".").pop()?.toUpperCase() ?? "";

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
            {/* Box文書バッジ */}
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                sourceConfig.className,
              )}
            >
              {sourceConfig.label}
            </span>
            {/* ファイル形式バッジ */}
            {fileExtension && (
              <Badge variant="outline" className="text-xs">
                {fileExtension}
              </Badge>
            )}
          </div>
          {/* 検索スコア（検索結果表示時のみ） */}
          {score !== undefined && (
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              スコア: {(score * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {/* ファイル名 — クリックで詳細ページへ遷移 */}
        <CardTitle className="text-sm leading-snug mt-1.5">
          <Link
            href={`/watson-news/box/${document.box_file_id}`}
            className="inline-flex items-center gap-1.5 hover:underline hover:text-primary"
          >
            <FileText className="h-3.5 w-3.5 flex-shrink-0" />
            {document.filename}
          </Link>
        </CardTitle>
      </CardHeader>

      <CardContent>
        {/* マッチしたチャンクのプレビュー（検索結果時のみ表示） */}
        {matchedChunkText && (
          <CardDescription className="text-sm line-clamp-3 mb-3 border-l-2 border-primary/40 pl-2">
            {matchedChunkText}
          </CardDescription>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-3">
            {/* オーナー（メールアドレス） */}
            <span className="flex items-center gap-1">
              <User className="h-3 w-3" />
              {document.owner}
            </span>
            {/* 更新日時 */}
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {updatedDate}
            </span>
          </div>

          {/* トピックタグ */}
          <span className="flex items-center gap-1">
            <Tag className="h-3 w-3" />
            {document.topic}
          </span>
        </div>

        {/* エンティティ一覧（最大3件表示） */}
        {document.entities.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {document.entities.slice(0, 3).map((entity) => (
              <Badge
                key={`${entity.type}-${entity.name}`}
                variant="secondary"
                className="text-xs px-1.5 py-0"
              >
                {entity.name}
              </Badge>
            ))}
            {document.entities.length > 3 && (
              <Badge variant="outline" className="text-xs px-1.5 py-0">
                +{document.entities.length - 3}
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
