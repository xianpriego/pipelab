// Plays interleaved float32 PCM chunks through the Web Audio API.

const JITTER_SECONDS = 0.15;
const MAX_LATENCY_SECONDS = 1.0;

export class PcmPlayer {
  private readonly context: AudioContext;
  private nextTime = 0;

  constructor() {
    this.context = new AudioContext();
  }

  push(samples: Float32Array, rate: number, channels: number): void {
    const frames = Math.floor(samples.length / Math.max(channels, 1));
    if (frames === 0) return;
    const buffer = this.context.createBuffer(channels, frames, rate);
    for (let channel = 0; channel < channels; channel += 1) {
      const data = buffer.getChannelData(channel);
      for (let i = 0; i < frames; i += 1) data[i] = samples[i * channels + channel];
    }
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    const now = this.context.currentTime;
    if (this.nextTime < now || this.nextTime - now > MAX_LATENCY_SECONDS) {
      this.nextTime = now + JITTER_SECONDS;
    }
    source.start(this.nextTime);
    this.nextTime += buffer.duration;
  }

  close(): void {
    void this.context.close();
  }
}
