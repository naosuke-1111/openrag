// センチメントラベルを視覚的に表示するバッジコンポーネント

import { cn } from "@/lib/utils";
import { SENTIMENT_CONFIG, type SentimentLabel } from "../_types/types";

interface SentimentBadgeProps {
  sentiment: SentimentLabel;
  score?: number;
  className?: string;
}

export function SentimentBadge({
  sentiment,
  score,
  className,
}: SentimentBadgeProps) {
  const config = SENTIMENT_CONFIG[sentiment];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        config.className,
        className,
      )}
    >
      {config.label}
      {/* スコアが指定されている場合は数値も表示 */}
      {score !== undefined && (
        <span className="opacity-70">
          ({score > 0 ? "+" : ""}
          {score.toFixed(2)})
        </span>
      )}
    </span>
  );
}
