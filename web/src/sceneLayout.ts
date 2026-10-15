import type { Scene, SceneBlock, VisualObject } from "./types";

export const identity = () => crypto.randomUUID().replaceAll("-", "");
export const emptyBlocks = (): SceneBlock[] => [20, 60, 20].map(height => ({
  id: identity(), width: 100, height, align: "center", object: null,
}));
export const newScene = (): Scene => ({ id: identity(), title: "Nova cena", narration: "", layout: "statement", items: [], blocks: emptyBlocks() });
export const newObject = (type: VisualObject["type"], id = identity()): VisualObject => ({
  id, type, width: 100, height: 100, horizontal: "center", vertical: "center",
  text: "", font: null, font_size: type === "title" ? 64 : 48, color: null,
  align: "left", asset_id: null, fit: "contain", zoom: 1, crop_x: 50, crop_y: 50,
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
