/**
 * Mock data generator — used as fallback when the backend is unavailable.
 */
import type {
  Article,
  CategoryCount,
  EntityItem,
  KpiMetrics,
  ToneData,
} from '../types';

const TITLES = [
  'IBM Announces New Quantum Computing Breakthrough',
  'watsonx.ai Enhances RAG Capabilities for Enterprise',
  'IBM Cloud Security Report: Global Threat Landscape 2026',
  'New IBM Mainframe z17 Targets AI Workloads',
  'Watson NLP Integration Expands to 12 New Languages',
  'IBM and Samsung Partner on Next-Gen Semiconductor Design',
  'Global AI Regulation: IBM Calls for Open Standards',
  'IBM Research Publishes Foundation Model Benchmark',
  'watsonx.governance: Explainable AI at Enterprise Scale',
  'IBM Consulting Deploys AI Agents for Supply Chain Optimization',
  'Conflict in Eastern Europe Disrupts Tech Supply Chains',
  'IBM Open-Sources New Granite Embedding Models',
  'Federal Reserve Warns of AI-Driven Market Volatility',
  'IBM Japan Announces Partnership with METI for AI Policy',
  'Climate Tech: IBM Applies AI to Carbon Tracking',
];

const TOPICS = ['Technology', 'Finance', 'Politics', 'Conflict', 'Environment', 'Health', 'Other'];
const DOMAINS = ['ibm.com', 'gdelt.org', 'reuters.com', 'bloomberg.com', 'nikkei.com'];
const SOURCE_TYPES: Article['source_type'][] = ['gdelt', 'ibm_crawl', 'box'];
const SENTIMENTS: Article['sentiment_label'][] = ['POSITIVE', 'NEUTRAL', 'NEGATIVE'];

let mockIdCounter = 1000;

export function generateMockArticle(): Article {
  const idx = Math.floor(Math.random() * TITLES.length);
  const sentIdx = Math.floor(Math.random() * SENTIMENTS.length);
  const score =
    sentIdx === 0 ? 0.3 + Math.random() * 0.7 :
    sentIdx === 2 ? -0.3 - Math.random() * 0.7 :
    -0.2 + Math.random() * 0.4;
  return {
    id: `mock-${++mockIdCounter}`,
    title: TITLES[idx],
    domain: DOMAINS[Math.floor(Math.random() * DOMAINS.length)],
    source_type: SOURCE_TYPES[Math.floor(Math.random() * SOURCE_TYPES.length)],
    sentiment_label: SENTIMENTS[sentIdx],
    sentiment_score: Math.round(score * 100) / 100,
    topic: TOPICS[Math.floor(Math.random() * TOPICS.length)],
    published: new Date().toISOString(),
    processing: true,
  };
}

/** Start mock article stream — returns a cancel function. */
export function startMockStream(onArticle: (a: Article) => void): () => void {
  let running = true;
  const tick = () => {
    if (!running) return;
    onArticle(generateMockArticle());
    const next = 3000 + Math.random() * 6000;
    setTimeout(tick, next);
  };
  setTimeout(tick, 1500);
  return () => { running = false; };
}

export const MOCK_KPI: KpiMetrics = {
  throughput: 198,
  total_today: 4821,
  active_sources: 3,
  connected: false,
  last_updated: new Date().toISOString(),
};

export const MOCK_CATEGORIES: CategoryCount[] = [
  { topic: 'Technology', count: 142 },
  { topic: 'Politics',   count: 98  },
  { topic: 'Finance',    count: 76  },
  { topic: 'Conflict',   count: 54  },
  { topic: 'Environment',count: 33  },
  { topic: 'Health',     count: 21  },
  { topic: 'Other',      count: 18  },
];

export const MOCK_TONE: ToneData = {
  average_score: -0.18,
  label: 'NEUTRAL',
  sample_size: 100,
};

export const MOCK_ENTITIES: EntityItem[] = [
  { text: 'IBM',              count: 312 },
  { text: 'watsonx',         count: 198 },
  { text: 'Arvind Krishna',  count: 87  },
  { text: 'United States',   count: 73  },
  { text: 'OpenAI',          count: 61  },
];
