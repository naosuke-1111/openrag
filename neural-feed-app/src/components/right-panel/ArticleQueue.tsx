import React from 'react';
import { useNeuralFeedStore } from '../../store/neuralFeedStore';
import { ArticleCard } from './ArticleCard';

export const ArticleQueue: React.FC = () => {
  const articles = useNeuralFeedStore(s => s.articleQueue);

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          marginBottom: '24px',
        }}
      >
        <div
          style={{
            width: '6px',
            height: '40px',
            background: 'var(--color-cyan)',
            boxShadow: '0 0 16px var(--color-cyan)',
          }}
        />
        <div>
          <div
            style={{
              fontSize: 'var(--fs-2xs)',
              color: 'var(--color-cyan-light)',
              letterSpacing: '0.2em',
              fontWeight: 600,
              marginBottom: '6px',
            }}
          >
            INCOMING ARTICLES
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
            }}
          >
            <span
              style={{
                fontSize: 'var(--fs-lg)',
                fontWeight: 700,
                color: 'var(--color-white)',
              }}
            >
              ARTICLE QUEUE
            </span>
            <span
              style={{
                fontSize: 'var(--fs-xs)',
                color: 'var(--color-cyan)',
                fontWeight: 600,
                animation: 'blink 1.5s ease-in-out infinite',
              }}
            >
              {articles.filter(a => a.processing).length > 0 ? '● PROCESSING' : '○ IDLE'}
            </span>
          </div>
        </div>
      </div>

      <div
        style={{
          border: '1px solid var(--color-border)',
          borderRadius: '4px',
          overflow: 'hidden',
          background: 'rgba(0,0,0,0.3)',
        }}
      >
        {articles.length === 0 ? (
          <div
            style={{
              padding: '40px',
              textAlign: 'center',
              color: 'var(--color-gray)',
              fontSize: 'var(--fs-sm)',
              letterSpacing: '0.1em',
            }}
          >
            AWAITING ARTICLES...
          </div>
        ) : (
          articles.map(article => (
            <ArticleCard key={article.id} article={article} />
          ))
        )}
      </div>
    </div>
  );
};
