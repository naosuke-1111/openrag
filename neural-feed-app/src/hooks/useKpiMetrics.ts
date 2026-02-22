import { useEffect } from 'react';
import useSWR from 'swr';
import { api } from '../lib/api';
import {
  MOCK_CATEGORIES,
  MOCK_ENTITIES,
  MOCK_KPI,
  MOCK_TONE,
} from '../lib/mockData';
import { useNeuralFeedStore } from '../store/neuralFeedStore';

const POLL_INTERVAL = 10_000; // 10 seconds

export function useKpiMetrics() {
  const setKpi        = useNeuralFeedStore(s => s.setKpi);
  const setCategories = useNeuralFeedStore(s => s.setCategories);
  const setTone       = useNeuralFeedStore(s => s.setTone);
  const setTopEntities = useNeuralFeedStore(s => s.setTopEntities);
  const isMockMode    = useNeuralFeedStore(s => s.isMockMode);

  const { data: kpiData } = useSWR(
    isMockMode ? null : 'kpi',
    () => api.kpi(),
    { refreshInterval: POLL_INTERVAL, revalidateOnFocus: false },
  );
  const { data: catData } = useSWR(
    isMockMode ? null : 'categories',
    () => api.categories(),
    { refreshInterval: POLL_INTERVAL, revalidateOnFocus: false },
  );
  const { data: toneData } = useSWR(
    isMockMode ? null : 'tone',
    () => api.tone(),
    { refreshInterval: POLL_INTERVAL, revalidateOnFocus: false },
  );
  const { data: entData } = useSWR(
    isMockMode ? null : 'entities',
    () => api.topEntities(),
    { refreshInterval: POLL_INTERVAL, revalidateOnFocus: false },
  );

  useEffect(() => { if (kpiData) setKpi(kpiData); }, [kpiData, setKpi]);
  useEffect(() => { if (catData) setCategories(catData.categories); }, [catData, setCategories]);
  useEffect(() => { if (toneData) setTone(toneData); }, [toneData, setTone]);
  useEffect(() => { if (entData) setTopEntities(entData.entities); }, [entData, setTopEntities]);

  // Load mock data once when in mock mode
  useEffect(() => {
    if (isMockMode) {
      setKpi(MOCK_KPI);
      setCategories(MOCK_CATEGORIES);
      setTone(MOCK_TONE);
      setTopEntities(MOCK_ENTITIES);
    }
  }, [isMockMode, setKpi, setCategories, setTone, setTopEntities]);
}
