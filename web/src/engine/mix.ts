/**
 * The sound of the composition (ADR 0019): one WebAudio graph, played in real time by the preview and rendered
 * offline by the export. Mono media reach both channels the same way on both sides (WebAudio up-mixing).
 */
import { audioPlan } from "./timeline.ts";
import type { AudioClip, Montage } from "./timeline.ts";

export const RATE = 48_000;

export class Mixer {
  private buffers = new Map<string, AudioBuffer>();

  constructor(
    private montage: Montage,
    private base: string,
  ) {}

  get plan() {
    return audioPlan(this.montage, RATE);
  }

  /** Decodes every audio resource the montage uses, at the rate of the mix. */
  async load(montage = this.montage) {
    this.montage = montage;
    const decoder = new OfflineAudioContext(2, RATE, RATE);
    const wanted = new Set(this.plan.map((clip) => clip.resource));
    await Promise.all(
      [...wanted]
        .filter((hash) => !this.buffers.has(hash))
        .map(async (hash) => {
          const response = await fetch(`${this.base}/resources/${hash}`);
          if (!response.ok) return;
          try {
            this.buffers.set(hash, await decoder.decodeAudioData(await response.arrayBuffer()));
          } catch {
            // A file the browser cannot decode stays silent, in the preview and in the export alike.
          }
        }),
    );
  }

  /**
   * Schedules what sounds from sample `from` of the mix on, with sample `from` played at context time `when`.
   * Returns the sources, so the preview can stop them.
   */
  schedule(context: BaseAudioContext, from: number, when: number, output: AudioNode) {
    const sources: AudioBufferSourceNode[] = [];
    for (const clip of this.plan) {
      const buffer = this.buffers.get(clip.resource);
      if (!buffer || clip.endSample <= from) continue;
      const first = Math.max(from, clip.startSample);
      const at = (sample: number) => when + (sample - from) / RATE;
      const source = context.createBufferSource();
      source.buffer = buffer;
      const gain = context.createGain();
      gain.gain.setValueAtTime(gainAt(clip, first), at(first));
      for (const sample of [clip.startSample + clip.fadeInSamples, clip.endSample - clip.fadeOutSamples, clip.endSample])
        if (sample > first) gain.gain.linearRampToValueAtTime(gainAt(clip, sample), at(sample));
      source.connect(gain).connect(output);
      const offset = clip.offsetSeconds + (first - clip.startSample) / RATE;
      if (offset < buffer.duration) {
        source.start(at(first), offset, (clip.endSample - first) / RATE);
        sources.push(source);
      }
    }
    return sources;
  }

  /** Export: [from, from + length) samples rendered offline, as interleaved stereo float32 in base64. */
  async render(from: number, length: number) {
    const context = new OfflineAudioContext(2, length, RATE);
    this.schedule(context, from, 0, context.destination);
    const buffer = await context.startRendering();
    const left = buffer.getChannelData(0);
    const right = buffer.getChannelData(1);
    const pcm = new Float32Array(length * 2);
    for (let i = 0; i < length; i++) {
      pcm[2 * i] = left[i];
      pcm[2 * i + 1] = right[i];
    }
    const bytes = new Uint8Array(pcm.buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(binary);
  }
}

/** Volume of a clip at a sample of the mix, with its fades. */
function gainAt(clip: AudioClip, sample: number) {
  const fadeIn = clip.fadeInSamples ? (sample - clip.startSample) / clip.fadeInSamples : 1;
  const fadeOut = clip.fadeOutSamples ? (clip.endSample - sample) / clip.fadeOutSamples : 1;
  return clip.volume * Math.min(1, Math.max(0, fadeIn), Math.max(0, fadeOut));
}
