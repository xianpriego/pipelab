// Fan-out of PCM chunks to whoever listens to a sink preview.

export type AudioListener = (samples: Float32Array, rate: number, channels: number) => void;

const listeners = new Map<string, Set<AudioListener>>();

export function subscribeAudio(nodeId: string, listener: AudioListener): () => void {
  let set = listeners.get(nodeId);
  if (!set) {
    set = new Set();
    listeners.set(nodeId, set);
  }
  set.add(listener);
  return () => {
    set?.delete(listener);
    if (set?.size === 0) listeners.delete(nodeId);
  };
}

export function publishAudio(nodeId: string, samples: Float32Array, rate: number, channels: number): void {
  listeners.get(nodeId)?.forEach((listener) => listener(samples, rate, channels));
}
