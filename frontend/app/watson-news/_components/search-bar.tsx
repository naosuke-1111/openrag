// 自然言語クエリ入力用の検索バーコンポーネント

"use client";

import { Loader2, Search, X } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
}

export function SearchBar({
  value,
  onChange,
  onSearch,
  isLoading = false,
  placeholder = "IBMのAI戦略、量子コンピュータ、Watson など自然言語で検索...",
  className,
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  // Enterキーで検索を実行
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !isLoading) {
      onSearch();
    }
  };

  // 入力クリアボタンの処理
  const handleClear = () => {
    onChange("");
    inputRef.current?.focus();
  };

  return (
    <div className={cn("relative flex items-center gap-2", className)}>
      {/* 検索アイコン（左側） */}
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={cn(
            "w-full rounded-lg border border-input bg-background pl-9 pr-9 py-2.5",
            "text-sm placeholder:text-muted-foreground",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent",
            "transition-shadow",
          )}
          disabled={isLoading}
        />
        {/* クリアボタン（入力がある場合のみ表示） */}
        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* 検索実行ボタン */}
      <Button
        onClick={onSearch}
        disabled={isLoading || !value.trim()}
        className="shrink-0"
      >
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
            検索中...
          </>
        ) : (
          <>
            <Search className="h-4 w-4 mr-1.5" />
            検索
          </>
        )}
      </Button>
    </div>
  );
}
