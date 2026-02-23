// 横断検索のフィルタパネルコンポーネント
// ソース種別・言語・センチメント・日付範囲のフィルタリングに対応

"use client";

import { Filter } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { Language, SearchFilters, SentimentLabel, SourceType } from "../_types/types";

interface FilterPanelProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
  /** アクティブなフィルター数（バッジ表示用） */
  activeFilterCount?: number;
  className?: string;
}

// ソース種別の選択肢
const SOURCE_OPTIONS: { value: SourceType; label: string }[] = [
  { value: "gdelt", label: "GDELT" },
  { value: "ibm_crawl", label: "IBM公式サイト" },
  { value: "box", label: "Box文書" },
];

// 言語の選択肢
const LANGUAGE_OPTIONS: { value: Language; label: string }[] = [
  { value: "ja", label: "日本語" },
  { value: "en", label: "English" },
];

// センチメントの選択肢
const SENTIMENT_OPTIONS: {
  value: SentimentLabel | "all";
  label: string;
  className: string;
}[] = [
  { value: "all", label: "すべて", className: "" },
  {
    value: "positive",
    label: "ポジティブ",
    className: "data-[active=true]:bg-green-100 data-[active=true]:text-green-800 dark:data-[active=true]:bg-green-900/30 dark:data-[active=true]:text-green-400",
  },
  {
    value: "neutral",
    label: "ニュートラル",
    className: "data-[active=true]:bg-gray-100 data-[active=true]:text-gray-700 dark:data-[active=true]:bg-gray-800 dark:data-[active=true]:text-gray-300",
  },
  {
    value: "negative",
    label: "ネガティブ",
    className: "data-[active=true]:bg-red-100 data-[active=true]:text-red-800 dark:data-[active=true]:bg-red-900/30 dark:data-[active=true]:text-red-400",
  },
];

export function FilterPanel({
  filters,
  onChange,
  activeFilterCount,
  className,
}: FilterPanelProps) {
  // ソース種別のトグル処理
  const toggleSourceType = (value: SourceType) => {
    const current = filters.source_types;
    const updated = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    onChange({ ...filters, source_types: updated });
  };

  // 言語のトグル処理
  const toggleLanguage = (value: Language) => {
    const current = filters.languages;
    const updated = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    onChange({ ...filters, languages: updated });
  };

  // フィルターをすべてリセット
  const resetFilters = () => {
    onChange({
      ...filters,
      source_types: [],
      languages: [],
      sentiment: "all",
      date_from: undefined,
      date_to: undefined,
    });
  };

  return (
    <div className={cn("space-y-5", className)}>
      {/* パネルヘッダー */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4" />
          <span className="font-medium text-sm">フィルター</span>
          {activeFilterCount !== undefined && activeFilterCount > 0 && (
            <Badge variant="secondary" className="text-xs px-1.5 py-0">
              {activeFilterCount}
            </Badge>
          )}
        </div>
        {/* リセットボタン（アクティブなフィルターがある場合のみ表示） */}
        {activeFilterCount !== undefined && activeFilterCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="h-auto py-0 px-1 text-xs text-muted-foreground"
            onClick={resetFilters}
          >
            クリア
          </Button>
        )}
      </div>

      <Separator />

      {/* ソース種別フィルター */}
      <div className="space-y-2">
        <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          ソース種別
        </Label>
        <div className="space-y-2">
          {SOURCE_OPTIONS.map((option) => {
            const isActive = filters.source_types.includes(option.value);
            return (
              <label
                key={option.value}
                className="flex items-center gap-2 cursor-pointer group"
              >
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={() => toggleSourceType(option.value)}
                  className="rounded border-border accent-primary"
                />
                <span
                  className={cn(
                    "text-sm transition-colors",
                    isActive ? "text-foreground font-medium" : "text-muted-foreground group-hover:text-foreground",
                  )}
                >
                  {option.label}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      <Separator />

      {/* 言語フィルター */}
      <div className="space-y-2">
        <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          言語
        </Label>
        <div className="space-y-2">
          {LANGUAGE_OPTIONS.map((option) => {
            const isActive = filters.languages.includes(option.value);
            return (
              <label
                key={option.value}
                className="flex items-center gap-2 cursor-pointer group"
              >
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={() => toggleLanguage(option.value)}
                  className="rounded border-border accent-primary"
                />
                <span
                  className={cn(
                    "text-sm transition-colors",
                    isActive ? "text-foreground font-medium" : "text-muted-foreground group-hover:text-foreground",
                  )}
                >
                  {option.label}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      <Separator />

      {/* センチメントフィルター */}
      <div className="space-y-2">
        <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          センチメント
        </Label>
        <div className="space-y-2">
          {SENTIMENT_OPTIONS.map((option) => {
            const isActive =
              option.value === "all"
                ? !filters.sentiment || filters.sentiment === "all"
                : filters.sentiment === option.value;
            return (
              <label
                key={option.value}
                className="flex items-center gap-2 cursor-pointer group"
              >
                <input
                  type="radio"
                  name="sentiment"
                  checked={isActive}
                  onChange={() =>
                    onChange({ ...filters, sentiment: option.value })
                  }
                  className="accent-primary"
                />
                <span
                  className={cn(
                    "text-sm transition-colors",
                    isActive ? "text-foreground font-medium" : "text-muted-foreground group-hover:text-foreground",
                  )}
                >
                  {option.label}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      <Separator />

      {/* 日付範囲フィルター */}
      <div className="space-y-2">
        <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          日付範囲
        </Label>
        <div className="space-y-2">
          <div>
            <Label className="text-xs text-muted-foreground mb-1 block">
              開始日
            </Label>
            <input
              type="date"
              value={filters.date_from ?? ""}
              onChange={(e) =>
                onChange({ ...filters, date_from: e.target.value || undefined })
              }
              className={cn(
                "w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm",
                "focus:outline-none focus:ring-1 focus:ring-ring",
              )}
            />
          </div>
          <div>
            <Label className="text-xs text-muted-foreground mb-1 block">
              終了日
            </Label>
            <input
              type="date"
              value={filters.date_to ?? ""}
              onChange={(e) =>
                onChange({ ...filters, date_to: e.target.value || undefined })
              }
              className={cn(
                "w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm",
                "focus:outline-none focus:ring-1 focus:ring-ring",
              )}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
