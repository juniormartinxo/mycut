/**
 * The temporal evaluator of the composition engine (ADR 0019): what every frame and every audio sample of the
 * editing document shows, as a function of time only. The preview and the export both ask it, so they resolve
 * the same montage.
 *
 * Time never accumulates: a frame's instant comes from its index (`frameTime`) and an audio item's position from
 * its own start in ms (`audioPlan`), so rounding to frames or samples cannot drift over a long video.
 */
import type { EditFormat, EditGeometry, EditResource, EditTrack } from "../types.ts";

export type Easing = "linear" | "ease" | "hold";
export type Keyframe = { at_ms: number; value: number; easing: Easing };
export type Transition = { kind: "fade" | "dissolve" | "rise" | "pop" | "type" | "sink"; duration_ms: number };
export type Freeze = { at_ms: number; duration_ms: number };
export type MontageItem = {
  id: string;
  track_id: string;
  scene_id: string | null;
  start_ms: number;
  duration_ms: number;
  source_start_ms: number;
  layer: number;
  geometry: EditGeometry | null;
  text: string | null;
  resource: string | null;
  resolved_style: Record<string, { value: string | number; inherited: boolean }>;
  keyframes: Record<string, Keyframe[]>;
  enter: Transition | null;
  exit: Transition | null;
  speed: number;
  freeze: Freeze | null;
};
/** What the engine needs of a project: the editing document as the service presents it. */
export type Montage = {
  format: EditFormat;
  tracks: EditTrack[];
  resources: EditResource[];
  items: MontageItem[];
  duration_ms: number;
};

export type MediaState = {
  type: "image" | "video" | "sketch";
  resource: string | null;
  /** Moment of the media shown, in ms of the media. */
  sourceMs: number;
  fit: "cover" | "contain";
  zoom: number;
  panX: number;
  panY: number;
};
export type TextState = {
  content: string;
  visibleChars: number;
  offsetY: number;
  color: string;
  fontFamily: string;
  fontSize: number;
  align: "left" | "center" | "right";
};
export type Layer = {
  id: string;
  kind: "visual" | "text";
  box: EditGeometry;
  opacity: number;
  scale: number;
  rotation: number;
  brightness: number;
  contrast: number;
  saturation: number;
  blur: number;
  media?: MediaState;
  text?: TextState;
};
export type Frame = { ms: number; layers: Layer[] };
export type AudioClip = {
  id: string;
  resource: string;
  startSample: number;
  endSample: number;
  offsetSeconds: number;
  volume: number;
  fadeInSamples: number;
  fadeOutSamples: number;
};

const AUDIO = new Set(["narration", "music", "effects"]);
export const isAudio = (kind: string) => AUDIO.has(kind);
// Distance travelled by a text that rises in or sinks out, in pixels of the composition.
const TEXT_TRAVEL = 40;
const POP_FROM = 0.6;

const clamp = (value: number, low = 0, high = 1) => Math.min(high, Math.max(low, value));
// Rounded so that the same instant always describes the same frame, whatever path led to it.
const round = (value: number) => Math.round(value * 1e6) / 1e6;
const smooth = (p: number) => p * p * (3 - 2 * p);
const settle = (p: number) => 1 - (1 - p) ** 3;

export const frameTime = (index: number, fps: number) => (index * 1000) / fps;
export const frameCount = (montage: Montage) => Math.ceil(round((montage.duration_ms * montage.format.fps) / 1000));
const end = (item: MontageItem) => item.start_ms + item.duration_ms;

/** Moment of the media at local ms of the item: plays at its speed and stops on the held frame. */
export function sourceAt(item: MontageItem, local: number) {
  let played = local;
  if (item.freeze) {
    const { at_ms, duration_ms } = item.freeze;
    played = local < at_ms ? local : Math.max(at_ms, local - duration_ms);
  }
  return round(item.source_start_ms + played * item.speed);
}

function eased(easing: Easing, p: number) {
  return easing === "hold" ? 0 : easing === "ease" ? smooth(p) : p;
}

/** A property at local ms: its points in time when it has them, otherwise its single value. */
export function valueAt(points: Keyframe[] | undefined, local: number, fallback: number) {
  if (!points?.length) return fallback;
  if (local <= points[0].at_ms) return points[0].value;
  const last = points[points.length - 1];
  if (local >= last.at_ms) return last.value;
  let k = 0;
  while (points[k + 1].at_ms <= local) k++;
  const a = points[k];
  const b = points[k + 1];
  return round(a.value + (b.value - a.value) * eased(a.easing, (local - a.at_ms) / (b.at_ms - a.at_ms)));
}

/** Entrance and exit lengths; when they would overlap, both shrink in proportion. */
function transitions(item: MontageItem) {
  const enter = item.enter?.duration_ms ?? 0;
  const exit = item.exit?.duration_ms ?? 0;
  const fit = enter + exit > item.duration_ms ? item.duration_ms / (enter + exit) : 1;
  return { enter: enter * fit, exit: exit * fit };
}

function style(item: MontageItem, name: string, fallback: number): number;
function style(item: MontageItem, name: string, fallback: string): string;
function style(item: MontageItem, name: string, fallback: number | string) {
  const value = item.resolved_style[name]?.value;
  return value === undefined ? fallback : value;
}

function mediaType(montage: Montage, item: MontageItem): MediaState["type"] {
  const resource = montage.resources.find((r) => r.hash === item.resource);
  if (!resource) return "sketch";
  return resource.media_type.startsWith("video/") ? "video" : "image";
}

type Index = { tracks: Map<string, { kind: EditTrack["kind"]; index: number }>; covers: Map<string, MontageItem> };
// Only for speed: what the index holds depends on the montage alone, never on the frames asked before.
const indexes = new WeakMap<Montage, Index>();

/** Track of each item, and the item a dissolve covers: the one before it on its track, ending where it starts. */
function indexOf(montage: Montage) {
  let index = indexes.get(montage);
  if (!index) {
    const covers = new Map<string, MontageItem>();
    const ends = new Map(montage.items.map((item) => [`${item.track_id}:${end(item)}`, item]));
    for (const next of montage.items) {
      const before = next.enter?.kind === "dissolve" && ends.get(`${next.track_id}:${next.start_ms}`);
      if (before && before.id !== next.id) covers.set(before.id, next);
    }
    index = { tracks: new Map(montage.tracks.map((track, k) => [track.id, { kind: track.kind, index: k }])), covers };
    indexes.set(montage, index);
  }
  return index;
}

function layerAt(montage: Montage, item: MontageItem, kind: "visual" | "text", ms: number, covered: boolean): Layer {
  // An item covered by a dissolve goes on under it, past its end, and the dissolve takes the place of its exit.
  const local = ms - item.start_ms;
  const { enter, exit } = transitions(item);
  const entering = item.enter && enter > 0 && local < enter ? local / enter : 1;
  const leaving = !covered && item.exit && exit > 0 && local > item.duration_ms - exit ? (item.duration_ms - local) / exit : 1;
  const value = (name: string, fallback: number) => valueAt(item.keyframes[name], local, style(item, name, fallback));
  const geometry = item.geometry!;
  let opacity = value("opacity", 1);
  let scale = value("scale", 1);
  let offsetY = 0;
  let visibleChars = item.text?.length ?? 0;
  const enterKind = item.enter?.kind;
  const exitKind = item.exit?.kind;
  if (entering < 1 && enterKind !== "type") opacity *= entering;
  if (entering < 1 && enterKind === "rise") offsetY += TEXT_TRAVEL * (1 - settle(entering));
  if (entering < 1 && enterKind === "pop") scale *= POP_FROM + (1 - POP_FROM) * settle(entering);
  if (entering < 1 && enterKind === "type") visibleChars = Math.ceil(round(visibleChars * entering));
  if (leaving < 1) opacity *= leaving;
  if (leaving < 1 && exitKind === "sink") offsetY += TEXT_TRAVEL * (1 - leaving);
  if (leaving < 1 && exitKind === "pop") scale *= POP_FROM + (1 - POP_FROM) * leaving;
  const layer: Layer = {
    id: item.id,
    kind,
    box: { x: value("x", geometry.x), y: value("y", geometry.y), width: geometry.width, height: geometry.height },
    opacity: round(clamp(opacity)),
    scale: round(scale),
    rotation: value("rotation", 0),
    brightness: value("brightness", 1),
    contrast: value("contrast", 1),
    saturation: value("saturation", 1),
    blur: value("blur", 0),
  };
  if (kind === "visual") {
    layer.media = {
      type: mediaType(montage, item),
      resource: item.resource,
      sourceMs: sourceAt(item, local),
      fit: style(item, "fit", "cover") === "contain" ? "contain" : "cover",
      zoom: value("zoom", 1),
      panX: value("pan_x", 0),
      panY: value("pan_y", 0),
    };
  } else {
    layer.text = {
      content: item.text ?? "",
      visibleChars,
      offsetY: round(offsetY),
      color: style(item, "color", "#ffffff"),
      fontFamily: style(item, "font_family", "Manrope"),
      fontSize: style(item, "font_size", 64),
      align: style(item, "align", "center") as TextState["align"],
    };
  }
  return layer;
}

/** Everything drawn at ms, bottom to top: by visual order, then by track (later tracks on top), then by start. */
export function frameAt(montage: Montage, ms: number): Frame {
  const { tracks: kinds, covers } = indexOf(montage);
  const shown: { item: MontageItem; covered: boolean }[] = [];
  for (const item of montage.items) {
    const track = kinds.get(item.track_id);
    if (!track || AUDIO.has(track.kind) || !item.geometry) continue;
    const next = covers.get(item.id);
    const until = next ? next.start_ms + transitions(next).enter : end(item);
    if (item.start_ms <= ms && ms < until) shown.push({ item, covered: Boolean(next) });
  }
  shown.sort(
    (a, b) =>
      a.item.layer - b.item.layer ||
      kinds.get(a.item.track_id)!.index - kinds.get(b.item.track_id)!.index ||
      a.item.start_ms - b.item.start_ms,
  );
  return {
    ms,
    layers: shown.map(({ item, covered }) =>
      layerAt(montage, item, kinds.get(item.track_id)!.kind === "text" ? "text" : "visual", ms, covered),
    ),
  };
}

/** Where each audio item sounds, in samples of the mix; each position comes from the item's own ms. */
export function audioPlan(montage: Montage, rate: number): AudioClip[] {
  const kinds = new Map(montage.tracks.map((track) => [track.id, track.kind]));
  const sample = (ms: number) => Math.round((ms * rate) / 1000);
  return montage.items
    .filter((item) => AUDIO.has(kinds.get(item.track_id) ?? "") && item.resource)
    .map((item) => {
      const { enter, exit } = transitions(item);
      return {
        id: item.id,
        resource: item.resource!,
        startSample: sample(item.start_ms),
        endSample: sample(end(item)),
        offsetSeconds: item.source_start_ms / 1000,
        volume: style(item, "volume", 1),
        fadeInSamples: item.enter ? sample(enter) : 0,
        fadeOutSamples: item.exit ? sample(exit) : 0,
      };
    });
}
