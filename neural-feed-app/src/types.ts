export type StepStatus = 'DONE' | 'ACTIVE' | 'QUEUE' | 'ALERT';

export interface PipelineStepDef {
  id: number;
  name: string;
  description: string;
}

export interface PipelineStepState extends PipelineStepDef {
  status: StepStatus;
}

export type SentimentLabel = 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';

export interface Article {
  id: string;
  title: string;
  domain: string;
  source_type: 'gdelt' | 'ibm_crawl' | 'box';
  sentiment_label: SentimentLabel;
  sentiment_score: number;
  topic: string;
  published: string;
  /** Frontend-only: true while pipeline animation is running */
  processing?: boolean;
}

export interface KpiMetrics {
  throughput: number;
  total_today: number;
  active_sources: number;
  connected: boolean;
  last_updated: string;
}

export interface CategoryCount {
  topic: string;
  count: number;
}

export interface EntityItem {
  text: string;
  count: number;
}

export interface ToneData {
  average_score: number;
  label: SentimentLabel;
  sample_size: number;
}

export type ClusterType =
  | 'HUB'
  | 'INPUT'
  | 'PARSE'
  | 'SENTIMENT'
  | 'TOPIC'
  | 'ENTITY'
  | 'CONFLICT'
  | 'OUTPUT';

export interface GraphNode {
  id: string;
  cluster: ClusterType;
  label?: string;
  /** d3-force fields */
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  /** Fixed position for hub/cluster nodes */
  fx?: number | null;
  fy?: number | null;
}

export interface GraphEdge {
  source: string;
  target: string;
}
