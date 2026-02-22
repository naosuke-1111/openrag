import { create } from 'zustand';
import type {
  Article,
  CategoryCount,
  EntityItem,
  GraphNode,
  KpiMetrics,
  PipelineStepState,
  ToneData,
} from '../types';

// ——— Pipeline step definitions ————————————————————————————————————
export const PIPELINE_STEP_DEFS: Omit<PipelineStepState, 'status'>[] = [
  { id: 0, name: 'Article Ingestion',      description: 'Receiving articles from crawlers' },
  { id: 1, name: 'Language Detection',     description: 'Identifying language (en/ja)' },
  { id: 2, name: 'Tokenization',           description: 'Morphological analysis & tokenization' },
  { id: 3, name: 'Sentiment Scoring',      description: 'Calculating sentiment score (-1.0 → 1.0)' },
  { id: 4, name: 'Entity Extraction',      description: 'Extracting named entities (persons/orgs/places)' },
  { id: 5, name: 'Topic Classification',   description: 'Classifying into topic categories' },
  { id: 6, name: 'Conflict Flag Detection','description': 'Detecting conflict & tension topics' },
];

// ——— Store interface ——————————————————————————————————————————————
interface NeuralFeedStore {
  // Article queue (right panel)
  articleQueue: Article[];
  addArticle: (article: Article) => void;
  markArticleDone: (id: string) => void;

  // Pipeline state (left panel)
  pipelineSteps: PipelineStepState[];
  setPipelineStepStatus: (stepId: number, status: PipelineStepState['status']) => void;
  resetPipeline: () => void;

  // KPI metrics (left panel)
  kpi: KpiMetrics;
  setKpi: (kpi: KpiMetrics) => void;

  // Categories (right panel)
  categories: CategoryCount[];
  setCategories: (cats: CategoryCount[]) => void;

  // Global tone (right panel)
  tone: ToneData;
  setTone: (tone: ToneData) => void;

  // Top entities (right panel)
  topEntities: EntityItem[];
  setTopEntities: (entities: EntityItem[]) => void;

  // Graph nodes queue — consumed by NeuralGraph component each frame
  pendingNodes: GraphNode[];
  enqueueNode: (node: GraphNode) => void;
  consumeNodes: () => GraphNode[];

  // Audio
  audioEnabled: boolean;
  toggleAudio: () => void;

  // Mock mode (backend unavailable)
  isMockMode: boolean;
  setMockMode: (v: boolean) => void;
}

const initialSteps = (): PipelineStepState[] =>
  PIPELINE_STEP_DEFS.map(d => ({ ...d, status: 'QUEUE' as const }));

export const useNeuralFeedStore = create<NeuralFeedStore>((set, get) => ({
  // ——— Article queue ———————————————————————————
  articleQueue: [],
  addArticle: (article) =>
    set(s => ({
      articleQueue: [article, ...s.articleQueue].slice(0, 15),
    })),
  markArticleDone: (id) =>
    set(s => ({
      articleQueue: s.articleQueue.map(a =>
        a.id === id ? { ...a, processing: false } : a,
      ),
    })),

  // ——— Pipeline ————————————————————————————————
  pipelineSteps: initialSteps(),
  setPipelineStepStatus: (stepId, status) =>
    set(s => ({
      pipelineSteps: s.pipelineSteps.map(step =>
        step.id === stepId ? { ...step, status } : step,
      ),
    })),
  resetPipeline: () => set({ pipelineSteps: initialSteps() }),

  // ——— KPI ————————————————————————————————————
  kpi: {
    throughput: 0,
    total_today: 0,
    active_sources: 0,
    connected: false,
    last_updated: '',
  },
  setKpi: (kpi) => set({ kpi }),

  // ——— Categories ——————————————————————————————
  categories: [],
  setCategories: (categories) => set({ categories }),

  // ——— Tone ————————————————————————————————————
  tone: { average_score: 0, label: 'NEUTRAL', sample_size: 0 },
  setTone: (tone) => set({ tone }),

  // ——— Entities ————————————————————————————————
  topEntities: [],
  setTopEntities: (topEntities) => set({ topEntities }),

  // ——— Graph node queue ————————————————————————
  pendingNodes: [],
  enqueueNode: (node) =>
    set(s => ({ pendingNodes: [...s.pendingNodes, node] })),
  consumeNodes: () => {
    const nodes = get().pendingNodes;
    set({ pendingNodes: [] });
    return nodes;
  },

  // ——— Audio ———————————————————————————————————
  audioEnabled: false,
  toggleAudio: () => set(s => ({ audioEnabled: !s.audioEnabled })),

  // ——— Mock mode ——————————————————————————————
  isMockMode: false,
  setMockMode: (v) => set({ isMockMode: v }),
}));
