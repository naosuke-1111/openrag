/**
 * Manages Three.js node rendering using InstancedMesh for performance.
 * Handles up to 500 nodes at 60fps via a single draw call.
 */
import * as THREE from 'three';
import { CLUSTER_COLORS } from './forceSimulation';
import type { ClusterType } from '../../types';

const MAX_INSTANCES = 500;

// Hub ring geometry
const HUB_RINGS = 3;
const HUB_BASE_RADIUS = 50;

export interface NodeManager {
  instancedMesh: THREE.InstancedMesh;
  hubGroup: THREE.Group;
  updatePositions: (nodes: Array<{ id: string; x?: number; y?: number; cluster: ClusterType }>) => void;
  flashNode: (index: number, cluster: ClusterType) => void;
  dispose: () => void;
}

export function createNodeManager(scene: THREE.Scene): NodeManager {
  // ——— InstancedMesh for leaf + cluster nodes ————————————
  const geo  = new THREE.SphereGeometry(8, 8, 8);
  const mat  = new THREE.MeshBasicMaterial({ vertexColors: true });
  const mesh = new THREE.InstancedMesh(geo, mat, MAX_INSTANCES);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  mesh.count = 0;
  scene.add(mesh);

  // ——— Hub: concentric glowing rings ————————————————————
  const hubGroup = new THREE.Group();
  const ringMat  = new THREE.MeshBasicMaterial({
    color: new THREE.Color(CLUSTER_COLORS['HUB']),
    wireframe: false,
    transparent: true,
    opacity: 0.6,
  });

  for (let r = 0; r < HUB_RINGS; r++) {
    const radius = HUB_BASE_RADIUS + r * 25;
    const ringGeo = new THREE.TorusGeometry(radius, 2, 8, 48);
    const ring    = new THREE.Mesh(ringGeo, ringMat.clone());
    ring.rotation.x = Math.PI / 2 + (r * 0.3);
    hubGroup.add(ring);

    // Core sphere
    if (r === 0) {
      const coreGeo = new THREE.SphereGeometry(HUB_BASE_RADIUS - 10, 16, 16);
      const coreMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(CLUSTER_COLORS['HUB']),
        transparent: true,
        opacity: 0.8,
      });
      hubGroup.add(new THREE.Mesh(coreGeo, coreMat));
    }
  }
  scene.add(hubGroup);

  // ——— Cluster label sprites (text via canvas texture) ————
  const matrix    = new THREE.Matrix4();
  const color     = new THREE.Color();
  const flashMap  = new Map<number, { t: number; baseColor: THREE.Color }>();

  const updatePositions = (
    nodes: Array<{ id: string; x?: number; y?: number; cluster: ClusterType }>,
  ) => {
    const nonHub    = nodes.filter(n => n.id !== '__hub__');
    mesh.count      = Math.min(nonHub.length, MAX_INSTANCES);

    nonHub.slice(0, MAX_INSTANCES).forEach((node, i) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const isCluster = node.id.startsWith('__cluster_');

      // Scale: cluster nodes are bigger
      const scale = isCluster ? 2.5 : 1.0;
      matrix.makeScale(scale, scale, scale);
      matrix.setPosition(x, y, 0);
      mesh.setMatrixAt(i, matrix);

      // Color
      const hex = CLUSTER_COLORS[node.cluster] ?? '#888888';
      color.set(hex);

      // Flash effect
      if (flashMap.has(i)) {
        const f = flashMap.get(i)!;
        f.t += 0.05;
        const intensity = Math.max(0, 1 - f.t);
        color.lerp(new THREE.Color(1, 1, 1), intensity * 0.8);
        if (f.t >= 1) flashMap.delete(i);
      }

      mesh.setColorAt(i, color);
    });

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  };

  // Hub pulse animation (called in render loop from NeuralGraph)
  let hubPulseT = 0;
  const _hubAnimate = (delta: number) => {
    hubPulseT += delta * 0.8;
    const pulse = 0.7 + Math.sin(hubPulseT) * 0.3;
    hubGroup.children.forEach((child, i) => {
      if ((child as THREE.Mesh).material) {
        ((child as THREE.Mesh).material as THREE.MeshBasicMaterial).opacity = pulse * (0.5 + i * 0.1);
      }
    });
    hubGroup.rotation.y += delta * 0.15;
  };

  // Expose hub animate via updatePositions delta trick
  (updatePositions as any).__hubAnimate = _hubAnimate;

  const flashNode = (index: number, cluster: ClusterType) => {
    flashMap.set(index, {
      t: 0,
      baseColor: new THREE.Color(CLUSTER_COLORS[cluster] ?? '#888'),
    });
  };

  const dispose = () => {
    geo.dispose();
    mat.dispose();
    scene.remove(mesh);
    scene.remove(hubGroup);
  };

  return { instancedMesh: mesh, hubGroup, updatePositions, flashNode, dispose };
}
