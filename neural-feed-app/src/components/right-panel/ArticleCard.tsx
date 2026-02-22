import React from 'react';
import type { Article } from '../../types';

interface Props {
  article: Article;
}

const SENTIMENT_COLOR: Record<string, string> = {
  POSITIVE: 'var(--color-green)',
  NEUTRAL:  'var(--color-yellow)',
  NEGATIVE: 'var(--color-red)',
};

const SOURCE_LABEL: Record<string, string> = {
  gdelt:     'GDELT',
  ibm_crawl: 'IBM.COM',
  box:       'BOX',
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}

export const ArticleCard: React.FC<Props> = ({ article }) => {
  const sentColor = SENTIMENT_COLOR[article.sentiment_label] ?? 'var(--color-gray)';
  const isActive  = article.processing;

  return (
    <div
      style={{
        padding: '20px 24px 20px 28px',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        position: 'relative',
        animation: 'slide-down 0.4s ease',
        transition: 'opacity 0.5s ease',
        background: isActive
          ? 'rgba(15,98,254,0.04)'
          : 'transparent',
      }}
    >
      {/* Active border line */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: '3px',
          height: '100%',
          background: isActive ? 'var(--color-blue)' : sentColor,
          boxShadow: isActive ? '0 0 12px var(--color-blue)' : undefined,
          transition: 'background 0.4s ease, box-shadow 0.4s ease',
        }}
      />

      {/* Header row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          marginBottom: '10px',
        }}
      >
        <span
          style={{
            fontSize: 'var(--fs-2xs)',
            color: 'var(--color-gray)',
            background: 'rgba(255,255,255,0.05)',
            padding: '2px 10px',
            borderRadius: '2px',
            letterSpacing: '0.1em',
          }}
        >
          {SOURCE_LABEL[article.source_type] ?? article.source_type}
        </span>
        <span
          style={{
            fontSize: 'var(--fs-2xs)',
            color: sentColor,
            fontWeight: 700,
            letterSpacing: '0.1em',
          }}
        >
          {article.sentiment_label}
        </span>
        <span
          style={{
            fontSize: 'var(--fs-2xs)',
            color: 'var(--color-gray)',
            marginLeft: 'auto',
          }}
        >
          {timeAgo(article.published)}
        </span>
      </div>

      {/* Title */}
      <div
        style={{
          fontSize: 'var(--fs-sm)',
          fontWeight: isActive ? 600 : 400,
          color: isActive ? 'var(--color-white)' : 'rgba(255,255,255,0.75)',
          lineHeight: 1.4,
          marginBottom: '8px',
          overflow: 'hidden',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
        }}
      >
        {article.title}
      </div>

      {/* Topic tag */}
      <span
        style={{
          fontSize: 'var(--fs-2xs)',
          color: 'var(--color-purple)',
          letterSpacing: '0.1em',
        }}
      >
        #{article.topic}
      </span>
    </div>
  );
};
