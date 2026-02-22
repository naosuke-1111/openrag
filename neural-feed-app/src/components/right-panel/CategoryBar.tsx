import React from 'react';
import { useNeuralFeedStore } from '../../store/neuralFeedStore';

const TOPIC_COLORS: Record<string, string> = {
  Technology:  'var(--cluster-parse)',
  Politics:    'var(--cluster-topic)',
  Finance:     'var(--cluster-entity)',
  Conflict:    'var(--cluster-conflict)',
  Environment: 'var(--cluster-input)',
  Health:      'var(--cluster-sentiment)',
  Other:       'var(--color-gray)',
};

export const CategoryBar: React.FC = () => {
  const categories = useNeuralFeedStore(s => s.categories);
  const total = categories.reduce((s, c) => s + c.count, 0) || 1;

  return (
    <div style={{ marginTop: '48px' }}>
      <div
        style={{
          fontSize: 'var(--fs-2xs)',
          color: 'var(--color-gray)',
          letterSpacing: '0.2em',
          fontWeight: 600,
          marginBottom: '24px',
        }}
      >
        WATSON NLU CATEGORY CLASSIFICATION
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {categories.map(cat => {
          const pct = Math.round((cat.count / total) * 100);
          const color = TOPIC_COLORS[cat.topic] ?? 'var(--color-gray)';
          return (
            <div key={cat.topic}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: '6px',
                }}
              >
                <span
                  style={{
                    fontSize: 'var(--fs-xs)',
                    color: 'var(--color-white)',
                    letterSpacing: '0.05em',
                  }}
                >
                  {cat.topic.toUpperCase()}
                </span>
                <span
                  style={{
                    fontSize: 'var(--fs-xs)',
                    color,
                    fontWeight: 700,
                  }}
                >
                  {pct}%
                </span>
              </div>
              <div
                style={{
                  height: '8px',
                  background: 'rgba(255,255,255,0.06)',
                  borderRadius: '2px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${pct}%`,
                    background: color,
                    boxShadow: `0 0 8px ${color}`,
                    borderRadius: '2px',
                    transition: 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
