import React from 'react';
import { ArticleQueue } from './ArticleQueue';
import { CategoryBar } from './CategoryBar';
import { ToneGauge } from './ToneGauge';

export const RightPanel: React.FC = () => {
  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
        overflowY: 'hidden',
      }}
    >
      {/* Article queue — top half */}
      <div
        style={{
          flex: '0 0 auto',
          maxHeight: '800px',
          overflowY: 'hidden',
        }}
      >
        <ArticleQueue />
      </div>

      {/* Divider */}
      <div
        style={{
          height: '1px',
          background: 'var(--color-border)',
          margin: '32px 0',
          flexShrink: 0,
        }}
      />

      {/* Category bars */}
      <div style={{ flex: '0 0 auto' }}>
        <CategoryBar />
      </div>

      {/* Divider */}
      <div
        style={{
          height: '1px',
          background: 'var(--color-border)',
          margin: '32px 0',
          flexShrink: 0,
        }}
      />

      {/* Tone gauge + entities */}
      <div style={{ flex: 1, overflowY: 'hidden' }}>
        <ToneGauge />
      </div>
    </div>
  );
};
