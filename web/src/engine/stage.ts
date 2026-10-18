/**
 * Draws `frameAt(montage, ms)` on the DOM (ADR 0019). The editor's preview and the export page use this same
 * code: the preview at a reduced size through `zoom` (never `transform: scale()`), the export at full size while
 * a headless Chromium captures each frame.
 *
 * Nothing here reads a clock, schedules a timer or uses a CSS animation or transition: a frame depends on its
 * instant only. Media files come from `base`: `${base}/resources/<hash>` and the prepared frames of each video
 * under `${base}/frames/<hash>`.
 */
import { frameAt } from "./timeline.ts";
import type { Layer, Montage } from "./timeline.ts";
import "./stage.css";

/** The frames of a video, prepared by the service at the project's fps (a `<video>` is not frame-exact). */
export type VideoFrames = { state: "ready"; fps: number; count: number } | { state: "preparing" | "failed" };

export const FONT = "Manrope Variable";
const SKETCH = "Esboço de mídia";

function element(tag: string, className: string, parent?: HTMLElement) {
  const node = document.createElement(tag);
  node.className = className;
  parent?.appendChild(node);
  return node;
}

type Drawn = { root: HTMLElement; content: HTMLElement; image?: HTMLImageElement; label?: HTMLElement; kind: string };

export class Stage {
  readonly root: HTMLElement;
  private montage: Montage;
  private drawn = new Map<string, Drawn>();
  private videos = new Map<string, VideoFrames>();
  // Only for speed: decoding a frame again gives the same picture.
  private decoded = new Map<string, Promise<void>>();
  private ready = new Set<string>();

  constructor(
    host: HTMLElement,
    montage: Montage,
    private base: string,
  ) {
    this.montage = montage;
    host.replaceChildren();
    this.root = element("div", "stage", host);
    this.resize();
  }

  /** Fonts, images and the frames of each video are ready before the first frame is drawn. */
  async load(montage = this.montage) {
    this.montage = montage;
    this.resize();
    for (const drawn of this.drawn.values()) drawn.root.remove();
    this.drawn.clear();
    await document.fonts.load(`64px "${FONT}"`);
    await document.fonts.ready;
    const used = new Set(montage.items.map((item) => item.resource));
    await Promise.all(
      montage.resources
        .filter((r) => used.has(r.hash))
        .map(async (resource) => {
          if (resource.media_type.startsWith("video/")) this.videos.set(resource.hash, await this.videoFrames(resource.hash));
          else if (resource.media_type.startsWith("image/")) await this.decode(this.url(resource.hash)).catch(() => undefined);
        }),
    );
  }

  /** Waits for the frames of the videos still being prepared; true when one of them became ready. */
  async refreshVideos() {
    let changed = false;
    for (const [hash, frames] of this.videos)
      if (frames.state === "preparing") {
        const now = await this.videoFrames(hash);
        changed ||= now.state !== frames.state;
        this.videos.set(hash, now);
      }
    return changed;
  }

  get preparing() {
    return [...this.videos.values()].some((frames) => frames.state === "preparing");
  }

  /** Scale of the drawing; the preview stays at 720p or less. */
  set zoom(value: number) {
    this.root.style.zoom = value === 1 ? "" : String(value);
  }

  /** Goes to ms and resolves once the whole frame is on screen, video frames included. */
  async seek(ms: number) {
    const frame = frameAt(this.montage, ms);
    await Promise.all(frame.layers.map((layer) => this.frameUrl(layer)).filter(Boolean).map((url) => this.decode(url!)));
    // An <img> given a new source paints it only once decoded too.
    await Promise.all(this.draw(frame.layers, false));
  }

  /** While playing: draws at once, keeping a video's previous frame until the new one is decoded. */
  show(ms: number) {
    this.draw(frameAt(this.montage, ms).layers, true);
  }

  private resize() {
    const { width, height } = this.montage.format;
    Object.assign(this.root.style, { width: `${width}px`, height: `${height}px` });
  }

  private url(hash: string) {
    return `${this.base}/resources/${hash}`;
  }

  private async videoFrames(hash: string): Promise<VideoFrames> {
    try {
      const response = await fetch(`${this.base}/frames/${hash}`);
      return response.ok ? ((await response.json()) as VideoFrames) : { state: "failed" };
    } catch {
      return { state: "failed" };
    }
  }

  private frameUrl(layer: Layer) {
    const media = layer.media;
    if (!media?.resource) return null;
    if (media.type === "image") return this.url(media.resource);
    const frames = this.videos.get(media.resource);
    if (media.type !== "video" || frames?.state !== "ready") return null;
    const index = Math.min(frames.count - 1, Math.max(0, Math.floor((media.sourceMs * frames.fps) / 1000 + 1e-6)));
    return `${this.base}/frames/${media.resource}/${index}.jpg`;
  }

  private decode(url: string) {
    let done = this.decoded.get(url);
    if (!done) {
      const image = new Image();
      image.src = url;
      done = image.decode().then(() => void this.ready.add(url));
      this.decoded.set(url, done);
      if (this.decoded.size > 240) {
        const oldest = this.decoded.keys().next().value!;
        this.decoded.delete(oldest);
        this.ready.delete(oldest);
      }
    }
    return done;
  }

  private draw(layers: Layer[], playing: boolean) {
    const loading: Promise<void>[] = [];
    const shown = new Set(layers.map((layer) => layer.id));
    for (const [id, drawn] of this.drawn) if (!shown.has(id)) drawn.root.style.visibility = "hidden";
    layers.forEach((layer, order) => {
      const drawn = this.drawnFor(layer);
      const { root } = drawn;
      const { box } = layer;
      Object.assign(root.style, {
        visibility: "visible",
        zIndex: String(order + 1),
        left: `${box.x}px`,
        top: `${box.y}px`,
        width: `${box.width}px`,
        height: `${box.height}px`,
        opacity: String(layer.opacity),
        transform: `translateY(${layer.text?.offsetY ?? 0}px) rotate(${layer.rotation}deg) scale(${layer.scale})`,
        filter:
          layer.brightness === 1 && layer.contrast === 1 && layer.saturation === 1 && layer.blur === 0
            ? "none"
            : `brightness(${layer.brightness}) contrast(${layer.contrast}) saturate(${layer.saturation}) blur(${layer.blur}px)`,
      });
      if (layer.text) this.drawText(drawn, layer);
      else {
        const load = this.drawMedia(drawn, layer, playing);
        if (load) loading.push(load);
      }
    });
    return loading;
  }

  private drawnFor(layer: Layer) {
    const kind = layer.text ? "text" : (this.frameUrl(layer) ? "media" : "sketch");
    let drawn = this.drawn.get(layer.id);
    if (drawn?.kind !== kind) {
      drawn?.root.remove();
      const root = element("div", `stage-layer ${kind}`, this.root);
      const content = element("div", "stage-content", root);
      drawn = { root, content, kind };
      if (kind === "media") drawn.image = element("img", "", content) as HTMLImageElement;
      if (kind === "sketch") {
        element("span", "stage-sketch-icon", content).textContent = "▣";
        drawn.label = element("span", "stage-sketch-label", content);
      }
      this.drawn.set(layer.id, drawn);
    }
    return drawn;
  }

  private drawText(drawn: Drawn, layer: Layer) {
    const text = layer.text!;
    const visible = text.content.slice(0, text.visibleChars);
    // Built with textContent, never innerHTML: the author's text appears as written.
    if (drawn.content.textContent !== visible) drawn.content.textContent = visible;
    Object.assign(drawn.content.style, {
      color: text.color,
      fontFamily: `"${text.fontFamily}", "${FONT}", sans-serif`,
      fontSize: `${text.fontSize}px`,
      textAlign: text.align,
      justifyContent: { left: "flex-start", center: "center", right: "flex-end" }[text.align],
    });
  }

  private drawMedia(drawn: Drawn, layer: Layer, playing: boolean) {
    const media = layer.media!;
    const { width, height } = layer.box;
    const move = `translate(${media.panX * width}px, ${media.panY * height}px) scale(${media.zoom})`;
    if (drawn.label) {
      const resource = this.montage.resources.find((r) => r.hash === media.resource);
      drawn.label.textContent = resource ? `${SKETCH}: ${resource.name}` : SKETCH;
      drawn.content.style.transform = move;
      return;
    }
    const image = drawn.image!;
    const url = this.frameUrl(layer)!;
    image.style.objectFit = media.fit;
    image.style.transform = move;
    if (image.getAttribute("src") === url) return image.complete ? undefined : image.decode().catch(() => undefined);
    if (!playing) {
      image.src = url;
      return image.decode().catch(() => undefined);
    }
    if (this.ready.has(url)) image.src = url;
    else void this.decode(url);
  }
}
