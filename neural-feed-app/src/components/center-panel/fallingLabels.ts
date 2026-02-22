/**
 * Falling label DOM elements overlaid on the Three.js canvas.
 * Uses CSS animations — no WebGL text rendering needed.
 */

const LABEL_COLORS: Record<string, string> = {
  CONFLICT:    '#ff8389',
  POLITICS:    '#d4bbff',
  TECHNOLOGY:  '#82cfff',
  FINANCE:     '#ffd6a5',
  HEALTH:      '#ffafd2',
  ENVIRONMENT: '#6fdc8c',
  OTHER:       '#8d8d8d',
};

const TOPIC_LABELS: Record<string, string> = {
  Conflict:    'CONFLICT',
  Politics:    'POLITICS',
  Technology:  'TECHNOLOGY',
  Finance:     'FINANCE',
  Health:      'HEALTH',
  Environment: 'ENVIRONMENT',
  Other:       'OTHER',
};

export function spawnFallingLabel(topic: string, containerId = 'falling-labels-container') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const key   = TOPIC_LABELS[topic] ?? topic.toUpperCase();
  const color = LABEL_COLORS[key] ?? '#ffffff';

  // Random x within center panel (3840px wide)
  const x     = Math.random() * 3600 + 120;
  const dur   = 2.5 + Math.random() * 2.5;

  const el = document.createElement('div');
  el.className          = 'falling-label';
  el.textContent        = `${key}▼`;
  el.style.left         = `${x}px`;
  el.style.color        = color;
  el.style.textShadow   = `0 0 16px ${color}, 0 0 40px ${color}`;
  el.style.setProperty('--fall-duration', `${dur}s`);

  container.appendChild(el);
  el.addEventListener('animationend', () => el.remove(), { once: true });
}

/** Cleanup all labels (e.g., on component unmount) */
export function clearAllLabels(containerId = 'falling-labels-container') {
  const container = document.getElementById(containerId);
  if (!container) return;
  while (container.firstChild) container.removeChild(container.firstChild);
}
