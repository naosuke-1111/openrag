import React from 'react';
import { FullscreenCanvas } from './components/layout/FullscreenCanvas';
import { SafeAreaContainer } from './components/layout/SafeAreaContainer';
import { useArticleStream } from './hooks/useArticleStream';
import { useKpiMetrics } from './hooks/useKpiMetrics';
import { usePipelineState } from './hooks/usePipelineState';
import { useNeuralFeedStore } from './store/neuralFeedStore';

import './styles/global.css';
import './styles/safe-area.css';

const DataLayer: React.FC = () => {
  useArticleStream();
  useKpiMetrics();
  usePipelineState();
  return null;
};

const MockModeBanner: React.FC = () => {
  const isMockMode = useNeuralFeedStore(s => s.isMockMode);
  if (!isMockMode) return null;
  return (
    <div
      style={{
        position: 'fixed',
        top: '135px',
        right: '24px',
        zIndex: 100,
        padding: '8px 20px',
        background: 'rgba(255,131,43,0.15)',
        border: '1px solid var(--color-orange)',
        borderRadius: '4px',
        color: 'var(--color-orange)',
        fontSize: 'var(--fs-2xs)',
        letterSpacing: '0.2em',
        fontWeight: 700,
      }}
    >
      ◈ DEMO MODE
    </div>
  );
};

const App: React.FC = () => {
  return (
    <>
      {/* Data layer — side-effect-only hooks */}
      <DataLayer />

      {/* Full-bleed background (7680×2160) */}
      <FullscreenCanvas />

      {/* Safe area content (7680×1890, margin-top: 135px) */}
      <SafeAreaContainer />

      {/* Demo mode indicator */}
      <MockModeBanner />
    </>
  );
};

export default App;
