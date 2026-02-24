"use client";

// Dashboard 画面（Watson News トップページ）
// ニュース収集状況の静的サマリーを表示する MVP 実装
// Phase 2 以降で @carbon/charts によるインタラクティブグラフに置き換える予定

import {
  Activity,
  ArrowRight,
  FileText,
  Newspaper,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { ProtectedRoute } from "@/components/protected-route";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatsCard } from "./_components/stats-card";
import { useDashboardStats } from "./_hooks/use-watson-news";

export default function WatsonNewsDashboardPage() {
  const { stats, isLoading } = useDashboardStats();

  return (
    <ProtectedRoute>
      <div className="h-full overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">
          {/* ページヘッダー */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Watson News ダッシュボード
              </h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                IBM関連ニュース・Box文書の収集・分析状況サマリー
              </p>
            </div>
            {/* 検索画面へのクイックリンク */}
            <Button asChild variant="default" size="sm">
              <Link href="/watson-news/search">
                <Newspaper className="h-4 w-4 mr-1.5" />
                検索する
              </Link>
            </Button>
          </div>

          <Separator />

          {/* 集計統計カード（4枚） */}
          <section>
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              収集状況サマリー
            </h2>
            {isLoading ? (
              /* ローディングスケルトン */
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[...Array(4)].map((_, i) => (
                  <Skeleton key={i} className="h-28 rounded-xl" />
                ))}
              </div>
            ) : stats ? (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {/* 総記事数 */}
                <StatsCard
                  title="総記事数"
                  value={stats.total_articles.toLocaleString("ja-JP")}
                  description="GDELT + IBM公式サイト"
                  icon={Newspaper}
                  iconClassName="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                />
                {/* Box文書数 */}
                <StatsCard
                  title="Box文書数"
                  value={stats.total_box_documents.toLocaleString("ja-JP")}
                  description="インデックス済み"
                  icon={FileText}
                  iconClassName="bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                />
                {/* 過去24時間の新着 */}
                <StatsCard
                  title="24時間の新着"
                  value={stats.articles_last_24h.toLocaleString("ja-JP")}
                  description="過去24時間に取得した記事"
                  icon={TrendingUp}
                  iconClassName="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                  trend={{ value: 12, label: "前日比" }}
                />
                {/* ポジティブ割合 */}
                <StatsCard
                  title="ポジティブ率"
                  value={`${(stats.positive_ratio * 100).toFixed(0)}%`}
                  description={`ネガティブ ${(stats.negative_ratio * 100).toFixed(0)}% / ニュートラル ${(stats.neutral_ratio * 100).toFixed(0)}%`}
                  icon={Activity}
                  iconClassName="bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                />
              </div>
            ) : null}
          </section>

          {/* センチメント分布バー */}
          {stats && !isLoading && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">センチメント分布</CardTitle>
                <CardDescription className="text-xs">
                  全記事のセンチメント内訳（Phase 2
                  でインタラクティブグラフに置き換え予定）
                </CardDescription>
              </CardHeader>
              <CardContent>
                {/* 積み上げバー */}
                <div className="flex h-6 rounded-full overflow-hidden gap-0.5">
                  <div
                    className="bg-green-500 transition-all"
                    style={{ width: `${stats.positive_ratio * 100}%` }}
                    title={`ポジティブ: ${(stats.positive_ratio * 100).toFixed(1)}%`}
                  />
                  <div
                    className="bg-gray-400 transition-all"
                    style={{ width: `${stats.neutral_ratio * 100}%` }}
                    title={`ニュートラル: ${(stats.neutral_ratio * 100).toFixed(1)}%`}
                  />
                  <div
                    className="bg-red-500 transition-all"
                    style={{ width: `${stats.negative_ratio * 100}%` }}
                    title={`ネガティブ: ${(stats.negative_ratio * 100).toFixed(1)}%`}
                  />
                </div>
                {/* 凡例 */}
                <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-green-500 inline-block" />
                    ポジティブ {(stats.positive_ratio * 100).toFixed(0)}%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-gray-400 inline-block" />
                    ニュートラル {(stats.neutral_ratio * 100).toFixed(0)}%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-red-500 inline-block" />
                    ネガティブ {(stats.negative_ratio * 100).toFixed(0)}%
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* 上位トピックランキング */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">上位トピック</CardTitle>
                <CardDescription className="text-xs">
                  直近30日間の記事数上位5トピック
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-2">
                    {[...Array(5)].map((_, i) => (
                      <Skeleton key={i} className="h-6 rounded" />
                    ))}
                  </div>
                ) : stats ? (
                  <div className="space-y-2">
                    {stats.top_topics.map((item, idx) => {
                      // 最大件数に対する相対的なバー幅を計算
                      const maxCount = stats.top_topics[0].count;
                      const widthPct = (item.count / maxCount) * 100;
                      return (
                        <div key={item.topic} className="space-y-0.5">
                          <div className="flex items-center justify-between text-sm">
                            <span className="flex items-center gap-1.5">
                              {/* ランキング番号 */}
                              <span className="text-xs text-muted-foreground w-4">
                                {idx + 1}.
                              </span>
                              {item.topic}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {item.count.toLocaleString("ja-JP")}件
                            </span>
                          </div>
                          {/* バーグラフ */}
                          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                            <div
                              className="h-full bg-primary/60 rounded-full"
                              style={{ width: `${widthPct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </CardContent>
            </Card>

            {/* 頻出エンティティランキング */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">頻出エンティティ</CardTitle>
                <CardDescription className="text-xs">
                  直近30日間に最も多く言及された固有表現
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-2">
                    {[...Array(5)].map((_, i) => (
                      <Skeleton key={i} className="h-6 rounded" />
                    ))}
                  </div>
                ) : stats ? (
                  <div className="space-y-2">
                    {stats.top_entities.map((item, idx) => (
                      <div
                        key={item.name}
                        className="flex items-center justify-between"
                      >
                        <span className="flex items-center gap-1.5 text-sm">
                          <span className="text-xs text-muted-foreground w-4">
                            {idx + 1}.
                          </span>
                          {item.name}
                          {/* エンティティタイプバッジ */}
                          <Badge
                            variant="outline"
                            className="text-xs px-1 py-0 font-mono"
                          >
                            {item.type}
                          </Badge>
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {item.count.toLocaleString("ja-JP")}件
                        </span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>

          {/* クイックアクション */}
          <Card className="bg-muted/30">
            <CardContent className="py-4">
              <div className="flex flex-wrap gap-3">
                <Button asChild variant="outline" size="sm">
                  <Link href="/watson-news/search">
                    <Newspaper className="h-4 w-4 mr-1.5" />
                    ニュースを検索する
                    <ArrowRight className="h-3.5 w-3.5 ml-1" />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <Link href="/watson-news/search?source=box">
                    <FileText className="h-4 w-4 mr-1.5" />
                    Box文書を検索する
                    <ArrowRight className="h-3.5 w-3.5 ml-1" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </ProtectedRoute>
  );
}
