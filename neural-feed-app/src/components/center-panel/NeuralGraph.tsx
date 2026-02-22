/**
 * NeuralGraph — mounts the Three.js canvas and drives the animation loop.
 * Consumes pending graph nodes from the Zustand store each frame.
 */
import React, { useEffect, useRef } from 'react';
import { CANVAS_W, CANVAS_H, createGraphEngine, updateCameraOrbit } from './graphEngine';
import { createForceSimulation } from './forceSimulation';
import { createNodeManager } from './nodeManager';
import { createEdgeManager } from './edgeManager';
import { spawnFallingLabel, clearAllLabels } from './fallingLabels';
import { useNeuralFeedStore } from '../../store/neuralFeedStore';
import { useAudio } from '../../hooks/useAudio';
import { CLUSTER_ORDER } from './forceSimulation';

export const NeuralGraph: React.FC = () => {
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const consumeNodes = useNeuralFeedStore(s => s.consumeNodes);
  const { playNodeFire } = useAudio();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // ——— Initialise subsystems ————————————————————————
    const engine     = createGraphEngine(canvas);
    const { scene, camera, renderer, clock } = engine;

    const forceSimRef = createForceSimulation();
    const nodeMgr     = createNodeManager(scene);
    const edgeMgr     = createEdgeManager(scene);

    let rafId: number;
    let alive = true;
    let frameCount = 0;

    // ——— Animation loop ———————————————————————————————
    const animate = () => {
      if (!alive) return;
      rafId = requestAnimationFrame(animate);

      const delta = clock.getDelta();
      frameCount++;

      // 1. Consume pending nodes from store → add to simulation
      const pending = consumeNodes();
      pending.forEach(node => {
        forceSimRef.addLeafNode(node);
        // Spawn falling label every other article
        spawnFallingLabel(node.label ?? 'OTHER');
        // Play audio
        const clusterIdx = CLUSTER_ORDER.indexOf(node.cluster as typeof CLUSTER_ORDER[number]);
        playNodeFire(Math.max(0, clusterIdx));
      });

      // 2. Tick force simulation (manual ticking for fine control)
      forceSimRef.simulation.tick();

      // 3. Update Three.js node positions from d3 layout
      const hubAnimate = (nodeMgr.updatePositions as any).__hubAnimate as
        ((d: number) => void) | undefined;
      hubAnimate?.(delta);

      nodeMgr.updatePositions(forceSimRef.nodes);

      // 4. Update hub group position (always at origin)
      nodeMgr.hubGroup.position.set(0, 0, 0);

      // 5. Update edges + signal dots
      edgeMgr.updateEdges(forceSimRef.links, delta);

      // 6. Camera orbit
      updateCameraOrbit(camera, delta);

      // 7. Render
      renderer.render(scene, camera);
    };

    animate();

    return () => {
      alive = false;
      cancelAnimationFrame(rafId);
      forceSimRef.stop();
      nodeMgr.dispose();
      edgeMgr.dispose();
      engine.dispose();
      clearAllLabels();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_W}
      height={CANVAS_H}
      style={{
        width:  `${CANVAS_W}px`,
        height: `${CANVAS_H}px`,
        display: 'block',
      }}
    />
  );
};
