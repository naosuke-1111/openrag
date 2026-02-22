import React from 'react';
import { useNeuralFeedStore } from '../../store/neuralFeedStore';

export const ToneGauge: React.FC = () => {
  const tone     = useNeuralFeedStore(s => s.tone);
  const entities = useNeuralFeedStore(s => s.topEntities);

  // Map -1..+1 to 0..100% position on gauge
  const pct = ((tone.average_score + 1) / 2) * 100;

  const labelColor =
    tone.label === 'POSITIVE' ? 'var(--color-green)' :
    tone.label === 'NEGATIVE' ? 'var(--color-red)' :
    'var(--color-yellow)';

  return (
    <div style={{ marginTop: '48px' }}>
      {/* Global Tone Index */}
      <div
        style={{
          fontSize: 'var(--fs-2xs)',
          color: 'var(--color-gray)',
          letterSpacing: '0.2em',
          fontWeight: 600,
          marginBottom: '24px',
        }}
      >
        GLOBAL TONE INDEX
      </div>

      <div
        style={{
          padding: '24px',
          background: 'rgba(0,0,0,0.4)',
          border: '1px solid var(--color-border)',
          borderRadius: '4px',
          marginBottom: '32px',
        }}
      >
        {/* Label + score */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: '20px',
          }}
        >
          <span
            style={{
              fontSize: 'var(--fs-xl)',
              fontWeight: 700,
              color: labelColor,
            }}
          >
            {tone.label}
          </span>
          <span
            style={{
              fontSize: 'var(--fs-md)',
              color: labelColor,
              fontWeight: 600,
            }}
          >
            {tone.average_score >= 0 ? '+' : ''}{tone.average_score.toFixed(2)}
          </span>
        </div>

        {/* Spectrum bar */}
        <div style={{ position: 'relative', height: '16px', borderRadius: '8px', overflow: 'hidden' }}>
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background:
                'linear-gradient(90deg, var(--color-red) 0%, var(--color-yellow) 50%, var(--color-green) 100%)',
              borderRadius: '8px',
            }}
          />
          {/* Pointer */}
          <div
            style={{
              position: 'absolute',
              top: '-4px',
              left: `${Math.max(2, Math.min(98, pct))}%`,
              transform: 'translateX(-50%)',
              width: '8px',
              height: '24px',
              background: 'var(--color-white)',
              borderRadius: '4px',
              boxShadow: '0 0 8px rgba(255,255,255,0.8)',
              transition: 'left 1.2s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          />
        </div>

        {/* Axis labels */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: '10px',
          }}
        >
          <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--color-red)' }}>
            NEGATIVE
          </span>
          <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--color-yellow)' }}>
            NEUTRAL
          </span>
          <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--color-green)' }}>
            POSITIVE
          </span>
        </div>

        {/* Sample size */}
        <div
          style={{
            marginTop: '12px',
            fontSize: 'var(--fs-2xs)',
            color: 'var(--color-gray)',
            textAlign: 'right',
          }}
        >
          n={tone.sample_size} articles (1h)
        </div>
      </div>

      {/* Top entities */}
      {entities.length > 0 && (
        <div>
          <div
            style={{
              fontSize: 'var(--fs-2xs)',
              color: 'var(--color-gray)',
              letterSpacing: '0.2em',
              fontWeight: 600,
              marginBottom: '20px',
            }}
          >
            TOP ENTITIES (15min)
          </div>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            {entities.slice(0, 5).map((e, i) => (
              <span
                key={e.text}
                style={{
                  padding: '8px 18px',
                  border: '1px solid var(--color-border)',
                  borderRadius: '2px',
                  fontSize: `calc(var(--fs-xs) - ${i * 2}px)`,
                  color: i === 0 ? 'var(--color-white)' : 'rgba(255,255,255,0.6)',
                  background: 'rgba(255,255,255,0.03)',
                  fontWeight: i === 0 ? 700 : 400,
                }}
              >
                {e.text}
                <span
                  style={{
                    marginLeft: '8px',
                    fontSize: 'var(--fs-2xs)',
                    color: 'var(--color-gray)',
                  }}
                >
                  ×{e.count}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
