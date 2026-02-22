/**
 * Manages edge rendering (thin lines) and animated signal dots.
 * Signal dots are rendered as a single THREE.Points for efficiency.
 */
import * as THREE from 'three';
import { CLUSTER_COLORS } from './forceSimulation';
import type { ClusterType } from '../../types';

const MAX_EDGES   = 600;
const MAX_SIGNALS = 600;
const SIGNAL_SPEED = 0.4; // units per ms

interface SignalDot {
  edgeIndex: number;
  t: number; // 0..1 along edge
  speed: number;
  cluster: ClusterType;
}

export interface EdgeManager {
  linesGroup: THREE.Group;
  signalPoints: THREE.Points;
  updateEdges: (
    edges: Array<{
      source: { x?: number; y?: number; cluster: ClusterType };
      target: { x?: number; y?: number; cluster: ClusterType };
    }>,
    delta: number,
  ) => void;
  dispose: () => void;
}

export function createEdgeManager(scene: THREE.Scene): EdgeManager {
  // ——— Lines ————————————————————————————————————————————
  const linesGroup = new THREE.Group();
  scene.add(linesGroup);

  const lineMaterial = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 0.25,
    linewidth: 1, // Note: linewidth > 1 requires LineMaterial from examples
  });

  // Pre-allocate line objects
  const lineObjects: THREE.Line[] = [];
  for (let i = 0; i < MAX_EDGES; i++) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute([0,0,0, 0,0,0], 3));
    geo.setAttribute('color',    new THREE.Float32BufferAttribute([1,1,1, 1,1,1], 3));
    const line = new THREE.Line(geo, lineMaterial.clone());
    line.visible = false;
    linesGroup.add(line);
    lineObjects.push(line);
  }

  // ——— Signal dots ——————————————————————————————————————
  const signalGeo = new THREE.BufferGeometry();
  const signalPositions = new Float32Array(MAX_SIGNALS * 3);
  const signalColors    = new Float32Array(MAX_SIGNALS * 3);
  signalGeo.setAttribute('position', new THREE.BufferAttribute(signalPositions, 3));
  signalGeo.setAttribute('color',    new THREE.BufferAttribute(signalColors, 3));

  const signalMat = new THREE.PointsMaterial({
    size: 10,
    vertexColors: true,
    transparent: true,
    opacity: 0.9,
    sizeAttenuation: true,
  });
  const signalPoints = new THREE.Points(signalGeo, signalMat);
  signalPoints.frustumCulled = false;
  scene.add(signalPoints);

  // Active signals
  const signals: SignalDot[] = [];

  // Edge snapshot for signal dot interpolation
  let edgeSnapshot: Array<{
    src: THREE.Vector3;
    tgt: THREE.Vector3;
    cluster: ClusterType;
  }> = [];

  const color3 = new THREE.Color();

  const updateEdges = (
    edges: Array<{
      source: { x?: number; y?: number; cluster: ClusterType };
      target: { x?: number; y?: number; cluster: ClusterType };
    }>,
    delta: number,
  ) => {
    const count = Math.min(edges.length, MAX_EDGES);
    edgeSnapshot = [];

    // Update line positions
    for (let i = 0; i < MAX_EDGES; i++) {
      const line = lineObjects[i];
      if (i >= count) {
        line.visible = false;
        continue;
      }
      const e   = edges[i];
      const sx  = e.source.x ?? 0;
      const sy  = e.source.y ?? 0;
      const tx  = e.target.x ?? 0;
      const ty  = e.target.y ?? 0;

      const posAttr = (line.geometry as THREE.BufferGeometry).getAttribute('position') as THREE.BufferAttribute;
      posAttr.setXYZ(0, sx, sy, 0);
      posAttr.setXYZ(1, tx, ty, 0);
      posAttr.needsUpdate = true;

      const src = new THREE.Vector3(sx, sy, 0);
      const tgt = new THREE.Vector3(tx, ty, 0);
      edgeSnapshot.push({ src, tgt, cluster: e.target.cluster });

      line.visible = true;

      // Spawn a signal dot occasionally
      if (
        signals.length < MAX_SIGNALS - 5 &&
        Math.random() < delta * 0.8
      ) {
        signals.push({
          edgeIndex: i,
          t: 0,
          speed: SIGNAL_SPEED * (0.7 + Math.random() * 0.6),
          cluster: e.target.cluster,
        });
      }
    }

    // Advance signals
    let activeCount = 0;
    const positions = signalPoints.geometry.getAttribute('position') as THREE.BufferAttribute;
    const colors    = signalPoints.geometry.getAttribute('color') as THREE.BufferAttribute;

    for (let s = signals.length - 1; s >= 0; s--) {
      const sig = signals[s];
      sig.t += sig.speed * delta;
      if (sig.t >= 1) {
        signals.splice(s, 1);
        continue;
      }
      const edge = edgeSnapshot[sig.edgeIndex];
      if (!edge) { signals.splice(s, 1); continue; }

      const pos = edge.src.clone().lerp(edge.tgt, sig.t);
      positions.setXYZ(activeCount, pos.x, pos.y, pos.z);

      const hex = CLUSTER_COLORS[sig.cluster] ?? '#ffffff';
      color3.set(hex);
      colors.setXYZ(activeCount, color3.r, color3.g, color3.b);
      activeCount++;
    }

    // Hide unused slots
    for (let i = activeCount; i < MAX_SIGNALS; i++) {
      positions.setXYZ(i, 0, 0, -9999);
    }

    signalPoints.geometry.setDrawRange(0, Math.max(1, activeCount));
    positions.needsUpdate = true;
    colors.needsUpdate    = true;
  };

  const dispose = () => {
    scene.remove(linesGroup);
    scene.remove(signalPoints);
    signalGeo.dispose();
    signalMat.dispose();
    lineMaterial.dispose();
  };

  return { linesGroup, signalPoints, updateEdges, dispose };
}
