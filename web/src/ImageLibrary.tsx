import { useState } from "react";
import { Check, Trash2 } from "lucide-react";
import type { ProjectImage, Scene } from "./types";
import { shotsOf } from "./sceneLayout";

/** Images shown by these scenes, in a block, a plano background or the older scene image. */
export function imagesInUse(scenes: Scene[]) {
  const used = new Set<string>();
  for (const scene of scenes) {
    if (scene.image_id) used.add(scene.image_id);
    if (!scene.blocks) continue;
    for (const shot of shotsOf(scene)) {
      if (shot.background?.kind === "image" && shot.background.asset_id) used.add(shot.background.asset_id);
      for (const block of shot.blocks)
        if (block.object?.type === "image" && block.object.asset_id) used.add(block.object.asset_id);
    }
  }
  return used;
}

/** The production's images as square, cropped previews side by side: click to use, trash to delete. */
export function ImageLibrary({ images, value, used, disabled, label, onSelect, onDelete }: {
  images: ProjectImage[]; value: string | null | undefined; used: Set<string>; disabled: boolean; label: string;
  onSelect: (id: string) => void; onDelete: (id: string) => void;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);
  if (!images.length) return <p className="block-hint">Nenhuma imagem nesta produção ainda. Importe a primeira abaixo.</p>;
  return <ul className="image-library" aria-label={label}>
    {images.map(image => {
      const selected = image.id === value, inUse = used.has(image.id);
      return <li key={image.id} className={selected ? "selected" : undefined}>
        <button type="button" className="image-library-pick" aria-pressed={selected} disabled={disabled}
          title={image.name} aria-label={`${image.name}${image.animated ? " · animada" : ""}`} onClick={() => onSelect(image.id)}>
          <img src={image.url} alt="" loading="lazy" draggable={false} />
          {image.animated && <span className="image-library-badge">Animada</span>}
          {selected && <span className="image-library-check" aria-hidden="true"><Check size={13} strokeWidth={3} /></span>}
        </button>
        {confirming === image.id ? <div className="image-library-confirm" role="group" aria-label={`Excluir ${image.name}?`}>
          <span>Excluir?</span>
          <button type="button" className="danger" disabled={disabled} onClick={() => { setConfirming(null); onDelete(image.id); }}>Excluir</button>
          <button type="button" onClick={() => setConfirming(null)}>Cancelar</button>
        </div> : <button type="button" className="image-library-delete" disabled={disabled || inUse}
          aria-label={`Excluir ${image.name}`} title={inUse ? "Em uso numa cena: troque-a antes de excluir" : `Excluir ${image.name}`}
          onClick={() => setConfirming(image.id)}><Trash2 size={13} /></button>}
      </li>;
    })}
  </ul>;
}
