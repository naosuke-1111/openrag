// ダッシュボード用の統計サマリーカードコンポーネント

import type { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatsCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon: LucideIcon;
  /** アイコン背景色のカスタムクラス */
  iconClassName?: string;
  trend?: {
    value: number;
    label: string;
  };
  className?: string;
}

export function StatsCard({
  title,
  value,
  description,
  icon: Icon,
  iconClassName,
  trend,
  className,
}: StatsCardProps) {
  const isPositiveTrend = trend && trend.value >= 0;

  return (
    <Card className={cn("", className)}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {/* アイコン背景付きコンテナ */}
        <div
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg",
            iconClassName ?? "bg-primary/10",
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
      </CardHeader>
      <CardContent>
        {/* メイン数値 */}
        <div className="text-2xl font-bold">{value}</div>
        {/* 説明文 */}
        {description && (
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        )}
        {/* トレンド表示（前日比など） */}
        {trend && (
          <p
            className={cn(
              "text-xs mt-1 font-medium",
              isPositiveTrend
                ? "text-green-600 dark:text-green-400"
                : "text-red-600 dark:text-red-400",
            )}
          >
            {isPositiveTrend ? "↑" : "↓"} {Math.abs(trend.value)}% {trend.label}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
