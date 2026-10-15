import { useCallback, useEffect, useRef, useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import type { SceneClock } from "./types";

const FPS = 10;
const AHEAD = 8;
const PARALLEL = 3;

/** Plays an animated flow with frames rendered by the same server code as the export. */
export function useFlowPlayer(body: string, clock: SceneClock | null) {
  const [time, setTime] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [frame, setFrame] = useState<string | null>(null);
  const cache = useRef(new Map<number, string>());
  const pending = useRef(new Set<number>());
  const generation = useRef(0);
  const [, setLoaded] = useState(0);
  const last = clock ? Math.ceil(clock.duration*FPS) : 0;
  useEffect(() => {
    // A new draft invalidates every frame; the player returns to the final state.
    generation.current += 1;
    cache.current.forEach(url => URL.revokeObjectURL(url));
    cache.current.clear(); pending.current.clear();
    setTime(null); setPlaying(false); setFrame(null);
  }, [body]);
  useEffect(() => () => cache.current.forEach(url => URL.revokeObjectURL(url)), []);
  const load = useCallback((index: number) => {
    if (index < 0 || index > last || cache.current.has(index) || pending.current.has(index) || pending.current.size >= PARALLEL) return;
    const owner = generation.current;
    pending.current.add(index);
    fetch("/api/scene-preview", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...JSON.parse(body), elapsed: index/FPS }) })
      .then(response => { if (!response.ok) throw new Error("frame"); return response.blob(); })
      .then(blob => { if (owner === generation.current) { cache.current.set(index, URL.createObjectURL(blob)); setLoaded(n => n+1); } })
      .catch(() => {})
      .finally(() => { if (owner === generation.current) { pending.current.delete(index); setLoaded(n => n+1); } });
  }, [body, last]);
  const index = time === null ? null : Math.min(last, Math.round(time*FPS));
  useEffect(() => {
    if (index === null) { setFrame(null); return; }
    for (let next = index; next <= Math.min(last, index+(playing ? AHEAD : 0)); next++) load(next);
    const url = cache.current.get(index);
    if (url) setFrame(url);
  });
  const ready = index !== null && cache.current.has(index+1);
  useEffect(() => {
    if (!playing || index === null) return;
    if (index >= last) { setPlaying(false); return; }
    // Advance only when the next frame is ready, so playback never shows a stale state.
    if (!ready) return;
    const timer = setTimeout(() => setTime(t => Math.min(clock!.duration, (t ?? 0)+1/FPS)), 1000/FPS);
    return () => clearTimeout(timer);
  }, [playing, index, ready, last, clock]);
  return {
    time, playing, frame, buffering: playing && index !== null && index < last && !ready,
    play: () => { setTime(t => t === null || (clock && t >= clock.duration) ? 0 : t); setPlaying(true); },
    pause: () => setPlaying(false),
    seek: (value: number) => { setPlaying(false); setTime(value); },
    reset: () => { setPlaying(false); setTime(null); },
  };
}

export function FlowControls({ player, clock, disabled }: {
  player: ReturnType<typeof useFlowPlayer>; clock: SceneClock | null; disabled: boolean;
}) {
  if (!clock) return null;
  const seconds = (value: number) => `${value.toFixed(1).replace(".", ",")} s`;
  return <div className="flow-controls" role="group" aria-label="Prévia animada da cena">
    <button type="button" className="button secondary" disabled={disabled} onClick={player.playing ? player.pause : player.play}
      aria-label={player.playing ? "Pausar animação" : "Reproduzir animação"}>
      {player.playing ? <Pause size={15} /> : <Play size={15} />}
    </button>
    <input type="range" aria-label="Tempo da cena" min={0} max={clock.duration} step={1/FPS} disabled={disabled}
      value={player.time ?? clock.duration} onChange={e => player.seek(e.currentTarget.valueAsNumber)} />
    <output aria-live="off">{player.time === null ? "Estado final" : `${seconds(player.time)} de ${seconds(clock.duration)}`}</output>
    <button type="button" className="text-button" disabled={disabled || player.time === null} onClick={player.reset} aria-label="Mostrar estado final"><RotateCcw size={15} /></button>
    <small>{player.buffering ? "Preparando quadros…" : clock.source === "narration" ? "Tempos da narração gerada" : "Tempos estimados: gere a narração para sincronizar"}</small>
  </div>;
}
