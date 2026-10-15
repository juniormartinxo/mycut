import { useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { Save, X } from "lucide-react";
import type { Scene } from "./types";
import "./SceneEditor.css";

export function SceneEditorDialog({ children, sceneNumber, scenes, busy, dirty, error, onSave, onClose, onSceneChange }: {
  children: ReactNode; sceneNumber: number; busy: boolean; dirty: boolean; error: string;
  scenes: Scene[]; onSceneChange: (index: number) => void; onSave: () => void; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const navigation = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const element = dialog.current!;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    element.showModal();
    return () => { element.close(); document.body.style.overflow = overflow; opener?.focus(); };
  }, []);
  useLayoutEffect(() => {
    navigation.current?.querySelector('[aria-current="step"]')?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [sceneNumber]);
  return createPortal(<dialog ref={dialog} className="scene-editor-dialog" aria-labelledby="scene-editor-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <header className="scene-editor-dialog-header">
      <div><h2 id="scene-editor-title">Editar cena {sceneNumber}</h2>
        <p role="status">{busy ? "Aguarde…" : dirty ? "Alterações não salvas" : "Salvo"}</p></div>
      <nav ref={navigation} className="scene-editor-navigation" aria-label="Navegação entre cenas">
        {scenes.map((scene, index) => <button key={scene.id || index} type="button" className="button secondary"
          aria-label={`Editar cena ${index + 1}`} aria-current={sceneNumber === index + 1 ? "step" : undefined}
          title={`Cena ${index + 1} · ${scene.title || "Sem título"}`} disabled={busy}
          onClick={() => onSceneChange(index)}>{String(index + 1).padStart(2, "0")}</button>)}
      </nav>
      <div className="scene-editor-dialog-actions">
        <button type="button" className="button primary" disabled={busy || !dirty} onClick={onSave}><Save size={17} /> Salvar</button>
        <button type="button" className="button secondary" disabled={busy} onClick={onClose}><X size={17} /> Fechar</button>
      </div>
    </header>
    <div className="scene-editor-dialog-body">
      {error && <p className="notice danger" role="alert">{error}</p>}
      {children}
    </div>
  </dialog>, document.body);
}
