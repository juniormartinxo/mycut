/**
 * Export page of the composition engine (ADR 0019): a headless Chromium opens it at the project's size, asks
 * each frame with `seek` and captures the screen; `mix` renders the sound offline with the preview's graph.
 */
import "@fontsource-variable/manrope";
import { Mixer } from "./engine/mix";
import { Stage } from "./engine/stage";
import { frameCount } from "./engine/timeline";
import type { Montage } from "./engine/timeline";
import "./render.css";

let stage: Stage;
let mixer: Mixer;

async function load(montage: Montage, base: string) {
  stage = new Stage(document.getElementById("stage")!, montage, base);
  mixer = new Mixer(montage, base);
  await Promise.all([stage.load(), mixer.load()]);
  if (stage.preparing) throw new Error("Os quadros de um vídeo ainda estão sendo preparados.");
  await stage.seek(0);
  return { frames: frameCount(montage), animations: document.getAnimations().length };
}

declare global {
  interface Window {
    motor: {
      load: typeof load;
      seek: (ms: number) => Promise<void>;
      mix: (from: number, length: number) => Promise<string>;
    };
  }
}

window.motor = {
  load,
  seek: (ms) => stage.seek(ms),
  mix: (from, length) => mixer.render(from, length),
};
