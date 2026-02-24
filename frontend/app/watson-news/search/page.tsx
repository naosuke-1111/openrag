"use client";

// Search & Filter 画面
// ニュース記事（GDELT/IBM公式）と Box文書を横断して全文検索・フィルタリングできる画面

import { FileText, Newspaper, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ProtectedRoute } from "@/components/protected-route";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ArticleCard } from "../_components/article-card";
import { BoxDocumentCard } from "../_components/box-document-card";
import { FilterPanel } from "../_components/filter-panel";
import { SearchBar } from "../_components/search-bar";
import { useWatsonNewsSearch } from "../_hooks/use-watson-news";
import type { SearchFilters } from "../_types/types";

// フィルターの初期値
const DEFAULT_FILTERS: SearchFilters = {
  query: "",
  source_types: [],
  languages: [],
  sentiment: "all",
};

export default function WatsonNewsSearchPage() {
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const { results, isLoading, error, search } = useWatsonNewsSearch();

  // 初回表示時に全件取得（クエリ空でも実行）
  useEffect(() => {
    search(DEFAULT_FILTERS);
  }, [search]);

  // フィルター変更時に自動検索
  const handleFiltersChange = useCallback(
    (newFilters: SearchFilters) => {
      setFilters(newFilters);
      // クエリが変わった場合は検索バーの「検索」ボタン押下を待つ
      // ソース種別・言語・センチメント・日付はリアルタイムで反映
      if (newFilters.query === filters.query) {
        search(newFilters);
      }
    },
    [filters.query, search],
  );

  // 検索バーの検索実行
  const handleSearch = useCallback(() => {
    search(filters);
  }, [filters, search]);

  // アクティブなフィルター数を計算
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.source_types.length > 0) count += 1;
    if (filters.languages.length > 0) count += 1;
    if (filters.sentiment && filters.sentiment !== "all") count += 1;
    if (filters.date_from) count += 1;
    if (filters.date_to) count += 1;
    return count;
  }, [filters]);

  // ニュースとBox文書に分類
  const newsResults = results.filter((r) => r.type === "news");
  const boxResults = results.filter((r) => r.type === "box");

  return (
    <ProtectedRoute>
      <div className="flex h-full flex-col">
        {/* ページヘッダー */}
        <div className="border-b border-border px-6 py-4">
          <div className="flex items-center gap-2 mb-1">
            <Search className="h-5 w-5" />
            <h1 className="text-lg font-semibold">横断検索</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            ニュース記事（GDELT・IBM公式サイト）とBox文書をまとめて検索できます
          </p>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* 左カラム: フィルターパネル */}
          <aside className="w-56 shrink-0 border-r border-border overflow-y-auto p-4">
            <FilterPanel
              filters={filters}
              onChange={handleFiltersChange}
              activeFilterCount={activeFilterCount}
            />
          </aside>

          {/* 右カラム: 検索バー + 検索結果リスト */}
          <main className="flex flex-1 flex-col overflow-hidden">
            {/* 検索バー */}
            <div className="border-b border-border px-6 py-4">
              <SearchBar
                value={filters.query}
                onChange={(query) => setFilters((prev) => ({ ...prev, query }))}
                onSearch={handleSearch}
                isLoading={isLoading}
              />
            </div>

            {/* 検索結果一覧 */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
              {/* エラー表示 */}
              {error && (
                <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                  {error.message}
                </div>
              )}

              {/* 結果サマリー */}
              {!isLoading && results.length > 0 && (
                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  <span>{results.length} 件の結果</span>
                  <Badge variant="outline" className="gap-1">
                    <Newspaper className="h-3 w-3" />
                    ニュース {newsResults.length}
                  </Badge>
                  <Badge variant="outline" className="gap-1">
                    <FileText className="h-3 w-3" />
                    Box文書 {boxResults.length}
                  </Badge>
                </div>
              )}

              {/* ローディングスケルトン */}
              {isLoading && (
                <div className="space-y-3">
                  {[...Array(4)].map((_, i) => (
                    <div
                      key={i}
                      className="h-32 rounded-xl border border-border bg-muted/30 animate-pulse"
                    />
                  ))}
                </div>
              )}

              {/* 結果なし */}
              {!isLoading && results.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Search className="h-10 w-10 text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground">
                    {filters.query
                      ? `「${filters.query}」に一致する結果が見つかりませんでした`
                      : "キーワードを入力して検索してください"}
                  </p>
                </div>
              )}

              {/* ニュース記事セクション */}
              {!isLoading && newsResults.length > 0 && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <Newspaper className="h-4 w-4 text-muted-foreground" />
                    <h2 className="text-sm font-semibold">
                      ニュース記事
                      <span className="ml-1.5 text-muted-foreground font-normal">
                        ({newsResults.length}件)
                      </span>
                    </h2>
                  </div>
                  <div className="space-y-3">
                    {newsResults.map((result) =>
                      result.article ? (
                        <ArticleCard
                          key={result.article.id}
                          article={result.article}
                          score={result.score}
                        />
                      ) : null,
                    )}
                  </div>
                </section>
              )}

              {/* ニュースとBoxの区切り */}
              {!isLoading &&
                newsResults.length > 0 &&
                boxResults.length > 0 && <Separator />}

              {/* Box文書セクション */}
              {!isLoading && boxResults.length > 0 && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <h2 className="text-sm font-semibold">
                      Box文書
                      <span className="ml-1.5 text-muted-foreground font-normal">
                        ({boxResults.length}件)
                      </span>
                    </h2>
                  </div>
                  <div className="space-y-3">
                    {boxResults.map((result) =>
                      result.box_document ? (
                        <BoxDocumentCard
                          key={result.box_document.id}
                          document={result.box_document}
                          matchedChunkText={result.matched_chunk?.clean_text}
                          score={result.score}
                        />
                      ) : null,
                    )}
                  </div>
                </section>
              )}
            </div>
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
