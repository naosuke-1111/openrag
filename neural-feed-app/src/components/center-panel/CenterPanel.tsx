import React from 'react';
import { NeuralGraph } from './NeuralGraph';
import { CLUSTER_ORDER, CLUSTER_COLORS } from './forceSimulation';
import type { ClusterType } from '../../types';

/** Cluster legend overlay in the center panel header area */
const ClusterLegend: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      top: '24px',
      left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex',
      gap: '24px',
      zIndex: 25,
      pointerEvents: 'none',
    }}
  >
    {CLUSTER_ORDER.map(cluster => (
      <div
        key={cluster}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <div
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            background: CLUSTER_COLORS[cluster as ClusterType],
            boxShadow: `0 0 8px ${CLUSTER_COLORS[cluster as ClusterType]}`,
          }}
        />
        <span
          style={{
            fontSize: 'var(--fs-2xs)',
            color: CLUSTER_COLORS[cluster as ClusterType],
            letterSpacing: '0.15em',
            fontWeight: 600,
          }}
        >
          {cluster}
        </span>
      </div>
    ))}
  </div>
);

/** Hub label at the true center of the canvas */
const HubLabel: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      textAlign: 'center',
      pointerEvents: 'none',
      zIndex: 5,
    }}
  >
    <div
      className="glow-text"
      style={{
        fontSize: 'var(--fs-2xs)',
        color: 'var(--color-blue-light)',
        letterSpacing: '0.2em',
        fontWeight: 700,
        marginBottom: '8px',
      }}
    >
      WATSON NLU CORE ENGINE
    </div>
  </div>
);

export const CenterPanel: React.FC = () => {
  return (
    <div
      style={{
        width:    '3840px',
        height:   '1890px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Three.js WebGL canvas */}
      <NeuralGraph />

      {/* Cluster legend */}
      <ClusterLegend />

      {/* Hub label */}
      <HubLabel />

      {/* Falling labels container (populated by fallingLabels.ts) */}
      <div id="falling-labels-container" />
    </div>
  );
};
