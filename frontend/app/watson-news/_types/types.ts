// Watson News で使用する型定義

// ソース種別
export type SourceType = "gdelt" | "ibm_crawl" | "box";

// センチメントラベル
export type SentimentLabel = "positive" | "neutral" | "negative";

// 対応言語
export type Language = "ja" | "en";

// エンティティ（人名・組織名・製品名など）
export interface Entity {
  name: string;
  type: string; // PERSON, ORG, PRODUCT, LOCATION など
}

// ニュース記事
export interface NewsArticle {
  id: string;
  title: string;
  url: string;
  source_type: Exclude<SourceType, "box">;
  source_name: string;
  published: string;
  language: Language;
  summary: string;
  clean_body?: string;
  sentiment_label: SentimentLabel;
  sentiment_score: number;
  entities: Entity[];
  topic: string;
}

// Box文書チャンク
export interface BoxChunk {
  chunk_index: number;
  clean_text: string;
  entities: Entity[];
  topic: string;
}

// Box文書
export interface BoxDocument {
  id: string;
  box_file_id: string;
  filename: string;
  mimetype: string;
  owner: string;
  updated_at: string;
  topic: string;
  entities: Entity[];
  chunks: BoxChunk[];
}

// 横断検索結果アイテム（ニュース・Box文書共通）
export interface SearchResultItem {
  type: "news" | "box";
  score: number;
  article?: NewsArticle;
  box_document?: BoxDocument;
  matched_chunk?: BoxChunk;
}

// 検索フィルター条件
export interface SearchFilters {
  query: string;
  source_types: SourceType[];
  languages: Language[];
  sentiment?: SentimentLabel | "all";
  date_from?: string;
  date_to?: string;
}

// ダッシュボード集計統計
export interface DashboardStats {
  total_articles: number;
  total_box_documents: number;
  articles_last_24h: number;
  positive_ratio: number;
  negative_ratio: number;
  neutral_ratio: number;
  top_topics: Array<{ topic: string; count: number }>;
  top_entities: Array<{ name: string; type: string; count: number }>;
}

// センチメントごとの表示設定
export const SENTIMENT_CONFIG: Record<
  SentimentLabel,
  { label: string; className: string }
> = {
  positive: {
    label: "ポジティブ",
    className:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  },
  neutral: {
    label: "ニュートラル",
    className:
      "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  },
  negative: {
    label: "ネガティブ",
    className:
      "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  },
};

// ソース種別ごとの表示設定
export const SOURCE_TYPE_CONFIG: Record<
  SourceType,
  { label: string; className: string }
> = {
  gdelt: {
    label: "GDELT",
    className:
      "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  },
  ibm_crawl: {
    label: "IBM公式",
    className:
      "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  },
  box: {
    label: "Box文書",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  },
};
