import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties, PointerEvent } from "react";
import { ArrowDown, ArrowUp, Copy, Plus, Redo2, Sparkles, Trash2, Undo2, Upload } from "lucide-react";
import type { Project, Scene, SceneBlock, SceneClock, SceneIssue, SceneThread, ShortFormat, VisualObject } from "./types";
import { request } from "./api";
import { RenderedScene } from "./FormatPicker";
import { GoogleFontPicker } from "./GoogleFontPicker";
import { SceneConversation } from "./SceneConversation";
import { FlowControls, useFlowPlayer } from "./FlowPlayer";
import { appendBlock, mediaExtent, newObject, removeBlock, resizeBlock, resizeBlockEdge } from "./sceneLayout";
import "./SceneEditor.css";

const labels = { flow: "Fluxo animado", title: "Título", paragraph: "Parágrafo", image: "Imagem", video: "Vídeo" };
const FLOW_REQUEST = "Monte um Fluxo animado para este objeto a partir da narração da cena: você decide nós, posições, conexões, etapas e a animação.";
const horizontal = { left: "Esquerda", center: "Centro", right: "Direita" };

function NumberField({ label, value, onChange, max = 100, min = .1 }: {
  label: string; value: number; onChange: (value: number) => void; max?: number; min?: number;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return <label>{label}<input type="number" inputMode="decimal" min={min} max={max} step="0.1" value={draft ?? Number(value.toFixed(2))}
    onChange={e => {
      setDraft(e.currentTarget.value);
      const next = e.currentTarget.valueAsNumber;
      if (Number.isFinite(next) && next >= min && next <= max && next !== value) onChange(next);
    }}
    onBlur={() => setDraft(null)}
    onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); } }} /></label>;
}

export function SceneEditor({ project, scene, disabled, onChange, save, onProject, onBusy }: {
  project: Project; scene: Scene; disabled: boolean; onChange: (scene: Scene) => void;
  save: () => Promise<Project>; onProject: (project: Project) => void; onBusy: (busy: boolean) => void;
}) {
  const [selected, setSelected] = useState(scene.blocks?.[0]?.id || "");
  const [past, setPast] = useState<Scene[]>([]);
  const [future, setFuture] = useState<Scene[]>([]);
  const [threads, setThreads] = useState<SceneThread[]>([]);
  const [issues, setIssues] = useState<SceneIssue[]>([]);
  const [warnings, setWarnings] = useState<SceneIssue[]>([]);
  const [clock, setClock] = useState<SceneClock | null>(null);
  const [agentRequest, setAgentRequest] = useState<{ key: number; text: string } | null>(null);
  const [error, setError] = useState("");
  const [inspectionError, setInspectionError] = useState("");
  const [pending, setPending] = useState(false);
  const [activeTab, setActiveTab] = useState("object");
  const tabId = useId();
  const conversation = activeTab === "agent";
  const [formats, setFormats] = useState<ShortFormat[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    request<{ formats: ShortFormat[] }>("/formats", { signal: controller.signal }).then(data => setFormats(data.formats)).catch(() => {});
    return () => controller.abort();
  }, []);
  const mediaBackground = project.visual_style?.background || formats.find(format => format.id === (project.visual_style?.format_id || "editorial"))?.background;
  const canvas = useRef<HTMLDivElement>(null);
  const mediaInput = useRef<HTMLInputElement>(null);
  const drag = useRef<{ scene: Scene; x: number; y: number; mode: "block" | "object" | "top" | "bottom" | "media"; width: number; height: number } | null>(null);
  const latest = useRef(scene);
  latest.current = scene;
  const blocks = scene.blocks || [];
  const block = blocks.find(b => b.id === selected) || blocks[0];
  const obj = block?.object;
  const media = obj?.type === "image" ? project.images?.find(asset => asset.id === obj.asset_id)
    : obj?.type === "video" ? project.videos?.find(asset => asset.id === obj.asset_id) : undefined;
  const mediaUrl = media && ("poster_url" in media ? media.poster_url : media.url);
  const extent = media && obj?.fit === "cover" ? mediaExtent(block, media) : null;
  const blockIndex = blocks.indexOf(block);
  const locked = disabled || pending;
  useEffect(() => {
    let alive = true;
    request<{ threads: SceneThread[] }>(`/projects/${project.id}/scene-conversations`)
      .then(data => { if (alive) setThreads(data.threads); }).catch(() => {});
    return () => { alive = false; };
  }, [project.id, project.revision, conversation]);
  const inspectBody = JSON.stringify({ scene, project_id: project.id, accent: project.accent, visual_style: project.visual_style || null });
  useEffect(() => {
    if (!scene.blocks) { setIssues([]); return; }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      request<{ issues: SceneIssue[]; warnings?: SceneIssue[]; clock?: SceneClock }>("/scene-layout/inspect", { method: "POST", body: inspectBody, signal: controller.signal })
        .then(result => { if (!controller.signal.aborted) { setIssues(result.issues); setWarnings(result.warnings || []); setClock(result.clock || null); setInspectionError(""); } })
        .catch(e => { if (!controller.signal.aborted) setInspectionError(e.message); });
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [inspectBody, scene.blocks]);
  const animated = blocks.some(b => b.object?.type === "flow" && b.object.flow);
  const player = useFlowPlayer(inspectBody, animated ? clock : null);
  const askAgent = (text = FLOW_REQUEST) => { setActiveTab("agent"); setAgentRequest({ key: Date.now(), text }); };
  const nodeName = (id: string | null) => obj?.flow?.nodes.find(n => n.id === id)?.label ?? id;
  const change = (next: Scene) => {
    setPast(old => [...old.slice(-99), structuredClone(scene)]); setFuture([]); onChange(next);
  };
  const changeBlocks = (next: SceneBlock[]) => change({ ...scene, blocks: next });
  const patchBlock = (values: Partial<SceneBlock>) => changeBlocks(blocks.map(b => b.id === block.id ? { ...b, ...values } : b));
  const patchObject = (values: Partial<VisualObject>) => patchBlock({ object: { ...obj!, ...values } });
  const undo = () => {
    if (!past.length) return;
    const previous = past[past.length - 1];
    setFuture(old => [structuredClone(scene), ...old]); setPast(old => old.slice(0, -1)); onChange(previous);
  };
  const redo = () => {
    if (!future.length) return;
    setPast(old => [...old, structuredClone(scene)]); onChange(future[0]); setFuture(old => old.slice(1));
  };
  const action = async (run: () => Promise<void>) => {
    setPending(true); onBusy(true); setError("");
    try { await run(); } catch (e) { setError((e as Error).message); } finally { setPending(false); onBusy(false); }
  };
  const upload = (file?: File) => {
    if (!file || !obj) return;
    const capturedId = obj.id, capturedType = obj.type;
    void action(async () => {
      const current = await save();
      const form = new FormData(); form.append("file", file);
      const saved = await request<Project>(`/projects/${project.id}/${capturedType === "video" ? "scene-videos" : "images"}?revision=${current.revision}`, { method: "POST", body: form });
      onProject(saved);
      const uploaded = (capturedType === "video" ? saved.videos : saved.images)?.at(-1);
      const savedScene = saved.scenes.find(s => s.id === scene.id)!;
      if (uploaded) {
        setPast(old => [...old, structuredClone(savedScene)]); setFuture([]);
        onChange({ ...savedScene, blocks: savedScene.blocks!.map(b => b.object?.id === capturedId ? { ...b, object: { ...b.object, asset_id: uploaded.id } } : b) });
      }
    });
  };
  const beginDrag = (event: PointerEvent<HTMLButtonElement>, mode: "block" | "object" | "top" | "bottom" | "media") => {
    if (locked || !canvas.current || event.button !== 0) return;
    event.preventDefault(); event.stopPropagation(); event.currentTarget.setPointerCapture(event.pointerId);
    const rect = canvas.current.getBoundingClientRect();
    drag.current = { scene: structuredClone(scene), x: event.clientX, y: event.clientY, mode, width: rect.width*940/1080, height: rect.height*1360/1920 };
  };
  const moveDrag = (event: PointerEvent<HTMLButtonElement>) => {
    const start = drag.current;
    if (!start) return;
    const original = start.scene.blocks!.find(b => b.id === block.id)!;
    const dx = event.clientX-start.x, dy = event.clientY-start.y;
    const clamp = (n: number) => Math.max(.1, Math.min(100, n));
    if (start.mode === "media" && media) {
      const object = original.object!;
      const size = mediaExtent(original, media);
      const excessX = start.width*original.width/100*object.width/100*(size.width/100-1);
      const excessY = start.height*original.height/100*object.height/100*(size.height/100-1);
      const crop_x = excessX > .01 ? Math.max(0, Math.min(100, (object.crop_x ?? 50)-dx/excessX*100)) : (object.crop_x ?? 50);
      const crop_y = excessY > .01 ? Math.max(0, Math.min(100, (object.crop_y ?? 50)-dy/excessY*100)) : (object.crop_y ?? 50);
      onChange({ ...start.scene, blocks: start.scene.blocks!.map(b => b.id === original.id ? { ...b, object: { ...object, crop_x, crop_y } } : b) });
    } else if (start.mode === "block") {
      const sized = resizeBlockEdge(start.scene.blocks!, original.id, "bottom", dy/start.height*100);
      onChange({ ...start.scene, blocks: sized.map(b => b.id === original.id ? { ...b, width: clamp(original.width+dx/start.width*100) } : b) });
    } else if (start.mode === "top" || start.mode === "bottom") {
      onChange({ ...start.scene, blocks: resizeBlockEdge(start.scene.blocks!, original.id, start.mode, dy/start.height*100) });
    } else {
      onChange({ ...start.scene, blocks: start.scene.blocks!.map(b => b.id === original.id ? { ...b, object: { ...b.object!,
        width: clamp(original.object!.width+dx/(start.width*original.width/100)*100),
        height: clamp(original.object!.height+dy/(start.height*original.height/100)*100),
      } } : b) });
    }
  };
  const endDrag = (cancelled = false) => {
    if (!drag.current) return;
    if (cancelled) onChange(drag.current.scene);
    else if (JSON.stringify(drag.current.scene) !== JSON.stringify(latest.current)) {
      const before = drag.current.scene;
      setPast(old => [...old.slice(-99), before]); setFuture([]);
    }
    drag.current = null;
  };
  const toolbar = <div className="block-actions">
    <button type="button" className="button secondary" disabled={locked || !past.length} onClick={undo}><Undo2 size={15} /> Desfazer</button>
    <button type="button" className="button secondary" disabled={locked || !future.length} onClick={redo}><Redo2 size={15} /> Refazer</button>
  </div>;
  let top = 0;
  return <section className="block-editor" aria-label="Editor de blocos">
    <div className="block-editor-heading"><div><h3>Composição da cena</h3><p>{blocks.length} blocos · um objeto por bloco</p></div>{toolbar}</div>
    <div className="block-workbench">
      <div className="block-canvas-column">
        <div className="block-stage">
          <aside className="block-commandbar" aria-label="Comandos do bloco selecionado">
            <h3>Bloco {blockIndex+1}</h3>
            <button type="button" className="button secondary" disabled={locked || blocks.length >= 100} onClick={() => { const next = appendBlock(blocks, block); changeBlocks(next); setSelected(next.at(-1)!.id); }}><Copy size={15} /> Duplicar</button>
            <button type="button" className="button secondary" aria-label="Mover bloco para cima" disabled={locked || blockIndex === 0} onClick={() => { const next = [...blocks]; [next[blockIndex-1], next[blockIndex]] = [next[blockIndex], next[blockIndex-1]]; changeBlocks(next); }}><ArrowUp size={16} /></button>
            <button type="button" className="button secondary" aria-label="Mover bloco para baixo" disabled={locked || blockIndex === blocks.length-1} onClick={() => { const next = [...blocks]; [next[blockIndex+1], next[blockIndex]] = [next[blockIndex], next[blockIndex+1]]; changeBlocks(next); }}><ArrowDown size={16} /></button>
            <button type="button" className="text-button destructive" disabled={locked || blocks.length === 1} onClick={() => changeBlocks(removeBlock(blocks, block.id))}><Trash2 size={15} /> Excluir bloco</button>
          </aside>
        <div ref={canvas} className="block-canvas" aria-label="Composição com áreas editáveis">
          <RenderedScene scene={scene} style={project.visual_style || null} accent={project.accent} projectId={project.id} />
          {player.frame && <img className="flow-frame" src={player.frame} alt="Quadro da animação no tempo selecionado" />}
          <div className="block-canvas-area">
            {blocks.map((b, index) => {
              const y = top; top += b.height;
              const left = (100-b.width)*{ left: 0, center: .5, right: 1 }[b.align];
              const style: CSSProperties = { top: `${y}%`, left: `${left}%`, width: `${b.width}%`, height: `${b.height}%` };
              return <div key={b.id} className={`block-outline ${b.id === block.id ? "selected" : ""} ${issues.some(issue => issue.object_id === b.object?.id) ? "invalid" : ""}`} style={style}>
                <button type="button" className="block-hit" aria-label={`Selecionar bloco ${index+1}`} aria-pressed={b.id === block.id} onClick={() => setSelected(b.id)}><span>{index+1}</span></button>
                {b.id === block.id && <>
                  {(["top", "bottom"] as const).map(edge => (edge === "top" ? index > 0 : index < blocks.length - 1) &&
                    <button key={edge} type="button" className={`resize-handle block-edge block-edge-${edge}`}
                      aria-label={`Mover borda ${edge === "top" ? "superior" : "inferior"} do bloco`} disabled={locked}
                      onPointerDown={e => beginDrag(e, edge)} onPointerMove={moveDrag} onPointerUp={() => endDrag()} onPointerCancel={() => endDrag(true)}
                      onKeyDown={e => { if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); changeBlocks(resizeBlockEdge(blocks, b.id, edge, e.key === "ArrowUp" ? -1 : 1)); } }} />)}
                  {b.object && <div className="object-outline" style={{ width: `${b.object.width}%`, height: `${b.object.height}%`,
                    left: `${(100-b.object.width)*{ left: 0, center: .5, right: 1 }[b.object.horizontal]}%`, top: `${(100-b.object.height)*{ top: 0, center: .5, bottom: 1 }[b.object.vertical]}%` }}>
                    {extent && mediaUrl && <button type="button" className="media-pan" aria-label="Reposicionar mídia no recorte" disabled={locked}
                      style={{ backgroundColor: mediaBackground, backgroundImage: mediaBackground ? `url(${JSON.stringify(mediaUrl)})` : undefined, backgroundSize: `${extent.width}% ${extent.height}%`, backgroundPosition: `${obj?.crop_x ?? 50}% ${obj?.crop_y ?? 50}%` }}
                      onPointerDown={e => beginDrag(e, "media")} onPointerMove={moveDrag} onPointerUp={() => endDrag()} onPointerCancel={() => endDrag(true)}
                      onKeyDown={e => {
                        if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); patchObject({ crop_x: Math.max(0, Math.min(100, (obj?.crop_x ?? 50)+(e.key === "ArrowLeft" ? 2 : -2))) }); }
                        if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); patchObject({ crop_y: Math.max(0, Math.min(100, (obj?.crop_y ?? 50)+(e.key === "ArrowUp" ? 2 : -2))) }); }
                      }} />}
                    <button type="button" className="resize-handle object-handle" aria-label="Redimensionar objeto" disabled={locked}
                      onPointerDown={e => beginDrag(e, "object")} onPointerMove={moveDrag} onPointerUp={() => endDrag()} onPointerCancel={() => endDrag(true)}
                      onKeyDown={e => { if (e.key.startsWith("Arrow")) { e.preventDefault(); patchObject(e.key === "ArrowUp" || e.key === "ArrowDown" ? { height: Math.max(.1, Math.min(100, obj!.height+(e.key === "ArrowUp" ? -1 : 1))) } : { width: Math.max(.1, Math.min(100, obj!.width+(e.key === "ArrowLeft" ? -1 : 1))) }); } }} />
                  </div>}
                  <button type="button" className="resize-handle block-handle" aria-label="Redimensionar bloco" disabled={locked}
                    onPointerDown={e => beginDrag(e, "block")} onPointerMove={moveDrag} onPointerUp={() => endDrag()} onPointerCancel={() => endDrag(true)}
                    onKeyDown={e => { if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); changeBlocks(resizeBlockEdge(blocks, b.id, "bottom", e.key === "ArrowUp" ? -1 : 1)); } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); patchBlock({ width: Math.max(.1, Math.min(100, b.width+(e.key === "ArrowLeft" ? -1 : 1))) }); } }} />
                </>}
              </div>;
            })}
          </div>
        </div>
        </div>
        {animated && <FlowControls player={player} clock={clock} disabled={locked} />}
        <p className="block-hint">Arraste a alça de cima ou de baixo para mover uma borda por vez. A alça do canto ajusta a largura e a borda inferior; a redonda ajusta o objeto. Marca e legendas ficam fora dessas áreas.</p>
        <ol className="block-list">{blocks.map((b, index) => <li key={b.id}>
          <button type="button" aria-pressed={b.id === block.id} onClick={() => setSelected(b.id)}><span>Bloco {index+1} · {b.object ? labels[b.object.type] : "Vazio"}</span><small>{threads.some(t => t.marked && !t.resolved && !t.archived && (t.target_id === b.object?.id || t.target_id === b.id)) ? "Conversa marcada · " : ""}{Number(b.height.toFixed(1))}%</small></button>
        </li>)}</ol>
        <button type="button" className="button secondary" disabled={locked || blocks.length >= 100} onClick={() => { const next = appendBlock(blocks); changeBlocks(next); setSelected(next.at(-1)!.id); }}><Plus size={15} /> Adicionar bloco</button>
      </div>
      <div className="block-controls">
        {error && <p className="notice danger" role="alert">{error}</p>}
        {inspectionError && <p className="notice danger" role="alert">Não foi possível conferir a composição: {inspectionError}</p>}
        <fieldset disabled={locked} className="block-object-picker">
          <label>Objeto do bloco<select value={obj?.type || ""} onChange={e => {
            const type = e.target.value as VisualObject["type"];
            patchBlock({ object: type ? { ...newObject(type, obj?.id), text: type === "flow" ? "" : obj?.text || "" } : null });
            // The agent builds every Fluxo animado; choosing it starts that request (ADR 0003).
            if (type === "flow") askAgent(); else setActiveTab("object");
          }}><option value="">Vazio</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </fieldset>
        <div className="block-tabs" role="tablist" aria-label="Propriedades do bloco">
          {[["block", "Bloco"], ["object", "Objeto"], ["agent", "Agente"]].map(([value, label]) =>
            <button key={value} type="button" role="tab" id={`${tabId}-${value}-tab`} aria-controls={`${tabId}-${value}-panel`}
              aria-selected={activeTab === value} tabIndex={activeTab === value ? 0 : -1} onClick={() => setActiveTab(value)}
              onKeyDown={event => {
                const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
                if (!keys.includes(event.key)) return;
                event.preventDefault();
                const tabs = ["block", "object", "agent"];
                const index = tabs.indexOf(value);
                const next = event.key === "Home" ? 0 : event.key === "End" ? 2 : (index+(event.key === "ArrowRight" ? 1 : 2))%3;
                setActiveTab(tabs[next]);
                document.getElementById(`${tabId}-${tabs[next]}-tab`)?.focus();
              }}>{label}</button>)}
        </div>
        <div className="block-panel" role="tabpanel" id={`${tabId}-block-panel`} aria-labelledby={`${tabId}-block-tab`} hidden={activeTab !== "block"} tabIndex={0}>
        <fieldset key={block.id} disabled={locked}>
          <legend>Dimensões do bloco</legend>
          <div className="block-field-grid"><NumberField label="Largura do bloco (%)" value={block.width} onChange={width => patchBlock({ width })} /><NumberField label="Altura do bloco (%)" value={block.height} onChange={height => changeBlocks(resizeBlock(blocks, block.id, height))} /></div>
          <label>Posição do bloco<select value={block.align} onChange={e => patchBlock({ align: e.target.value as SceneBlock["align"] })}>{Object.entries(horizontal).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </fieldset>
        </div>
        <div className="block-panel" role="tabpanel" id={`${tabId}-object-panel`} aria-labelledby={`${tabId}-object-tab`} hidden={activeTab !== "object"} tabIndex={0}>
        {obj && <fieldset key={obj.id} disabled={locked}>
          <legend>{labels[obj.type]}</legend>
          <div className="block-object-geometry">
            <NumberField label="Largura (%)" value={obj.width} onChange={width => patchObject({ width })} />
            <NumberField label="Altura (%)" value={obj.height} onChange={height => patchObject({ height })} />
            <label>Posição horizontal<select value={obj.horizontal} onChange={e => patchObject({ horizontal: e.target.value as VisualObject["horizontal"] })}>{Object.entries(horizontal).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>Posição vertical<select value={obj.vertical} onChange={e => patchObject({ vertical: e.target.value as VisualObject["vertical"] })}><option value="top">Topo</option><option value="center">Centro</option><option value="bottom">Base</option></select></label>
          </div>
          {obj.type === "flow" ? <div className="flow-summary">
            <p className="block-hint">O agente de direção monta o Fluxo animado a partir da narração: nós, posições, conexões, pulsos, gráficos e a sincronia com a fala. Revise e aceite a proposta na aba Agente.</p>
            {obj.flow ? <>
              <p><strong>{obj.flow.nodes.length} nós · {obj.flow.links.length} conexões · {obj.flow.steps.length} etapas</strong></p>
              <ol aria-label="Etapas do fluxo">{obj.flow.steps.map((step, index) => {
                const missing = warnings.some(w => w.object_id === obj.id && w.step === index);
                return <li key={index}>
                  {step.source ? `${nodeName(step.source)} → ${nodeName(step.target)}` : `Ativa ${nodeName(step.target)}`}
                  <small> · {step.source ? step.kind === "result" ? "resultado" : "pedido" : "ativação"}{step.anchor ? ` · na fala “${step.anchor}”` : " · tempo automático"}{missing ? " · âncora fora da narração" : ""}</small>
                </li>;
              })}</ol>
            </> : <p className="notice">Este Fluxo animado ainda não foi montado.</p>}
            <button type="button" className="button secondary" disabled={locked} onClick={() => askAgent(obj.flow ? "Refaça este Fluxo animado a partir da narração atual da cena, mantendo o mesmo objeto." : FLOW_REQUEST)}>
              <Sparkles size={15} /> {obj.flow ? "Pedir nova versão ao agente" : "Pedir ao agente para montar"}
            </button>
            <div className="block-field-grid"><NumberField label="Tamanho dos rótulos (px)" value={obj.font_size} min={8} max={400} onChange={font_size => patchObject({ font_size })} /></div>
          </div> : obj.type === "title" || obj.type === "paragraph" ? <>
            <label>Texto do {obj.type === "title" ? "título" : "parágrafo"}<textarea rows={obj.type === "title" ? 2 : 5} value={obj.text} maxLength={6000} onChange={e => patchObject({ text: e.target.value })} /></label>
            <GoogleFontPicker key={obj.id} value={obj.font} inherit disabled={locked} onChange={font => patchObject({ font })} />
            <div className="block-field-grid"><NumberField label="Tamanho da fonte (px)" value={obj.font_size} min={8} max={400} onChange={font_size => patchObject({ font_size })} />
              <label>Alinhamento do texto<select value={obj.align} onChange={e => patchObject({ align: e.target.value as VisualObject["align"] })}>{Object.entries(horizontal).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            </div>
            <label>Alinhamento vertical do texto<select value={obj.text_vertical ?? "top"} onChange={e => patchObject({ text_vertical: e.target.value as VisualObject["text_vertical"] })}>
              <option value="top">Topo</option><option value="center">Centro</option><option value="bottom">Rodapé</option>
            </select></label>
            <label className="block-color">Cor do texto<input type="color" value={obj.color || project.visual_style?.text_color || "#292e29"} onChange={e => patchObject({ color: e.target.value })} /></label>
            <button type="button" className="text-button" disabled={!obj.color} onClick={() => patchObject({ color: null })}>{obj.color ? "Herdar cor do projeto" : "Cor herdada do projeto"}</button>
          </> : <>
            <label>Arquivo da biblioteca<select value={obj.asset_id || ""} onChange={e => patchObject({ asset_id: e.target.value || null })}><option value="">Selecionar arquivo…</option>{(obj.type === "image" ? project.images : project.videos)?.map(asset => <option key={asset.id} value={asset.id}>{asset.name}</option>)}</select></label>
            <div className="block-media-import">
              <button type="button" className="button secondary" disabled={locked} onClick={() => mediaInput.current?.click()}>
                <Upload size={16} /> Importar {obj.type === "image" ? "imagem" : "vídeo"}
              </button>
              <small>{obj.type === "image" ? "PNG, JPG ou WebP · até 15 MB" : "MP4, MOV ou WebM · até 100 MB"}</small>
              <input ref={mediaInput} type="file" hidden aria-label={`Importar ${obj.type === "image" ? "imagem" : "vídeo"}`} disabled={locked}
                accept={obj.type === "image" ? "image/png,image/jpeg,image/webp" : "video/mp4,video/quicktime,video/webm"}
                onChange={e => { upload(e.target.files?.[0]); e.target.value = ""; }} />
            </div>
            <label>Enquadramento<select value={obj.fit} onChange={e => patchObject({ fit: e.target.value as VisualObject["fit"] })}><option value="contain">Mostrar inteiro</option><option value="cover">Preencher com corte</option></select></label>
            {obj.fit === "cover" && <label>Zoom no recorte · {Math.round((obj.zoom ?? 1)*100)}%
              <input type="range" aria-label="Zoom no recorte" min="1" max="5" step="0.05" value={obj.zoom ?? 1} onChange={e => patchObject({ zoom: e.currentTarget.valueAsNumber })} />
            </label>}
            {obj.fit === "cover" && <>
              <p className="block-hint">Arraste a mídia na composição para ajustar o recorte. Você também pode selecioná-la e usar as setas do teclado.</p>
              <button type="button" className="button secondary" disabled={(obj.crop_x ?? 50) === 50 && (obj.crop_y ?? 50) === 50}
                onClick={() => patchObject({ crop_x: 50, crop_y: 50 })}>Centralizar recorte</button>
            </>}
            {obj.type === "video" && <><p className="block-hint">Sem áudio original. Repete ou termina junto com a cena. MP4, MOV ou WebM · até 100 MB e 180 s.</p>{obj.asset_id && <video className="object-video" controls muted loop playsInline src={project.videos?.find(v => v.id === obj.asset_id)?.url} aria-label="Reproduzir vídeo do objeto" />}</>}
          </>}
          {issues.filter(issue => issue.object_id === obj.id).map(issue => <div key={issue.kind} className="notice danger" role="alert">{issue.message}
            {issue.kind === "overflow" && issue.font_size && <button type="button" className="text-button" onClick={() => patchObject({ font_size: issue.font_size! })}>Ajustar fonte ao espaço ({issue.font_size} px)</button>}
          </div>)}
          <button type="button" className="text-button destructive" onClick={() => patchBlock({ object: null })}><Trash2 size={15} /> Remover objeto</button>
        </fieldset>}
        {!obj && <p className="block-hint">Este bloco está vazio. Escolha um objeto no dropdown ou peça uma proposta ao agente.</p>}
        </div>
        {issues.some(issue => issue.object_id !== obj?.id) && <p className="notice">Há pendências em outros blocos. Revise cada objeto antes de exportar.</p>}
        <div className="block-panel" role="tabpanel" id={`${tabId}-agent-panel`} aria-labelledby={`${tabId}-agent-tab`} hidden={!conversation} tabIndex={0}>
          <SceneConversation project={project} scene={scene} blockId={block.id} objectId={obj?.id} disabled={locked} save={save} onBusy={onBusy} onThreads={setThreads} autoRequest={agentRequest} onAccepted={updated => {
            setPast(old => [...old, structuredClone(scene)]); setFuture([]); onProject(updated);
          }} />
        </div>
      </div>
    </div>
  </section>;
}
