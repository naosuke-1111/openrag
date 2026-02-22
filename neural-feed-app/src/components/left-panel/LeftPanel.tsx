import React from 'react';
import { KpiMetrics } from './KpiMetrics';
import { PipelineFlow } from './PipelineFlow';
import { useNeuralFeedStore } from '../../store/neuralFeedStore';

export const LeftPanel: React.FC = () => {
  const toggleAudio   = useNeuralFeedStore(s => s.toggleAudio);
  const audioEnabled  = useNeuralFeedStore(s => s.audioEnabled);

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
    >
      {/* Top: app title */}
      <div style={{ marginBottom: 'var(--sp-lg)' }}>
        <div
          style={{
            fontSize: 'var(--fs-2xs)',
            letterSpacing: '0.3em',
            color: 'var(--color-blue)',
            marginBottom: '12px',
            fontWeight: 600,
          }}
        >
          IBM WATSON NLU
        </div>
        <div
          className="glow-text"
          style={{
            fontSize: 'var(--fs-2xl)',
            fontWeight: 700,
            color: 'var(--color-white)',
            letterSpacing: '-0.02em',
            lineHeight: 1,
          }}
        >
          NEURAL
          <br />
          FEED
        </div>
        <div
          style={{
            fontSize: 'var(--fs-xs)',
            color: 'var(--color-gray)',
            marginTop: '16px',
            letterSpacing: '0.1em',
          }}
        >
          AI Thought Process Visualization
        </div>
      </div>

      {/* Middle: pipeline */}
      <div style={{ flex: 1, overflowY: 'hidden' }}>
        <PipelineFlow />
      </div>

      {/* Bottom: KPI + audio toggle */}
      <div>
        <KpiMetrics />

        <button
          onClick={toggleAudio}
          style={{
            marginTop: '24px',
            width: '100%',
            padding: '18px',
            background: 'transparent',
            border: `1px solid ${audioEnabled ? 'var(--color-blue)' : 'var(--color-border)'}`,
            color: audioEnabled ? 'var(--color-blue-light)' : 'var(--color-gray)',
            fontSize: 'var(--fs-2xs)',
            letterSpacing: '0.2em',
            cursor: 'pointer',
            fontFamily: 'var(--font-mono)',
            fontWeight: 600,
            transition: 'all 0.3s ease',
          }}
        >
          {audioEnabled ? '◉ AUDIO ON' : '○ AUDIO OFF'}
        </button>
      </div>
    </div>
  );
};
