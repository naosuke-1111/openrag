import { useEffect, useRef } from 'react';
import { useNeuralFeedStore, PIPELINE_STEP_DEFS } from '../store/neuralFeedStore';
import type { Article, ClusterType, GraphNode } from '../types';

// How long (ms) each step stays ACTIVE before becoming DONE
const STEP_DURATIONS: number[] = [350, 250, 900, 700, 800, 600, 250];

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function articleToCluster(article: Article): ClusterType {
  const topic = (article.topic || '').toLowerCase();
  if (topic.includes('conflict') || topic.includes('war')) return 'CONFLICT';
  if (article.sentiment_score < -0.3) return 'SENTIMENT';
  if (topic.includes('tech') || topic.includes('ai')) return 'TOPIC';
  if (topic.includes('finance') || topic.includes('econom')) return 'ENTITY';
  return 'OUTPUT';
}

export function usePipelineState() {
  const setPipelineStepStatus = useNeuralFeedStore(s => s.setPipelineStepStatus);
  const resetPipeline         = useNeuralFeedStore(s => s.resetPipeline);
  const markArticleDone       = useNeuralFeedStore(s => s.markArticleDone);
  const enqueueNode           = useNeuralFeedStore(s => s.enqueueNode);
  const articleQueue          = useNeuralFeedStore(s => s.articleQueue);

  const processingRef = useRef(false);
  const queueRef      = useRef<Article[]>([]);

  // Keep local queue in sync
  useEffect(() => {
    const newProcessing = articleQueue.filter(a => a.processing);
    newProcessing.forEach(a => {
      if (!queueRef.current.find(q => q.id === a.id)) {
        queueRef.current.push(a);
      }
    });
  }, [articleQueue]);

  useEffect(() => {
    let alive = true;

    const runPipeline = async () => {
      while (alive) {
        if (queueRef.current.length === 0 || processingRef.current) {
          await delay(500);
          continue;
        }
        const article = queueRef.current.shift()!;
        processingRef.current = true;
        resetPipeline();

        // Set DONE for steps 0..1 immediately (ingest + lang detect are fast)
        for (let i = 0; i < 2; i++) {
          setPipelineStepStatus(i, 'ACTIVE');
          await delay(STEP_DURATIONS[i]);
          setPipelineStepStatus(i, 'DONE');
        }

        // Steps 2..5 — show ACTIVE for duration then DONE
        for (let i = 2; i < 6; i++) {
          setPipelineStepStatus(i, 'ACTIVE');
          await delay(STEP_DURATIONS[i]);
          setPipelineStepStatus(i, 'DONE');
        }

        // Step 6 — conflict flag: show ALERT briefly if conflict topic
        const isConflict = (article.topic || '').toLowerCase().includes('conflict');
        setPipelineStepStatus(6, isConflict ? 'ALERT' : 'ACTIVE');
        await delay(STEP_DURATIONS[6]);
        setPipelineStepStatus(6, 'DONE');

        // Pipeline done → mark article as processed in queue
        markArticleDone(article.id);

        // Enqueue node for Three.js graph
        const node: GraphNode = {
          id: article.id,
          cluster: articleToCluster(article),
          label: article.topic,
        };
        enqueueNode(node);

        // Brief pause before next article
        processingRef.current = false;
        await delay(1500);
      }
    };

    runPipeline();
    return () => { alive = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
