/**
 * Full-bleed particle background layer (7680×2160px).
 * Renders behind the safe area, giving the LED screen an immersive glow.
 * Uses Canvas 2D — intentionally simple to not compete with Three.js GPU budget.
 */
import React, { useEffect, useRef } from 'react';

const W = 7680;
const H = 2160;
const PARTICLE_COUNT = 220;

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  alpha: number;
  dAlpha: number;
  color: string;
}

const COLORS = [
  'rgba(15,98,254,',    // IBM Blue
  'rgba(51,177,255,',   // Cyan
  'rgba(66,190,101,',   // Green
  'rgba(212,187,255,',  // Purple
];

function createParticle(): Particle {
  const color = COLORS[Math.floor(Math.random() * COLORS.length)];
  return {
    x:      Math.random() * W,
    y:      Math.random() * H,
    vx:     (Math.random() - 0.5) * 0.4,
    vy:     (Math.random() - 0.5) * 0.4,
    radius: 1 + Math.random() * 3,
    alpha:  Math.random(),
    dAlpha: (Math.random() - 0.5) * 0.005,
    color,
  };
}

export const FullscreenCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;

    const particles = Array.from({ length: PARTICLE_COUNT }, createParticle);
    let rafId: number;
    let alive = true;

    const render = () => {
      if (!alive) return;
      rafId = requestAnimationFrame(render);

      // Fade trail
      ctx.fillStyle = 'rgba(0, 0, 0, 0.06)';
      ctx.fillRect(0, 0, W, H);

      particles.forEach(p => {
        p.x     += p.vx;
        p.y     += p.vy;
        p.alpha += p.dAlpha;

        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
        if (p.alpha <= 0 || p.alpha >= 1) p.dAlpha *= -1;
        p.alpha = Math.max(0, Math.min(1, p.alpha));

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${p.alpha.toFixed(2)})`;
        ctx.fill();

        // Glow
        ctx.beginPath();
        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius * 8);
        grad.addColorStop(0, `${p.color}${(p.alpha * 0.3).toFixed(2)})`);
        grad.addColorStop(1, `${p.color}0)`);
        ctx.arc(p.x, p.y, p.radius * 8, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
      });

      // Subtle grid overlay
      ctx.strokeStyle = 'rgba(15,98,254,0.025)';
      ctx.lineWidth   = 1;
      const gridStep  = 240;
      for (let x = 0; x < W; x += gridStep) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
      }
      for (let y = 0; y < H; y += gridStep) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
      }
    };

    render();
    return () => { alive = false; cancelAnimationFrame(rafId); };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={W}
      height={H}
      className="full-bleed-layer"
    />
  );
};
