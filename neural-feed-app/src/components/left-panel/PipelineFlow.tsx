import React from 'react';
import { useNeuralFeedStore } from '../../store/neuralFeedStore';
import { PipelineStep } from './PipelineStep';

export const PipelineFlow: React.FC = () => {
  const steps = useNeuralFeedStore(s => s.pipelineSteps);

  return (
    <div>
      {/* Section header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          marginBottom: '32px',
        }}
      >
        <div
          style={{
            width: '6px',
            height: '40px',
            background: 'var(--color-blue)',
            boxShadow: '0 0 16px var(--color-blue)',
          }}
        />
        <div>
          <div
            style={{
              fontSize: 'var(--fs-2xs)',
              color: 'var(--color-blue-light)',
              letterSpacing: '0.2em',
              fontWeight: 600,
              marginBottom: '6px',
            }}
          >
            WATSON NLU PIPELINE
          </div>
          <div
            style={{
              fontSize: 'var(--fs-lg)',
              fontWeight: 700,
              color: 'var(--color-white)',
              letterSpacing: '-0.01em',
            }}
          >
            AI PROCESSING
          </div>
        </div>
      </div>

      {/* Steps */}
      <div>
        {steps.map((step, i) => (
          <PipelineStep key={step.id} step={step} index={i} />
        ))}
      </div>
    </div>
  );
};
