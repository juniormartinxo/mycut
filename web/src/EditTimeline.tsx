import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  CircleAlert,
  HardDrive,
  History,
  LoaderCircle,
  Plus,
  Redo2,
  Scissors,
  Trash2,
  Undo2,
  Upload,
} from "lucide-react";
import { request } from "./api";
import type {
  EditAuthor,
  EditHistoryEntry,
  EditItem,
  EditProject,
  EditStorage,
  EditTrack,
} from "./types";
import "./EditTimeline.css";

/** Every change made on this screen is an operation of the author, recorded with this authorship. */
export const HUMAN: EditAuthor = { kind: "human", name: "Autor" };
// Pixels per millisecond of the timeline.
const SCALE = 0.08;
const NEW_ITEM_MS = 2000;
const number = (value: number, digits = 2) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: digits });
export const seconds = (ms: number) => `${number(ms / 1000)} s`;
export const clock = (ms: number) =>
  `${Math.floor(ms / 60000)}:${(Math.floor(ms / 1000) % 60).toString().padStart(2, "0")}`;
export const bytes = (size: number) =>
  size < 1024
    ? `${size} B`
    : size < 1024 ** 2
      ? `${number(size / 1024, 1)} KB`
      : `${number(size / 1024 ** 2, 1)} MB`;
const fieldNames: Record<string, string> = {
  track_id: "faixa",
  scene_id: "cena",
  start_ms: "início",
  duration_ms: "duração",
  source_start_ms: "recorte",
  layer: "ordem visual",
  geometry: "posição e tamanho",
  text: "texto",
  resource: "mídia",
};
const styleNames: Record<string, string> = {
  opacity: "Opacidade",
  volume: "Volume",
  color: "Cor",
  font_family: "Fonte",
  font_size: "Tamanho do texto",
  align: "Alinhamento",
  fit: "Encaixe",
};
const choices: Record<string, Record<string, string>> = {
  fit: { cover: "Preencher", contain: "Caber inteiro" },
  align: { left: "Esquerda", center: "Centro", right: "Direita" },
};
const placement = { inside: "Dentro do quadro", partial: "Parte fora do quadro", outside: "Fora do quadro" };

type Operation = Record<string, unknown>;
type Drag = {
  item: string;
  mode: "move" | "start" | "end";
  origin: number;
  moved: boolean;
  start_ms: number;
  duration_ms: number;
  source_start_ms: number;
};

const newId = () => crypto.randomUUID().replaceAll("-", "");

function itemLabel(project: EditProject, item: EditItem, track: EditTrack) {
  if (item.text) return item.text;
  const resource = project.resources.find((r) => r.hash === item.resource);
  return resource?.name ?? track.name;
}

/** Commits a typed value when the field loses focus or on Enter, as one operation. */
function NumberField({
  label,
  value,
  step,
  min,
  onCommit,
  disabled,
}: {
  label: string;
  value: number;
  step: number;
  min?: number;
  onCommit: (value: number) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  const commit = () => {
    const parsed = Number(text.replace(",", "."));
    if (!Number.isFinite(parsed) || parsed === value) return setText(String(value));
    onCommit(parsed);
  };
  return (
    <label>
      {label}
      <input
        type="number"
        inputMode="decimal"
        step={step}
        min={min}
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && commit()}
      />
    </label>
  );
}

export function EditTimeline({ id, onBack }: { id: string; onBack: () => void }) {
  const [project, setProject] = useState<EditProject | null>(null);
  const [storage, setStorage] = useState<EditStorage | null>(null);
  const [history, setHistory] = useState<EditHistoryEntry[]>([]);
  const [selected, setSelected] = useState<{ kind: "item" | "scene"; id: string } | null>(null);
  const [cursor, setCursor] = useState(0);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirming, setConfirming] = useState(false);
  const upload = useRef<HTMLInputElement>(null);

  const refreshSide = useCallback(async () => {
    const [space, entries] = await Promise.all([
      request<EditStorage>(`/edit-projects/${id}/storage`),
      request<{ entries: EditHistoryEntry[] }>(`/edit-projects/${id}/history`),
    ]);
    setStorage(space);
    setHistory(entries.entries);
  }, [id]);
  const reload = useCallback(async () => {
    setProject(await request<EditProject>(`/edit-projects/${id}`));
    await refreshSide();
  }, [id, refreshSide]);
  useEffect(() => {
    reload().catch((e: Error) => setError(e.message));
  }, [reload]);

  const commit = useCallback(
    async (path: string, body: Record<string, unknown> | FormData) => {
      setPending(true);
      setError("");
      setNotice("");
      try {
        const next = await request<EditProject>(`/edit-projects/${id}${path}`, {
          method: "POST",
          body: body instanceof FormData ? body : JSON.stringify(body),
        });
        setProject(next);
        // Storage and history follow in the background; the timeline is editable again right away.
        refreshSide().catch((e: Error) => setError(e.message));
        return next;
      } catch (e) {
        setError((e as Error).message);
        // A refused operation changed nothing; show the document as the server has it.
        await reload().catch(() => undefined);
        return null;
      } finally {
        setPending(false);
      }
    },
    [id, refreshSide, reload],
  );
  const send = (operations: Operation[], label?: string) =>
    project &&
    commit("/operations", { revision: project.revision, author: HUMAN, operations, ...(label ? { label } : {}) });
  const step = useCallback(
    (action: "undo" | "redo") =>
      project && commit(`/${action}`, { revision: project.revision, author: HUMAN }),
    [project, commit],
  );

  useEffect(() => {
    const keys = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || pending) return;
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey && project?.undo) {
        event.preventDefault();
        void step("undo");
      } else if ((key === "y" || (key === "z" && event.shiftKey)) && project?.redo) {
        event.preventDefault();
        void step("redo");
      }
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, [project, pending, step]);

  if (!project)
    return (
      <div className="loading">
        {error ? <span role="alert">{error}</span> : <LoaderCircle className="spin" />}
        {!error && "Abrindo a timeline…"}
      </div>
    );

  const frame = 1000 / project.format.fps;
  const snap = (ms: number) => Math.max(0, Math.round(Math.round(ms / frame) * frame));
  const width = (Math.max(project.duration_ms, cursor) + 5000) * SCALE;
  const sceneAt = (ms: number) =>
    project.scenes.find((s) => s.start_ms <= ms && ms < s.start_ms + s.duration_ms)?.id ?? null;
  const item = selected?.kind === "item" ? project.items.find((i) => i.id === selected.id) : undefined;
  const scene = selected?.kind === "scene" ? project.scenes.find((s) => s.id === selected.id) : undefined;
  const trackOf = (value: EditItem) => project.tracks.find((t) => t.id === value.track_id)!;

  const insert = async (track: EditTrack, extra: Operation = {}) => {
    const itemId = newId();
    const next = await send([
      {
        op: "add_item",
        item: {
          id: itemId,
          track_id: track.id,
          scene_id: sceneAt(cursor),
          start_ms: snap(cursor),
          duration_ms: NEW_ITEM_MS,
          ...(track.kind === "text" ? { text: "Novo texto" } : {}),
          ...extra,
        },
      },
    ]);
    if (next) setSelected({ kind: "item", id: itemId });
  };
  const change = (value: EditItem, changes: Operation) =>
    send([{ op: "update_item", item_id: value.id, changes }]);

  const shown = (value: EditItem) => {
    if (!drag || drag.item !== value.id) return value;
    return { ...value, start_ms: drag.start_ms, duration_ms: drag.duration_ms, source_start_ms: drag.source_start_ms };
  };
  const startDrag = (event: React.PointerEvent, value: EditItem, mode: Drag["mode"]) => {
    if (pending) return;
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    setDrag({ item: value.id, mode, origin: event.clientX, moved: false, start_ms: value.start_ms,
      duration_ms: value.duration_ms, source_start_ms: value.source_start_ms });
  };
  const moveDrag = (event: React.PointerEvent, value: EditItem) => {
    if (!drag || drag.item !== value.id) return;
    const delta = (event.clientX - drag.origin) / SCALE;
    const moved = drag.moved || Math.abs(event.clientX - drag.origin) > 3;
    if (drag.mode === "move")
      return setDrag({ ...drag, moved, start_ms: snap(value.start_ms + delta) });
    if (drag.mode === "end")
      return setDrag({ ...drag, moved, duration_ms: Math.max(Math.round(frame), snap(value.duration_ms + delta)) });
    // The left edge trims the media: it cannot go before the media starts nor past the item's end.
    const earliest = value.start_ms - value.source_start_ms;
    const start = Math.min(Math.max(snap(value.start_ms + delta), Math.max(0, earliest)),
      value.start_ms + value.duration_ms - Math.round(frame));
    const shift = start - value.start_ms;
    setDrag({ ...drag, moved, start_ms: start, duration_ms: value.duration_ms - shift,
      source_start_ms: value.source_start_ms + shift });
  };
  const endDrag = (value: EditItem) => {
    if (!drag || drag.item !== value.id) return;
    setDrag(null);
    setSelected({ kind: "item", id: value.id });
    if (!drag.moved) return;
    const changes: Operation = {};
    for (const field of ["start_ms", "duration_ms", "source_start_ms"] as const)
      if (drag[field] !== value[field]) changes[field] = drag[field];
    if (Object.keys(changes).length)
      void send([{ op: "update_item", item_id: value.id, changes }],
        drag.mode === "move" ? "Mover item" : "Redimensionar item");
  };

  const importFile = async (file: File | undefined) => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("revision", String(project.revision));
    form.append("author_kind", HUMAN.kind);
    form.append("author_name", HUMAN.name);
    const next = await commit("/resources", form);
    if (next) setNotice(`${file.name} importado.`);
    if (upload.current) upload.current.value = "";
  };
  const cleanHistory = async () => {
    setPending(true);
    setError("");
    try {
      const result = await request<{ freed_bytes: number; project: EditProject; storage: EditStorage }>(
        `/edit-projects/${id}/cleanup`,
        { method: "POST", body: JSON.stringify({ kind: "history", revision: project.revision, author: HUMAN }) },
      );
      setProject(result.project);
      await refreshSide();
      setNotice(`Histórico apagado. ${bytes(result.freed_bytes)} liberados.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
      setConfirming(false);
    }
  };
  const used = new Set(project.items.map((i) => i.resource));
  const resourceTrack = (mediaType: string) =>
    project.tracks.find((t) => t.kind === (mediaType.startsWith("audio/") ? "music" : "visual"));
  const ticks = Array.from({ length: Math.ceil(width / SCALE / 1000) + 1 }, (_, s) => s);

  return (
    <section className="edit-page">
      <div className="editor-heading">
        <div className="editor-title">
          <button className="back-button" aria-label="Voltar às produções" onClick={onBack}>
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1>{project.title}</h1>
            <p>
              <span>
                {project.aspect} · {project.format.width}×{project.format.height} · {project.format.fps} fps
              </span>
              <span>Canal {project.channel.name}</span>
              <span>
                Marca {project.inherited.brand.value}
                {project.inherited.brand.inherited && " (do canal)"}
              </span>
              <span>
                Voz {project.inherited.voice.value?.voice_name || "das Conexões"}
                {project.inherited.voice.inherited && " (do canal)"}
              </span>
            </p>
          </div>
        </div>
        <div className="editor-actions">
          <button
            className="button secondary"
            disabled={pending || !project.undo}
            title={project.undo ? `Desfazer: ${project.undo.label}` : undefined}
            onClick={() => void step("undo")}
          >
            <Undo2 size={16} />
            Desfazer
          </button>
          <button
            className="button secondary"
            disabled={pending || !project.redo}
            title={project.redo ? `Refazer: ${project.redo.label}` : undefined}
            onClick={() => void step("redo")}
          >
            <Redo2 size={16} />
            Refazer
          </button>
        </div>
      </div>
      {error && (
        <p className="notice danger" role="alert">
          <CircleAlert size={16} />
          {error}
        </p>
      )}
      <p className="edit-status" role="status">
        {notice || `Revisão ${project.revision} · ${clock(project.duration_ms)} · cursor em ${seconds(cursor)}`}
      </p>

      <div className="edit-toolbar">
        <button
          className="button secondary"
          disabled={pending}
          onClick={async () => {
            const sceneId = newId();
            const next = await send([
              { op: "add_scene", scene: { id: sceneId, title: `Cena ${project.scenes.length + 1}`, duration_ms: 5000 } },
            ]);
            if (next) setSelected({ kind: "scene", id: sceneId });
          }}
        >
          <Plus size={16} />
          Adicionar cena
        </button>
        <button className="button secondary" disabled={pending} onClick={() => upload.current?.click()}>
          <Upload size={16} />
          Importar recurso
        </button>
        <input
          ref={upload}
          className="edit-file-input"
          type="file"
          aria-label="Arquivo do recurso"
          accept="image/*,video/*,audio/*"
          onChange={(e) => void importFile(e.target.files?.[0])}
        />
      </div>

      <div className="timeline" aria-label="Timeline">
        <div className="timeline-row timeline-ruler">
          <div className="timeline-head">Tempo</div>
          <div
            className="timeline-lane"
            style={{ width }}
            role="slider"
            tabIndex={0}
            aria-label="Cursor da timeline"
            aria-valuemin={0}
            aria-valuemax={project.duration_ms}
            aria-valuenow={cursor}
            aria-valuetext={seconds(cursor)}
            onPointerDown={(e) => {
              const box = e.currentTarget.getBoundingClientRect();
              setCursor(snap((e.clientX - box.left) / SCALE));
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") setCursor(snap(cursor + frame));
              if (e.key === "ArrowLeft") setCursor(snap(cursor - frame));
            }}
          >
            {ticks.map((s) => (
              <span key={s} className="timeline-tick" style={{ left: s * 1000 * SCALE }}>
                {s}s
              </span>
            ))}
            <span className="timeline-cursor" style={{ left: cursor * SCALE }} />
          </div>
        </div>
        <div className="timeline-row">
          <div className="timeline-head">Cenas</div>
          <div className="timeline-lane" style={{ width }}>
            {project.scenes.map((s, index) => (
              <button
                key={s.id}
                type="button"
                className={`timeline-scene ${selected?.id === s.id ? "selected" : ""}`}
                style={{ left: s.start_ms * SCALE, width: s.duration_ms * SCALE }}
                aria-label={`Cena ${index + 1}: ${s.title || "sem título"}, ${seconds(s.duration_ms)}`}
                onClick={() => setSelected({ kind: "scene", id: s.id })}
              >
                <span>{index + 1}</span>
                {s.title}
              </button>
            ))}
            <span className="timeline-cursor" style={{ left: cursor * SCALE }} />
          </div>
        </div>
        {project.tracks.map((track) => (
          <div className={`timeline-row track-${track.kind}`} key={track.id}>
            <div className="timeline-head">
              <span>{track.name}</span>
              <button
                type="button"
                className="icon-button"
                disabled={pending}
                aria-label={`Inserir item em ${track.name}`}
                title="Inserir no cursor"
                onClick={() => void insert(track)}
              >
                <Plus size={15} />
              </button>
            </div>
            <div className="timeline-lane" style={{ width }} role="list" aria-label={`Faixa ${track.name}`}>
              {project.items
                .filter((i) => i.track_id === track.id)
                .map((value) => {
                  const view = shown(value);
                  const label = itemLabel(project, value, track);
                  return (
                    <div
                      key={value.id}
                      role="listitem"
                      className={`timeline-item ${item?.id === value.id ? "selected" : ""}`}
                      style={{ left: view.start_ms * SCALE, width: Math.max(view.duration_ms * SCALE, 6) }}
                    >
                      <span
                        className="timeline-handle start"
                        aria-hidden="true"
                        onPointerDown={(e) => startDrag(e, value, "start")}
                        onPointerMove={(e) => moveDrag(e, value)}
                        onPointerUp={() => endDrag(value)}
                      />
                      <button
                        type="button"
                        aria-label={`${label}, ${seconds(view.start_ms)} a ${seconds(view.start_ms + view.duration_ms)}`}
                        aria-pressed={item?.id === value.id}
                        onPointerDown={(e) => startDrag(e, value, "move")}
                        onPointerMove={(e) => moveDrag(e, value)}
                        onPointerUp={() => endDrag(value)}
                        onClick={() => setSelected({ kind: "item", id: value.id })}
                      >
                        {label}
                      </button>
                      <span
                        className="timeline-handle end"
                        aria-hidden="true"
                        onPointerDown={(e) => startDrag(e, value, "end")}
                        onPointerMove={(e) => moveDrag(e, value)}
                        onPointerUp={() => endDrag(value)}
                      />
                    </div>
                  );
                })}
              <span className="timeline-cursor" style={{ left: cursor * SCALE }} />
            </div>
          </div>
        ))}
      </div>

      <div className="edit-panels">
        <section className="edit-panel" aria-labelledby="inspector-heading">
          <h2 id="inspector-heading">{item ? "Item" : scene ? "Cena" : "Seleção"}</h2>
          {item ? (
            <ItemInspector
              key={`${item.id}:${project.revision}`}
              project={project}
              item={item}
              track={trackOf(item)}
              cursor={cursor}
              pending={pending}
              onChange={(changes) => change(item, changes)}
              onStyle={(values) => send([{ op: "set_style", item_id: item.id, values }])}
              onSplit={() => send([{ op: "split_item", item_id: item.id, at_ms: snap(cursor), new_id: newId() }])}
              onRemove={async () => (await send([{ op: "remove_item", item_id: item.id }])) && setSelected(null)}
            />
          ) : scene ? (
            <div className="inspector" key={`${scene.id}:${project.revision}`}>
              <label>
                Título da cena
                <input
                  defaultValue={scene.title}
                  maxLength={100}
                  onBlur={(e) =>
                    e.target.value !== scene.title &&
                    void send([{ op: "update_scene", scene_id: scene.id, title: e.target.value }])
                  }
                />
              </label>
              <NumberField
                label="Duração da cena (s)"
                value={scene.duration_ms / 1000}
                step={frame / 1000}
                min={frame / 1000}
                disabled={pending}
                onCommit={(value) =>
                  void send([{ op: "update_scene", scene_id: scene.id, duration_ms: Math.max(1, snap(value * 1000)) }])
                }
              />
              <button
                type="button"
                className="text-button destructive"
                disabled={pending || project.scenes.length === 1}
                onClick={async () => (await send([{ op: "remove_scene", scene_id: scene.id }])) && setSelected(null)}
              >
                <Trash2 size={15} />
                Remover cena
              </button>
            </div>
          ) : (
            <p className="edit-help">
              Clique numa cena ou num item para ajustá-lo. Arraste um item para movê-lo e as bordas para
              mudar a duração ou cortar o início. O cursor marca onde inserir e onde cortar.
            </p>
          )}
        </section>

        <section className="edit-panel" aria-labelledby="resources-heading">
          <h2 id="resources-heading">Recursos</h2>
          {project.resources.length === 0 ? (
            <p className="edit-help">Importe imagens, vídeos e áudios. Um arquivo usado em vários projetos é guardado uma vez.</p>
          ) : (
            <ul className="edit-list" aria-label="Recursos do projeto">
              {project.resources.map((resource) => {
                const track = resourceTrack(resource.media_type);
                return (
                  <li key={resource.hash}>
                    <span>
                      <strong>{resource.name}</strong>
                      <small>
                        {bytes(resource.size)} · {used.has(resource.hash) ? "na timeline" : "fora da timeline"}
                      </small>
                    </span>
                    <span className="edit-list-actions">
                      {track && (
                        <button
                          type="button"
                          className="text-button"
                          disabled={pending}
                          onClick={() => void insert(track, { resource: resource.hash })}
                        >
                          Inserir no cursor
                        </button>
                      )}
                      {!used.has(resource.hash) && (
                        <button
                          type="button"
                          className="text-button muted"
                          disabled={pending}
                          onClick={() => void send([{ op: "remove_resource", hash: resource.hash }])}
                        >
                          Tirar do projeto
                        </button>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {storage && (
          <section className="edit-panel" aria-labelledby="storage-heading">
            <h2 id="storage-heading">
              <HardDrive size={18} />
              Espaço do projeto
            </h2>
            <p className="edit-space">
              <strong>{bytes(storage.referenced_bytes)}</strong> referenciados
              {storage.shared_bytes > 0 && `, dos quais ${bytes(storage.shared_bytes)} também em outros projetos`}
            </p>
            {storage.resources.length > 0 && (
              <ul className="edit-list" aria-label="Conteúdo referenciado">
                {storage.resources.map((resource) => (
                  <li key={resource.hash}>
                    <span>
                      <strong>{resource.name ?? "Recurso removido"}</strong>
                      <small>
                        {bytes(resource.size)} ·{" "}
                        {resource.in_document ? "no projeto" : "só no histórico"}
                        {resource.other_projects > 0 &&
                          ` · também em ${resource.other_projects} ${resource.other_projects === 1 ? "projeto" : "projetos"}`}
                      </small>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {storage.cleanups.map((cleanup) => (
              <div className="edit-cleanup" key={cleanup.kind}>
                <p>
                  {cleanup.label}: {cleanup.entries} {cleanup.entries === 1 ? "registro" : "registros"}.{" "}
                  <strong>Libera {bytes(cleanup.frees_bytes)}</strong>
                  {cleanup.frees_bytes === 0 &&
                    storage.referenced_bytes > 0 &&
                    " — o conteúdo ainda é usado pelo projeto ou por outro projeto"}
                  .
                  Desfazer deixa de alcançar as alterações anteriores.
                </p>
                {confirming ? (
                  <span className="edit-list-actions">
                    <button type="button" className="button primary" disabled={pending} onClick={() => void cleanHistory()}>
                      Confirmar e apagar
                    </button>
                    <button type="button" className="text-button muted" onClick={() => setConfirming(false)}>
                      Manter histórico
                    </button>
                  </span>
                ) : (
                  <button type="button" className="button secondary" disabled={pending} onClick={() => setConfirming(true)}>
                    <Trash2 size={15} />
                    Apagar histórico
                  </button>
                )}
              </div>
            ))}
          </section>
        )}

        <section className="edit-panel" aria-labelledby="history-heading">
          <h2 id="history-heading">
            <History size={18} />
            Histórico
          </h2>
          <ol className="edit-history" aria-label="Histórico de edição">
            {[...history].reverse().slice(0, 12).map((entry) => (
              <li key={entry.id} className={entry.state === "undone" ? "undone" : ""}>
                <span>
                  {entry.kind === "undo" ? "Desfeito: " : entry.kind === "redo" ? "Refeito: " : ""}
                  {entry.label}
                </span>
                <small>
                  {entry.author.name} ({entry.author.kind === "human" ? "autor" : "agente"}) · revisão {entry.revision}
                </small>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </section>
  );
}

function ItemInspector({
  project,
  item,
  track,
  cursor,
  pending,
  onChange,
  onStyle,
  onSplit,
  onRemove,
}: {
  project: EditProject;
  item: EditItem;
  track: EditTrack;
  cursor: number;
  pending: boolean;
  onChange: (changes: Operation) => void;
  onStyle: (values: Record<string, string | number | null>) => void;
  onSplit: () => void;
  onRemove: () => void;
}) {
  const frame = 1000 / project.format.fps;
  const ms = (value: number) => Math.max(0, Math.round(Math.round((value * 1000) / frame) * frame));
  const inside = item.start_ms < cursor && cursor < item.start_ms + item.duration_ms;
  const audio = ["narration", "music", "effects"].includes(track.kind);
  const media = project.resources.filter((r) =>
    audio ? r.media_type.startsWith("audio/") : !r.media_type.startsWith("audio/"),
  );
  return (
    <div className="inspector">
      <p className="edit-help">
        {track.name} · última alteração por {item.last_author.name} (
        {item.last_author.kind === "human" ? "autor" : "agente"})
        {item.human.length > 0 &&
          ` · escolhas do autor protegidas: ${item.human.map((f) => fieldNames[f] ?? f.replace("style.", "estilo ")).join(", ")}`}
      </p>
      <div className="inspector-grid">
        <NumberField label="Início (s)" value={item.start_ms / 1000} step={frame / 1000} min={0} disabled={pending}
          onCommit={(v) => onChange({ start_ms: ms(v) })} />
        <NumberField label="Duração (s)" value={item.duration_ms / 1000} step={frame / 1000} min={frame / 1000} disabled={pending}
          onCommit={(v) => onChange({ duration_ms: Math.max(1, ms(v)) })} />
        <NumberField label="Recorte inicial (s)" value={item.source_start_ms / 1000} step={frame / 1000} min={0} disabled={pending}
          onCommit={(v) => onChange({ source_start_ms: ms(v) })} />
        {!audio && (
          <NumberField label="Ordem visual" value={item.layer} step={1} disabled={pending}
            onCommit={(v) => onChange({ layer: Math.round(v) })} />
        )}
      </div>
      {item.geometry && (
        <>
          <div className="inspector-grid">
            {(["x", "y", "width", "height"] as const).map((key) => (
              <NumberField
                key={key}
                label={{ x: "X (px)", y: "Y (px)", width: "Largura (px)", height: "Altura (px)" }[key]}
                value={item.geometry![key]}
                step={1}
                disabled={pending}
                onCommit={(v) => onChange({ geometry: { ...item.geometry!, [key]: v } })}
              />
            ))}
          </div>
          {item.in_frame && <p className="edit-help">{placement[item.in_frame]}</p>}
        </>
      )}
      {track.kind === "text" && (
        <label>
          Texto
          <textarea
            defaultValue={item.text ?? ""}
            maxLength={2000}
            onBlur={(e) => e.target.value !== (item.text ?? "") && onChange({ text: e.target.value })}
          />
        </label>
      )}
      {track.kind !== "text" && (
        <label>
          Mídia
          <select
            value={item.resource ?? ""}
            disabled={pending}
            onChange={(e) => onChange({ resource: e.target.value || null })}
          >
            <option value="">Sem mídia</option>
            {media.map((r) => (
              <option key={r.hash} value={r.hash}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <fieldset className="inspector-style">
        <legend>Estilo</legend>
        {Object.entries(item.resolved_style).map(([name, style]) => (
          <div key={name} className="inspector-style-row">
            {choices[name] ? (
              <label>
                {styleNames[name]}
                <select value={String(style.value)} disabled={pending} onChange={(e) => onStyle({ [name]: e.target.value })}>
                  {Object.entries(choices[name]).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            ) : name === "color" ? (
              <label>
                {styleNames[name]}
                <input type="color" value={String(style.value)} disabled={pending}
                  onChange={(e) => onStyle({ [name]: e.target.value })} />
              </label>
            ) : typeof style.value === "number" ? (
              <NumberField label={styleNames[name]} value={style.value} step={name === "font_size" ? 1 : 0.05}
                disabled={pending} onCommit={(v) => onStyle({ [name]: v })} />
            ) : (
              <label>
                {styleNames[name]}
                <input defaultValue={String(style.value)} disabled={pending}
                  onBlur={(e) => e.target.value !== style.value && onStyle({ [name]: e.target.value })} />
              </label>
            )}
            {style.inherited ? (
              <small>Herdado do template</small>
            ) : (
              <button type="button" className="text-button" disabled={pending}
                aria-label={`Voltar a herdar ${styleNames[name]}`} onClick={() => onStyle({ [name]: null })}>
                Voltar a herdar
              </button>
            )}
          </div>
        ))}
      </fieldset>
      <div className="edit-list-actions">
        <button type="button" className="button secondary" disabled={pending || !inside} onClick={onSplit}
          title={inside ? undefined : "Coloque o cursor dentro do item"}>
          <Scissors size={15} />
          Cortar no cursor
        </button>
        <button type="button" className="text-button destructive" disabled={pending} onClick={onRemove}>
          <Trash2 size={15} />
          Remover item
        </button>
      </div>
    </div>
  );
}
