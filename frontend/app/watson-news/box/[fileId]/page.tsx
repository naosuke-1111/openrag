"use client";

// Box Document View 画面
// Box から取得した文書のチャンク・エンティティ・トピックを表示する

import {
  ArrowLeft,
  Calendar,
  ChevronDown,
  ChevronRight,
  FileText,
  Tag,
  User,
} from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { ProtectedRoute } from "@/components/protected-route";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useBoxDocumentDetail } from "../../_hooks/use-watson-news";
import { SOURCE_TYPE_CONFIG } from "../../_types/types";
import { cn } from "@/lib/utils";

interface BoxDocumentPageProps {
  params: Promise<{ fileId: string }>;
}

export default function BoxDocumentPage({ params }: BoxDocumentPageProps) {
  // Next.js 15 では params が Promise になった
  const { fileId } = use(params);
  const { document, isLoading, error } = useBoxDocumentDetail(fileId);

  // 各チャンクの展開/折りたたみ状態を管理
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(
    new Set([0]), // 最初のチャンクはデフォルトで展開
  );

  // チャンクの展開/折りたたみを切り替える
  const toggleChunk = (index: number) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

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

          {/* Box文書詳細コンテンツ */}
          {document && !isLoading && (
            <>
              {/* ヘッダー: ファイル名とメタ情報 */}
              <div className="space-y-3">
                {/* Box文書バッジ */}
                <div className="flex flex-wrap gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                      SOURCE_TYPE_CONFIG.box.className,
                    )}
                  >
                    {SOURCE_TYPE_CONFIG.box.label}
                  </span>
                  {/* ファイル形式バッジ */}
                  <Badge variant="outline" className="text-xs">
                    {document.filename.split(".").pop()?.toUpperCase()}
                  </Badge>
                </div>

                {/* ファイル名 */}
                <h1 className="text-xl font-bold leading-snug flex items-start gap-2">
                  <FileText className="h-5 w-5 mt-0.5 shrink-0 text-muted-foreground" />
                  {document.filename}
                </h1>

                {/* メタ情報 */}
                <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <User className="h-3.5 w-3.5" />
                    {document.owner}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5" />
                    {new Date(document.updated_at).toLocaleDateString("ja-JP", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                    更新
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Tag className="h-3.5 w-3.5" />
                    {document.topic}
                  </span>
                </div>

                {/* Box File ID（デバッグ・参照用） */}
                <p className="text-xs text-muted-foreground font-mono">
                  Box File ID: {document.box_file_id}
                </p>
              </div>

              <Separator />

              {/* 文書サマリー情報 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* エンティティ一覧 */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">
                      抽出エンティティ
                      <span className="ml-1.5 text-xs text-muted-foreground font-normal">
                        ({document.entities.length}件)
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {document.entities.length > 0 ? (
                      <div className="space-y-1.5">
                        {document.entities.map((entity) => (
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

                {/* 文書統計 */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">文書情報</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">チャンク数</span>
                      <span className="font-medium">{document.chunks.length}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">MIMEタイプ</span>
                      <span className="font-mono text-xs truncate max-w-[160px]">
                        {document.mimetype}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">トピック</span>
                      <span className="font-medium">{document.topic}</span>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Separator />

              {/* チャンク一覧セクション */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold">
                    テキストチャンク
                    <span className="ml-1.5 text-xs text-muted-foreground font-normal">
                      ({document.chunks.length}件)
                    </span>
                  </h2>
                  {/* 全チャンクを一括展開/折りたたみ */}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedChunks(
                          new Set(document.chunks.map((_, i) => i)),
                        )
                      }
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      すべて展開
                    </button>
                    <span className="text-muted-foreground text-xs">|</span>
                    <button
                      type="button"
                      onClick={() => setExpandedChunks(new Set())}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      すべて折りたたむ
                    </button>
                  </div>
                </div>

                {/* チャンクカード一覧 */}
                {document.chunks.map((chunk) => {
                  const isExpanded = expandedChunks.has(chunk.chunk_index);
                  return (
                    <Card
                      key={chunk.chunk_index}
                      className="overflow-hidden"
                    >
                      {/* チャンクヘッダー（クリックで展開/折りたたみ） */}
                      <button
                        type="button"
                        className="w-full text-left"
                        onClick={() => toggleChunk(chunk.chunk_index)}
                      >
                        <CardHeader className="py-3 hover:bg-muted/30 transition-colors">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {/* チャンク番号 */}
                              <Badge
                                variant="secondary"
                                className="text-xs px-1.5 py-0 font-mono"
                              >
                                #{chunk.chunk_index + 1}
                              </Badge>
                              {/* チャンクトピック */}
                              <span className="text-xs text-muted-foreground">
                                {chunk.topic}
                              </span>
                            </div>
                            {/* 展開アイコン */}
                            {isExpanded ? (
                              <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            )}
                          </div>
                          {/* 折りたたみ時はテキストをプレビュー表示 */}
                          {!isExpanded && (
                            <p className="text-xs text-muted-foreground line-clamp-1 mt-1">
                              {chunk.clean_text}
                            </p>
                          )}
                        </CardHeader>
                      </button>

                      {/* チャンク展開時のコンテンツ */}
                      {isExpanded && (
                        <CardContent className="pt-0 space-y-3">
                          {/* チャンクテキスト本文 */}
                          <p className="text-sm leading-relaxed whitespace-pre-line">
                            {chunk.clean_text}
                          </p>

                          {/* チャンク内エンティティ */}
                          {chunk.entities.length > 0 && (
                            <div className="flex flex-wrap gap-1 pt-1 border-t border-border">
                              {chunk.entities.map((entity) => (
                                <Badge
                                  key={`${entity.type}-${entity.name}`}
                                  variant="outline"
                                  className="text-xs px-1.5 py-0"
                                >
                                  {entity.name}
                                  <span className="ml-1 opacity-60 font-mono">
                                    {entity.type}
                                  </span>
                                </Badge>
                              ))}
                            </div>
                          )}
                        </CardContent>
                      )}
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
