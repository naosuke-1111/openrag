import type {
  Article,
  CategoryCount,
  EntityItem,
  KpiMetrics,
  ToneData,
} from '../types';

const BASE = '/api/neural-feed';

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  recentArticles: (): Promise<{ articles: Article[]; total: number }> =>
    fetchJson('/articles/recent'),

  kpi: (): Promise<KpiMetrics> =>
    fetchJson('/kpi'),

  categories: (): Promise<{ categories: CategoryCount[]; total: number }> =>
    fetchJson('/categories'),

  tone: (): Promise<ToneData> =>
    fetchJson('/tone'),

  topEntities: (): Promise<{ entities: EntityItem[]; unique_count: number }> =>
    fetchJson('/entities/top'),
};

/** Open an SSE connection for real-time article events.
 *  Returns an EventSource (close it on component unmount).
 */
export function openArticleStream(
  onArticle: (article: Article) => void,
  onError?: (e: Event) => void,
): EventSource {
  const es = new EventSource(`${BASE}/articles/stream`);
  es.addEventListener('new_article', (ev: MessageEvent) => {
    try {
      const article: Article = JSON.parse(ev.data);
      onArticle(article);
    } catch (_) {
      // ignore malformed events
    }
  });
  if (onError) es.onerror = onError;
  return es;
}
