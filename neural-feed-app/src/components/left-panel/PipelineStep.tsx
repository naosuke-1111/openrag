import React from 'react';
import type { PipelineStepState } from '../../types';

interface Props {
  step: PipelineStepState;
  index: number;
}

const STATUS_COLORS: Record<PipelineStepState['status'], string> = {
  DONE:   'var(--status-done)',
  ACTIVE: 'var(--status-active)',
  QUEUE:  'var(--status-queue)',
  ALERT:  'var(--status-alert)',
};

const STATUS_ICONS: Record<PipelineStepState['status'], string> = {
  DONE:  '●',
  ACTIVE:'◉',
  QUEUE: '○',
  ALERT: '◈',
};

export const PipelineStep: React.FC<Props> = ({ step, index }) => {
  const color = STATUS_COLORS[step.status];
  const icon  = STATUS_ICONS[step.status];
  const isActive = step.status === 'ACTIVE';
  const isAlert  = step.status === 'ALERT';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '24px',
        padding: '20px 0',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        opacity: step.status === 'QUEUE' ? 0.45 : 1,
        transition: 'opacity 0.4s ease',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Step number */}
      <span
        style={{
          fontSize: 'var(--fs-xs)',
          color: 'var(--color-gray)',
          minWidth: '36px',
          paddingTop: '4px',
        }}
      >
        {String(index + 1).padStart(2, '0')}
      </span>

      {/* Status icon */}
      <span
        className={isActive || isAlert ? 'glow-text' : undefined}
        style={{
          fontSize: 'var(--fs-md)',
          color,
          minWidth: '36px',
          animation: isActive
            ? 'blink 0.8s ease-in-out infinite'
            : isAlert
            ? 'blink 0.4s ease-in-out infinite'
            : undefined,
          transition: 'color 0.3s ease',
        }}
      >
        {icon}
      </span>

      {/* Step info */}
      <div style={{ flex: 1 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            marginBottom: '8px',
          }}
        >
          <span
            style={{
              fontSize: 'var(--fs-sm)',
              fontWeight: 600,
              color: step.status === 'QUEUE' ? 'var(--color-gray)' : 'var(--color-white)',
              transition: 'color 0.3s ease',
            }}
          >
            {step.name}
          </span>
          <span
            style={{
              fontSize: 'var(--fs-2xs)',
              fontWeight: 700,
              letterSpacing: '0.12em',
              color,
              padding: '2px 10px',
              border: `1px solid ${color}`,
              borderRadius: '2px',
            }}
          >
            {step.status}
          </span>
        </div>
        <div
          style={{
            fontSize: 'var(--fs-2xs)',
            color: 'var(--color-gray)',
            lineHeight: 1.4,
          }}
        >
          {step.description}
        </div>

        {/* Active progress bar */}
        {isActive && (
          <div
            style={{
              marginTop: '12px',
              height: '3px',
              background: 'rgba(51,177,255,0.15)',
              borderRadius: '2px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
                width: '60%',
                animation: 'signal-move 1.2s linear infinite',
              }}
            />
          </div>
        )}
      </div>

      {/* Scan line for ACTIVE state */}
      {isActive && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            width: '2px',
            height: '100%',
            background: `linear-gradient(to bottom, transparent, ${color}, transparent)`,
            animation: 'pulse-glow 1.2s ease-in-out infinite',
          }}
        />
      )}
    </div>
  );
};
