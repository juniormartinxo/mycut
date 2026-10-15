import type { Scene, SceneBlock, Shot, VisualObject } from "./types";

export const identity = () => crypto.randomUUID().replaceAll("-", "");
export const emptyBlocks = (): SceneBlock[] => [20, 60, 20].map(height => ({
  id: identity(), width: 100, height, align: "center", object: null,
}));
export const newScene = (): Scene => ({ id: identity(), title: "Nova cena", narration: "", layout: "statement", items: [], blocks: emptyBlocks() });
export const newObject = (type: VisualObject["type"], id = identity()): VisualObject => ({
  id, type, width: 100, height: 100, horizontal: "center", vertical: "center",
  text: "", font: null, font_size: type === "title" ? 64 : type === "flow" ? 30 : 48, color: null,
  align: "left", asset_id: null, fit: "contain", zoom: 1, crop_x: 50, crop_y: 50,
  ...(type === "flow" ? { flow: null } : {}),
});
export function mediaExtent(block: SceneBlock, source: { width: number; height: number }) {
  const obj = block.object!;
  const width = 940 * block.width/100 * obj.width/100;
  const height = 1360 * block.height/100 * obj.height/100;
  const scale = Math.max(width/source.width, height/source.height) * (obj.zoom ?? 1);
  return { width: source.width*scale/width*100, height: source.height*scale/height*100 };
}
export function resizeBlockEdge(blocks: SceneBlock[], id: string, edge: "top" | "bottom", delta: number): SceneBlock[] {
  const index = blocks.findIndex(b => b.id === id);
  const neighbor = index + (edge === "top" ? -1 : 1);
  if (index < 0 || neighbor < 0 || neighbor >= blocks.length) return blocks;
  const growth = edge === "top" ? -delta : delta;
  const amount = Math.max(.1 - blocks[index].height, Math.min(blocks[neighbor].height - .1, growth));
  return blocks.map((b, i) => i === index ? { ...b, height: b.height + amount }
    : i === neighbor ? { ...b, height: b.height - amount } : b);
}
export function resizeBlock(blocks: SceneBlock[], id: string, height: number): SceneBlock[] {
  const index = blocks.findIndex(b => b.id === id);
  if (index < 0) return blocks;
  const edge = index === blocks.length - 1 ? "top" : "bottom";
  return resizeBlockEdge(blocks, id, edge, (height - blocks[index].height) * (edge === "top" ? -1 : 1));
}
export function appendBlock(blocks: SceneBlock[], source?: SceneBlock): SceneBlock[] {
  const height = 100 / (blocks.length + 1);
  const block: SceneBlock = source
    ? { ...structuredClone(source), id: identity(), height, object: source.object ? { ...source.object, id: identity() } : null }
    : { id: identity(), width: 100, height, align: "center", object: null };
  return [...blocks.map(b => ({ ...b, height: b.height * (100 - height) / 100 })), block];
}
export function removeBlock(blocks: SceneBlock[], id: string): SceneBlock[] {
  if (blocks.length === 1) return blocks;
  const remaining = blocks.filter(b => b.id !== id);
  const total = remaining.reduce((sum, b) => sum + b.height, 0);
  return remaining.map(b => ({ ...b, height: b.height / total * 100 }));
}

export const MAX_SHOTS = 12;
export const MAX_PROJECT_SHOTS = 60;
/** Every plano of a block scene; the first is the scene's own composition (ADR 0004). */
export function shotsOf(scene: Scene): Shot[] {
  return [{ id: scene.id!, anchor: null, transition: "cut", background: scene.background ?? null, brand: scene.brand ?? true, blocks: scene.blocks || [] },
    ...(scene.shots || [])];
}
/** Rebuilds the scene from its planos in order; the first keeps the scene's identity.
 * Values stay explicit (never deleted) because scene edits are merged into the draft. */
export function fromShots(scene: Scene, planos: Shot[]): Scene {
  const [first, ...rest] = planos;
  return { ...scene, blocks: first.blocks, background: first.background, brand: first.brand,
    shots: rest.map(s => s.id === scene.id ? { ...s, id: identity() } : s) };
}
export const withShot = (scene: Scene, index: number, values: Partial<Shot>) =>
  fromShots(scene, shotsOf(scene).map((s, i) => i === index ? { ...s, ...values } : s));
/** The scene as seen in one plano, for the static preview and agent proposals. */
export function shotView(scene: Scene, index: number): Scene {
  const shot = shotsOf(scene)[index] ?? shotsOf(scene)[0];
  const view: Scene = { ...scene, blocks: shot.blocks };
  delete view.shots; delete view.background; delete view.brand;
  if (shot.background) view.background = shot.background;
  if (!shot.brand) view.brand = false;
  return view;
}
const copyBlocks = (blocks: SceneBlock[]) => blocks.map(b => ({ ...structuredClone(b), id: identity(), object: b.object ? { ...structuredClone(b.object), id: identity() } : null }));
export function insertShot(scene: Scene, after: number, source?: Shot): Scene {
  const planos = shotsOf(scene);
  const shot: Shot = source ? { ...structuredClone(source), id: identity(), anchor: null, blocks: copyBlocks(source.blocks) }
    : { id: identity(), anchor: null, transition: "cut", background: null, brand: true, blocks: emptyBlocks() };
  return fromShots(scene, [...planos.slice(0, after+1), shot, ...planos.slice(after+1)]);
}
export function removeShot(scene: Scene, index: number): Scene {
  const planos = shotsOf(scene);
  return planos.length === 1 ? scene : fromShots(scene, planos.filter((_, i) => i !== index));
}
export function moveShot(scene: Scene, index: number, offset: -1 | 1): Scene {
  const planos = shotsOf(scene);
  const target = index + offset;
  if (target < 0 || target >= planos.length) return scene;
  [planos[index], planos[target]] = [planos[target], planos[index]];
  return fromShots(scene, planos);
}
export const shotCount = (scenes: Scene[]) => scenes.reduce((sum, s) => sum + 1 + (s.shots?.length ?? 0), 0);
/** Applies a change to one object wherever it sits among the planos. */
export const mapObject = (scene: Scene, id: string, change: (obj: VisualObject) => VisualObject) =>
  fromShots(scene, shotsOf(scene).map(s => ({ ...s, blocks: s.blocks.map(b => b.object?.id === id ? { ...b, object: change(b.object) } : b) })));
