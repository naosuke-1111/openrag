import { useEffect, useRef } from 'react';
import { openArticleStream } from '../lib/api';
import { startMockStream } from '../lib/mockData';
import { useNeuralFeedStore } from '../store/neuralFeedStore';
import type { Article } from '../types';

const RECONNECT_DELAY_BASE = 2000;
const MAX_RECONNECT_DELAY  = 30000;

export function useArticleStream() {
  const addArticle   = useNeuralFeedStore(s => s.addArticle);
  const setMockMode  = useNeuralFeedStore(s => s.setMockMode);
  const setKpi       = useNeuralFeedStore(s => s.setKpi);
  const kpi          = useNeuralFeedStore(s => s.kpi);
  const reconnectRef = useRef(0);
  const esRef        = useRef<EventSource | null>(null);
  const mockCancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let delay = RECONNECT_DELAY_BASE;

    const connect = () => {
      const es = openArticleStream(
        (article: Article) => {
          setMockMode(false);
          addArticle({ ...article, processing: true });
          // update throughput approximation
          setKpi({
            ...kpi,
            connected: true,
            last_updated: new Date().toISOString(),
          });
        },
        (_ev) => {
          // SSE error → fall back to mock and schedule reconnect
          setMockMode(true);
          if (!mockCancelRef.current) {
            mockCancelRef.current = startMockStream((a) => addArticle(a));
          }
          setTimeout(() => {
            es.close();
            delay = Math.min(delay * 2, MAX_RECONNECT_DELAY);
            connect();
          }, delay);
        },
      );
      esRef.current = es;
    };

    connect();

    return () => {
      esRef.current?.close();
      mockCancelRef.current?.();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
