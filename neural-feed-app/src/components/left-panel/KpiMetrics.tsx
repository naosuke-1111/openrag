import React from 'react';
import { useNeuralFeedStore } from '../../store/neuralFeedStore';

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  color?: string;
  blink?: boolean;
}

const MetricCard: React.FC<MetricCardProps> = ({
  label, value, unit, color = 'var(--color-cyan-light)', blink,
}) => (
  <div
    style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: '4px',
      padding: '20px 24px',
      flex: 1,
    }}
  >
    <div
      style={{
        fontSize: 'var(--fs-2xs)',
        color: 'var(--color-gray)',
        letterSpacing: '0.15em',
        marginBottom: '12px',
      }}
    >
      {label}
    </div>
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: '8px',
      }}
    >
      <span
        style={{
          fontSize: 'var(--fs-xl)',
          fontWeight: 700,
          color,
          animation: blink ? 'blink 1s ease-in-out infinite' : undefined,
        }}
      >
        {value}
      </span>
      {unit && (
        <span
          style={{
            fontSize: 'var(--fs-xs)',
            color: 'var(--color-gray)',
          }}
        >
          {unit}
        </span>
      )}
    </div>
  </div>
);

export const KpiMetrics: React.FC = () => {
  const kpi        = useNeuralFeedStore(s => s.kpi);
  const isMockMode = useNeuralFeedStore(s => s.isMockMode);

  const connColor  = kpi.connected ? 'var(--color-green)' : 'var(--color-orange)';
  const connLabel  = kpi.connected ? 'ONLINE' : isMockMode ? 'DEMO' : 'RECONNECTING';

  return (
    <div style={{ marginTop: '40px' }}>
      {/* Connection status bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          padding: '16px 24px',
          background: 'rgba(0,0,0,0.4)',
          border: `1px solid ${connColor}`,
          borderRadius: '4px',
          marginBottom: '24px',
        }}
      >
        <div
          style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            background: connColor,
            boxShadow: `0 0 12px ${connColor}`,
            animation: 'blink 1.5s ease-in-out infinite',
          }}
        />
        <span
          style={{
            fontSize: 'var(--fs-2xs)',
            letterSpacing: '0.2em',
            color: connColor,
            fontWeight: 700,
          }}
        >
          WATSON NLU — {connLabel}
        </span>
      </div>

      {/* KPI grid */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
        <MetricCard
          label="THROUGHPUT"
          value={kpi.throughput.toFixed(0)}
          unit="art/min"
          color="var(--color-cyan-light)"
        />
        <MetricCard
          label="TODAY"
          value={kpi.total_today.toLocaleString()}
          unit="articles"
          color="var(--color-green)"
        />
      </div>

      <MetricCard
        label="ACTIVE SOURCES"
        value={String(kpi.active_sources)}
        unit="connectors"
        color="var(--color-purple)"
        blink={false}
      />
    </div>
  );
};
