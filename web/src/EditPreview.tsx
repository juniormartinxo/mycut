import { useEffect, useRef, useState } from "react";
import { LoaderCircle, Pause, Play } from "lucide-react";
import { snapToFrame } from "./EditFields";
import { Mixer, RATE } from "./engine/mix";
import { Stage } from "./engine/stage";
import type { EditProject } from "./types";

// The preview stays at 720p or less (Q34); the export draws the same frames at full size.
const PREVIEW_HEIGHT = 720;
// Margin for the first sound to be scheduled before it plays.
const START_DELAY = 0.1;

/**
 * Preview of the editing document in the composition engine (ADR 0019): stopped, it shows the exact frame of the
 * cursor; playing, the clock is the audio's and every frame drawn is the frame of that instant.
 */
export function EditPreview({
  project,
  cursor,
  onCursor,
}: {
  project: EditProject;
  cursor: number;
  onCursor: (ms: number) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLDivElement>(null);
  const engine = useRef<{ stage: Stage; mixer: Mixer } | null>(null);
  const playback = useRef<{ context: AudioContext; sources: AudioScheduledSourceNode[]; generation: number } | null>(null);
  const [loaded, setLoaded] = useState(0);
  const [shown, setShown] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [width, setWidth] = useState(0);
  const base = `/api/edit-projects/${project.id}`;
  const { width: W, height: H } = project.format;
  const zoom = Math.min(1, PREVIEW_HEIGHT / H, width ? width / W : 1);

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(frame.current!);
    return () => observer.disconnect();
  }, []);

  // A new revision redraws the montage; media already decoded stay in the browser's cache.
  useEffect(() => {
    let current = true;
    stop();
    setShown(null);
    const loading = engine.current
      ? Promise.all([engine.current.stage.load(project), engine.current.mixer.load(project)])
      : (() => {
          engine.current = { stage: new Stage(host.current!, project, base), mixer: new Mixer(project, base) };
          return Promise.all([engine.current.stage.load(), engine.current.mixer.load()]);
        })();
    void loading.then(() => {
      if (!current) return;
      setPreparing(engine.current!.stage.preparing);
      setLoaded((n) => n + 1);
    });
    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, project.revision]);

  useEffect(() => {
    if (engine.current) engine.current.stage.zoom = zoom;
  }, [zoom, loaded]);

  // Videos still being prepared show as media sketches until their frames exist.
  useEffect(() => {
    if (!preparing) return;
    const timer = window.setInterval(async () => {
      const stage = engine.current!.stage;
      if (await stage.refreshVideos()) setLoaded((n) => n + 1);
      setPreparing(stage.preparing);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [preparing]);

  useEffect(() => {
    if (!loaded || playing) return;
    let current = true;
    setShown(null);
    void engine.current!.stage.seek(cursor).then(() => current && setShown(cursor));
    return () => {
      current = false;
    };
  }, [cursor, loaded, playing]);

  useEffect(() => () => stop(), []);

  function stop() {
    const active = playback.current;
    if (!active) return;
    active.generation++;
    for (const source of active.sources) {
      try {
        source.stop();
      } catch {
        // Already stopped.
      }
    }
    active.sources = [];
    setPlaying(false);
  }

  async function play() {
    const { stage, mixer } = engine.current!;
    const active = playback.current ?? { context: new AudioContext({ sampleRate: RATE, latencyHint: "interactive" }), sources: [], generation: 0 };
    playback.current = active;
    await active.context.resume();
    const from = cursor >= project.duration_ms ? 0 : cursor;
    const when = active.context.currentTime + START_DELAY;
    active.sources = mixer.schedule(active.context, Math.round((from * RATE) / 1000), when, active.context.destination);
    const generation = ++active.generation;
    setPlaying(true);
    let reported = 0;
    const step = (now: number) => {
      if (active.generation !== generation) return;
      const { contextTime } = active.context.getOutputTimestamp();
      const ms = Math.min(project.duration_ms, from + Math.max(0, (contextTime ?? active.context.currentTime) - when) * 1000);
      stage.show(ms);
      if (now - reported > 100 || ms >= project.duration_ms) {
        reported = now;
        onCursor(Math.round(ms));
      }
      if (ms >= project.duration_ms) return stop();
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // Goes to the frame of a typed instant.
  function go(text: string) {
    const seconds = Number(text.replace(",", "."));
    if (!Number.isFinite(seconds)) return;
    const ms = snapToFrame(seconds * 1000, project.format.fps);
    if (ms !== cursor) onCursor(ms);
  }

  return (
    <section className="edit-preview" aria-labelledby="preview-heading">
      <div className="edit-preview-heading">
        <h2 id="preview-heading">Prévia</h2>
        <small>
          {Math.round(W * zoom)}×{Math.round(H * zoom)}
          {preparing && " · preparando os quadros dos vídeos"}
        </small>
      </div>
      <div className="edit-preview-frame" ref={frame}>
        <div
          className="edit-preview-stage"
          ref={host}
          role="img"
          aria-label="Quadro da prévia"
          data-ms={playing ? undefined : (shown ?? undefined)}
          style={{ width: W * zoom, height: H * zoom }}
        />
        {!loaded && <LoaderCircle className="spin edit-preview-loading" />}
      </div>
      <div className="edit-preview-controls">
        <button
          type="button"
          className="button secondary"
          disabled={!loaded}
          onClick={() => (playing ? stop() : void play())}
        >
          {playing ? <Pause size={16} /> : <Play size={16} />}
          {playing ? "Pausar" : "Tocar"}
        </button>
        <label>
          Instante (s)
          <input
            type="number"
            inputMode="decimal"
            min={0}
            step={1 / project.format.fps}
            key={playing ? "tocando" : cursor}
            defaultValue={cursor / 1000}
            disabled={playing}
            onKeyDown={(e) => e.key === "Enter" && go(e.currentTarget.value)}
            onBlur={(e) => go(e.currentTarget.value)}
          />
        </label>
      </div>
    </section>
  );
}
