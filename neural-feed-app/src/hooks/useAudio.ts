import { useCallback, useRef } from 'react';
import { useNeuralFeedStore } from '../store/neuralFeedStore';

type AudioEngine = {
  playNodeFire: (clusterIndex: number) => void;
};

// Lazy-load Tone.js to avoid blocking initial render
async function createAudioEngine(): Promise<AudioEngine> {
  const Tone = await import('tone');
  await Tone.start();

  const synth = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: 'sine' },
    envelope: { attack: 0.01, decay: 0.35, sustain: 0, release: 0.2 },
    volume: -18,
  }).toDestination();

  const NOTES = ['C2', 'D2', 'E2', 'G2', 'A2', 'B2', 'C3'];

  return {
    playNodeFire: (clusterIndex: number) => {
      const note = NOTES[clusterIndex % NOTES.length];
      synth.triggerAttackRelease(note, '16n');
    },
  };
}

export function useAudio() {
  const audioEnabled = useNeuralFeedStore(s => s.audioEnabled);
  const engineRef    = useRef<AudioEngine | null>(null);
  const loadingRef   = useRef(false);

  const ensureEngine = useCallback(async () => {
    if (engineRef.current || loadingRef.current) return;
    loadingRef.current = true;
    engineRef.current  = await createAudioEngine();
    loadingRef.current = false;
  }, []);

  const playNodeFire = useCallback(
    async (clusterIndex: number) => {
      if (!audioEnabled) return;
      await ensureEngine();
      engineRef.current?.playNodeFire(clusterIndex);
    },
    [audioEnabled, ensureEngine],
  );

  return { playNodeFire };
}
