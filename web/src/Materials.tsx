import { CircleAlert, ListVideo, Upload } from "lucide-react";
import { CopyButton } from "./FreeShort";
import { shotsOf } from "./sceneLayout";
import type { Background, Broll, Project } from "./types";
import "./Materials.css";

type Place = Broll["places"][number];
const CLIP_TYPES = "video/mp4,video/quicktime,video/webm,image/png,image/jpeg,image/webp,image/gif";
const placeName = (place: Place) => `cena ${place.scene}, plano ${place.shot}`;
const toolAndLength = (item: Broll) => `${item.tool} · ${String(item.seconds).replace(".", ",")} s`;

/** A plano background still waiting for its B-roll's clip: not a video and not the image imported for it (ADR 0005). */
export function waitingClip(background: Background | null | undefined, brolls: Broll[] = []) {
  if (!background?.broll || background.kind === "video") return false;
  const clip = brolls.find((item) => item.key === background.broll)?.clip;
  return !clip || background.asset_id !== clip.id;
}

const backgroundAt = (project: Project, place: Place) => {
  const scene = project.scenes[place.scene - 1];
  return scene?.blocks ? shotsOf(scene)[place.shot - 1]?.background : undefined;
};

/** The B-rolls some plano still waits for, numbered as in the lista de materiais. */
function missing(project: Project) {
  return (project.brolls || []).map((item, i) => ({ item, number: i + 1, places: item.places.filter((p) => p.waiting) }))
    .filter((entry) => entry.places.length);
}

function ClipState({ waiting }: { waiting: boolean }) {
  return <span className={`badge ${waiting ? "working" : "ready"}`}><span />{waiting ? "Aguardando clipe" : "Clipe importado"}</span>;
}

/** What the author still has to bring: which clips, in which plano, with which prompt and tool. Shown in the
 * production and in the scenes; nothing when every clip is in. */
export function MissingClips({ project, onOpen }: { project: Project; onOpen?: () => void }) {
  const entries = missing(project);
  if (!entries.length) return null;
  return (
    <section className="notice materials-missing" aria-label="Clipes de B-roll que faltam">
      <CircleAlert size={18} aria-hidden="true" />
      <div>
        <strong>{entries.length === 1 ? "Falta 1 clipe de B-roll" : `Faltam ${entries.length} clipes de B-roll`}</strong>
        <ul>
          {entries.map(({ item, number, places }) => (
            <li key={item.key}>
              B-roll {number} · {item.title} · {places.map(placeName).join(" e ")} · {toolAndLength(item)}
              <details><summary>Prompt</summary><pre>{item.prompt}</pre></details>
            </li>
          ))}
        </ul>
        <p>
          Faça cada clipe com o prompt e importe-o. Até lá, o plano mostra a imagem provisória com movimento de
          câmera, e a exportação continua liberada.
        </p>
        {onOpen && <button type="button" className="button secondary" onClick={onOpen}>
          <ListVideo size={16} /> Abrir a lista de materiais
        </button>}
      </div>
    </section>
  );
}

/** The lista de materiais: each B-roll with its prompt, tool, references and duration, and its clip to import. */
export function MaterialsList({ project, locked, onImport }: {
  project: Project; locked: boolean; onImport: (key: string, file: File) => void;
}) {
  const brolls = project.brolls || [];
  if (!brolls.length)
    return <p className="materials-empty">Este Short livre não pede B-rolls: as cenas usam imagens, textos e animações.</p>;
  const images = Object.fromEntries((project.images || []).map((image) => [image.id, image]));
  // A reference is a base of the Arte (by its key) or one of the production's images.
  const bases = Object.fromEntries((project.art?.requests || []).filter((r) => r.image_id).map((r) => [r.key, r.image_id!]));
  return (
    <ol className="materials-list" aria-label="Lista de materiais">
      {brolls.map((item, i) => {
        const shown = item.places.map((place) => backgroundAt(project, place)).find((background) => background?.asset_id);
        const clip = item.clip && (item.clip.kind === "video" ? project.videos : project.images)?.find((entry) => entry.id === item.clip!.id);
        const frame = shown?.kind === "video" ? project.videos?.find((entry) => entry.id === shown.asset_id)?.poster_url
          : shown?.asset_id ? images[shown.asset_id]?.url : undefined;
        const waiting = item.places.some((place) => place.waiting);
        const references = item.references.map((reference) => images[bases[reference] || reference]).filter(Boolean);
        return (
          <li key={item.key} className="materials-card">
            <div className="materials-frame">
              {frame ? <img src={frame} alt={`${waiting ? "Imagem provisória" : "Clipe"} do B-roll ${i + 1}`} />
                : <span>Sem imagem provisória</span>}
            </div>
            <div className="materials-body">
              <header>
                <strong>B-roll {i + 1} · {item.title}</strong>
                {item.places.length ? <ClipState waiting={waiting} /> : <span className="badge"><span />Fora dos planos</span>}
              </header>
              <small>{toolAndLength(item)}</small>
              <p>Entra em: {item.places.length ? item.places.map(placeName).join("; ") : "nenhum plano"}</p>
              {references.length ? (
                <div className="materials-references">
                  <span>Referências:</span>
                  {references.map((image) => (
                    <a key={image.id} href={image.url} download title={`Baixar ${image.name}`}>
                      <img src={image.url} alt={image.name} />{image.name}
                    </a>
                  ))}
                </div>
              ) : <p>Referências: nenhuma</p>}
              <pre>{item.prompt}</pre>
              <div className="materials-actions">
                <CopyButton label={`Copiar o prompt do B-roll ${i + 1}`} text={item.prompt} />
                <ClipInput number={i + 1} broll={item.key} waiting={waiting} disabled={locked || !item.places.length} onImport={onImport} />
              </div>
              {clip && <p>Clipe importado: {clip.name}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ClipInput({ number, broll, waiting, disabled, onImport }: {
  number: number; broll: string; waiting: boolean; disabled: boolean; onImport: (key: string, file: File) => void;
}) {
  return (
    <label className={`button ${waiting ? "primary" : "secondary"} materials-import`}>
      <Upload size={15} />
      {waiting ? "Importar clipe" : "Trocar clipe"}
      <input type="file" accept={CLIP_TYPES} disabled={disabled} aria-label={`Importar clipe do B-roll ${number}`}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onImport(broll, file);
        }} />
    </label>
  );
}

/** The editor's view of the B-roll a plano shows: what the clip is, where to make it and the import. */
export function BrollPlano({ project, background, disabled, onImport }: {
  project: Project; background: Background; disabled: boolean; onImport: (key: string, file: File) => void;
}) {
  const brolls = project.brolls || [];
  const index = brolls.findIndex((item) => item.key === background.broll);
  if (index < 0) return null;
  const item = brolls[index];
  const waiting = waitingClip(background, brolls);
  const clip = item.clip && (item.clip.kind === "video" ? project.videos : project.images)?.find((entry) => entry.id === item.clip!.id);
  return (
    <section role="group" aria-label="B-roll deste plano" className={`broll-plano ${waiting ? "waiting" : ""}`}>
      <strong>B-roll {index + 1} · {item.title}</strong>
      <ClipState waiting={waiting} />
      <small>{toolAndLength(item)}</small>
      {waiting ? <p className="block-hint">Enquanto o clipe não chega, o plano mostra a imagem provisória com movimento de
        câmera. A exportação continua liberada.</p> : clip && <p className="block-hint">Clipe importado: {clip.name}</p>}
      <details><summary>Prompt</summary><pre>{item.prompt}</pre></details>
      <ClipInput number={index + 1} broll={item.key} waiting={waiting} disabled={disabled} onImport={onImport} />
    </section>
  );
}
