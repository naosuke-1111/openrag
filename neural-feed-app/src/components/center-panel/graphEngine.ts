/**
 * Three.js scene setup for the Neural Graph.
 * Responsible for scene, camera, renderer, and the main animation loop.
 */
import * as THREE from 'three';

export const CANVAS_W = 3840;
export const CANVAS_H = 1890;

export interface GraphEngineContext {
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  renderer: THREE.WebGLRenderer;
  clock: THREE.Clock;
  dispose: () => void;
}

export function createGraphEngine(canvas: HTMLCanvasElement): GraphEngineContext {
  // ——— Renderer ————————————————————————————
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance',
  });
  renderer.setSize(CANVAS_W, CANVAS_H, false);
  renderer.setPixelRatio(1); // 1:1 on LED panels
  renderer.setClearColor(0x000000, 0);

  // ——— Scene ———————————————————————————————
  const scene = new THREE.Scene();
  scene.fog   = new THREE.FogExp2(0x000000, 0.00035);

  // Ambient light — very dim
  const ambient = new THREE.AmbientLight(0x0a0a1a, 1);
  scene.add(ambient);

  // ——— Camera ——————————————————————————————
  const camera = new THREE.PerspectiveCamera(55, CANVAS_W / CANVAS_H, 1, 8000);
  camera.position.set(0, 200, 1400);
  camera.lookAt(0, 0, 0);

  const clock = new THREE.Clock();

  const dispose = () => {
    renderer.dispose();
  };

  return { scene, camera, renderer, clock, dispose };
}

// ——— Camera orbit ——————————————————————————
const ORBIT_RADIUS = 1400;
const ORBIT_SPEED  = 0.00025; // rad/ms
let theta = 0;

export function updateCameraOrbit(camera: THREE.Camera, delta: number) {
  theta += ORBIT_SPEED * delta * 1000;
  camera.position.set(
    Math.sin(theta) * ORBIT_RADIUS,
    200 + Math.sin(theta * 0.5) * 100,
    Math.cos(theta) * ORBIT_RADIUS,
  );
  camera.lookAt(0, 0, 0);
}
