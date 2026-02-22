/**
 * d3-force layout for the neural graph.
 * Hub and cluster nodes have fixed positions; leaf nodes float around clusters.
 */
import * as d3 from 'd3-force';
import type { GraphEdge, GraphNode, ClusterType } from '../../types';

// ——— Cluster fixed positions (in graph coordinate space) ————————————
const TWO_PI = Math.PI * 2;
const CLUSTER_RADIUS = 420;

function clusterPos(index: number, total: number): { x: number; y: number } {
  const angle = (index / total) * TWO_PI - Math.PI / 2;
  return {
    x: Math.cos(angle) * CLUSTER_RADIUS,
    y: Math.sin(angle) * CLUSTER_RADIUS,
  };
}

export const CLUSTER_ORDER: ClusterType[] = [
  'INPUT', 'PARSE', 'SENTIMENT', 'TOPIC', 'ENTITY', 'CONFLICT', 'OUTPUT',
];

export const CLUSTER_COLORS: Record<ClusterType, string> = {
  HUB:       '#0f62fe',
  INPUT:     '#6fdc8c',
  PARSE:     '#82cfff',
  SENTIMENT: '#ffafd2',
  TOPIC:     '#d4bbff',
  ENTITY:    '#ffd6a5',
  CONFLICT:  '#ff8389',
  OUTPUT:    '#ffffff',
};

/** Build initial fixed nodes (hub + 7 clusters) */
export function buildFixedNodes(): GraphNode[] {
  const hub: GraphNode = {
    id: '__hub__',
    cluster: 'HUB',
    label: 'Watson NLU Core',
    fx: 0, fy: 0, x: 0, y: 0,
  };

  const clusters: GraphNode[] = CLUSTER_ORDER.map((c, i) => {
    const pos = clusterPos(i, CLUSTER_ORDER.length);
    return {
      id: `__cluster_${c}__`,
      cluster: c,
      label: c,
      fx: pos.x, fy: pos.y,
      x: pos.x, y: pos.y,
    };
  });

  return [hub, ...clusters];
}

/** Build initial edges: hub → each cluster */
export function buildFixedEdges(): GraphEdge[] {
  return CLUSTER_ORDER.map(c => ({
    source: '__hub__',
    target: `__cluster_${c}__`,
  }));
}

export type D3Node = GraphNode & d3.SimulationNodeDatum;
export type D3Link = { source: D3Node; target: D3Node };

export interface ForceSimulation {
  nodes: D3Node[];
  links: D3Link[];
  simulation: d3.Simulation<D3Node, undefined>;
  addLeafNode: (node: GraphNode) => void;
  tick: () => void;
  stop: () => void;
}

export function createForceSimulation(): ForceSimulation {
  const fixedNodes = buildFixedNodes() as D3Node[];
  const fixedLinks: GraphEdge[] = buildFixedEdges();

  const nodes: D3Node[] = [...fixedNodes];
  const links: D3Link[] = fixedLinks.map(l => ({
    source: nodes.find(n => n.id === l.source)!,
    target: nodes.find(n => n.id === l.target)!,
  }));

  const simulation = d3
    .forceSimulation<D3Node>(nodes)
    .force(
      'link',
      d3.forceLink<D3Node, D3Link>(links)
        .id(d => d.id)
        .distance(d => {
          const src = d.source as D3Node;
          const tgt = d.target as D3Node;
          if (src.cluster === 'HUB' || tgt.cluster === 'HUB') return 0;
          return 120;
        })
        .strength(0.8),
    )
    .force('charge', d3.forceManyBody<D3Node>().strength(-60))
    .force('collision', d3.forceCollide<D3Node>(30))
    .alphaDecay(0.008)
    .velocityDecay(0.4);

  const MAX_LEAF_NODES = 450;
  let leafCount = 0;

  const addLeafNode = (node: GraphNode) => {
    if (leafCount >= MAX_LEAF_NODES) {
      // Remove oldest leaf node
      const oldestLeafIdx = nodes.findIndex(n => !n.id.startsWith('__'));
      if (oldestLeafIdx >= 0) {
        const removed = nodes.splice(oldestLeafIdx, 1)[0];
        // Remove associated links
        const idxToRemove: number[] = [];
        links.forEach((l, i) => {
          if (
            (l.source as D3Node).id === removed.id ||
            (l.target as D3Node).id === removed.id
          ) {
            idxToRemove.push(i);
          }
        });
        for (let i = idxToRemove.length - 1; i >= 0; i--) {
          links.splice(idxToRemove[i], 1);
        }
        leafCount--;
      }
    }

    // Initial position near the target cluster
    const clusterNode = nodes.find(n => n.id === `__cluster_${node.cluster}__`);
    const baseX = clusterNode?.x ?? 0;
    const baseY = clusterNode?.y ?? 0;
    const jitter = 80;
    const newNode: D3Node = {
      ...node,
      x: baseX + (Math.random() - 0.5) * jitter,
      y: baseY + (Math.random() - 0.5) * jitter,
      vx: 0, vy: 0,
    };
    nodes.push(newNode);

    // Link to cluster
    const clusterD3 = nodes.find(n => n.id === `__cluster_${node.cluster}__`);
    if (clusterD3) {
      links.push({ source: clusterD3, target: newNode });
    }

    simulation.nodes(nodes);
    (simulation.force('link') as d3.ForceLink<D3Node, D3Link>).links(links);
    simulation.alpha(0.3).restart();
    leafCount++;
  };

  const tick = () => {
    simulation.tick();
  };

  const stop = () => {
    simulation.stop();
  };

  return { nodes, links, simulation, addLeafNode, tick, stop };
}
