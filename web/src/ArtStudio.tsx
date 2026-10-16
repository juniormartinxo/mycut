import { useState } from "react";
import { ImagePlus, Paperclip, RefreshCw, X } from "lucide-react";
import { AgentSteps } from "./Automation";
import { money } from "./ProjectCosts";
import type { ArtRequest, Project } from "./types";
import "./ArtStudio.css";

const MAX_EXAMPLES = 4;
const states: Record<ArtRequest["state"], string> = {
  pending: "Aguardando geração",
  generated: "Gerada",
  failed: "Não gerada",
};
const kinds = { character: "Personagem", setting: "Cenário" } as const;

const estimateText = (count: number, perImage: number | null | undefined) =>
  typeof perImage === "number" ? ` · estimativa ${money(count * perImage)}` : "";

/** The Arte's work on a Short livre (ADR 0005): the visual bible, the bases to review and guide, and the
 * remaining images, generated only when the author asks. */
export function ArtStudio({
  project,
  locked,
  perImage,
  onGenerate,
  onRedo,
}: {
  project: Project;
  locked: boolean;
  perImage: number | null | undefined;
  onGenerate: () => void;
  onRedo: (key: string, text: string, files: File[]) => void;
}) {
  const art = project.art;
  if (!art || art.mode === "none")
    return (
      <p className="art-empty">
        Este Short livre foi criado sem imagens geradas pela Arte. As cenas usam
        os anexos, textos e animações.
      </p>
    );
  if (!art.requests.length)
    return (
      <p className="art-empty">
        A bíblia visual e os pedidos de imagem aparecem aqui depois que o
        diretor compõe as cenas.
      </p>
    );
  const missing = art.requests.filter((item) => item.state !== "generated");
  // Only the voice and the video are left of a production that stopped for the bases.
  const resumes = art.then === "pipeline";
  const bases = art.requests.filter((item) => item.base);
  const others = art.requests.filter((item) => !item.base);
  const titles = Object.fromEntries(
    [
      ...art.requests.map((item) => [item.key, item.title]),
      ...(project.images || []).map((item) => [item.id, item.name]),
    ] as [string, string][],
  );
  const latest = project.jobs.find((job) => job.kind === "art");
  return (
    <div className="art-studio">
      {art.bible && (
        <section className="art-bible" aria-label="Bíblia visual">
          <h3>Bíblia visual</h3>
          {art.bible.tone && <p>{art.bible.tone}</p>}
          {art.bible.sheets.length > 0 && (
            <dl>
              {art.bible.sheets.map((sheet, i) => (
                <div key={i}>
                  <dt>
                    {kinds[sheet.kind]} · {sheet.name}
                  </dt>
                  <dd>{sheet.description}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      )}
      <div className="art-actions">
        <button
          type="button"
          className="button primary"
          disabled={locked || (!missing.length && !resumes)}
          onClick={onGenerate}
        >
          <ImagePlus size={17} />
          {missing.length
            ? `Gerar ${missing.length === 1 ? "a imagem que falta" : `as ${missing.length} imagens que faltam`}${resumes ? " e continuar a produção" : ""}`
            : resumes
              ? "Continuar a produção"
              : "Todas as imagens foram geradas"}
        </button>
        <p className="connection-help">
          {missing.length > 0 &&
            `${missing.length} ${missing.length === 1 ? "imagem" : "imagens"}${estimateText(missing.length, perImage)}. `}
          Confira as imagens-base antes: as demais são geradas com elas
          anexadas, para manter o rosto e o cenário.
          {art.estimate &&
            ` Última estimativa: ${art.estimate.images} ${art.estimate.images === 1 ? "imagem" : "imagens"}${art.estimate.usd === null ? ", sem preço" : `, ${money(art.estimate.usd)}`}. O valor registrado está em Custos.`}
        </p>
      </div>
      {latest && <AgentSteps job={latest} />}
      <ArtGroup
        title="Imagens-base"
        detail="Fichas de personagem e cenários vazios, referência das outras imagens."
        items={bases}
        {...{ project, titles, locked, perImage, onRedo }}
      />
      <ArtGroup
        title="Imagens das cenas"
        detail="Cada uma entra no plano que o diretor escolheu."
        items={others}
        {...{ project, titles, locked, perImage, onRedo }}
      />
    </div>
  );
}

function ArtGroup({
  title,
  detail,
  items,
  ...props
}: {
  title: string;
  detail: string;
  items: ArtRequest[];
  project: Project;
  titles: Record<string, string>;
  locked: boolean;
  perImage: number | null | undefined;
  onRedo: (key: string, text: string, files: File[]) => void;
}) {
  if (!items.length) return null;
  return (
    <section className="art-group" aria-label={title}>
      <header>
        <h3>{title}</h3>
        <p>{detail}</p>
      </header>
      <ul>
        {items.map((item) => (
          <ArtCard key={item.key} item={item} {...props} />
        ))}
      </ul>
    </section>
  );
}

function ArtCard({
  item,
  project,
  titles,
  locked,
  perImage,
  onRedo,
}: {
  item: ArtRequest;
  project: Project;
  titles: Record<string, string>;
  locked: boolean;
  perImage: number | null | undefined;
  onRedo: (key: string, text: string, files: File[]) => void;
}) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const image = project.images?.find((entry) => entry.id === item.image_id);
  // Without its bases an image would lose the face or the place it has to keep.
  const waiting = (project.art?.requests || []).filter(
    (base) => base.base && item.references.includes(base.key) && base.state !== "generated",
  );
  const blocked = locked || waiting.length > 0;
  return (
    <li className={`art-card ${item.state}`}>
      <div className="art-frame">
        {image ? (
          <img src={image.url} alt={item.title} />
        ) : (
          <span>{states[item.state]}</span>
        )}
      </div>
      <div className="art-body">
        <strong>{item.title}</strong>
        <small>
          {states[item.state]} · {item.aspect}
          {item.references.length > 0 &&
            ` · com ${item.references.map((key) => titles[key] || key).join(" e ")}`}
        </small>
        {item.state === "failed" && item.error && (
          <p className="art-warning">{item.error}</p>
        )}
        {waiting.length > 0 && (
          <p className="art-warning">
            Gere antes a imagem-base “{waiting[0].title}”: esta imagem a usa
            como referência.
          </p>
        )}
        {item.outdated && (
          <p className="art-warning">
            Feita com a versão anterior de uma imagem-base. Refaça para manter a
            consistência.
          </p>
        )}
        <details>
          <summary>Prompt</summary>
          <pre>{item.prompt}</pre>
        </details>
        {item.messages.length > 0 && (
          <ol className="art-messages" aria-label={`Orientações para ${item.title}`}>
            {item.messages.map((message, i) => (
              <li key={i}>
                {message.text}
                {message.attachments > 0 &&
                  ` · ${message.attachments} ${message.attachments === 1 ? "exemplo" : "exemplos"}`}
              </li>
            ))}
          </ol>
        )}
        <form
          className="art-guidance"
          onSubmit={(e) => {
            e.preventDefault();
            onRedo(item.key, text, files);
            setText("");
            setFiles([]);
          }}
        >
          <label>
            Orientação para a Arte
            <textarea
              rows={2}
              maxLength={2000}
              value={text}
              disabled={blocked}
              placeholder="Ex.: cabelo mais curto, cicatriz bem visível, luz de emergência mais forte."
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <div className="art-guidance-actions">
            <label className="button secondary">
              <Paperclip size={15} />
              Anexar exemplo
              <input
                type="file"
                multiple
                accept="image/png,image/jpeg,image/webp"
                disabled={blocked}
                onChange={(e) => {
                  const chosen = [...(e.target.files || [])];
                  e.target.value = "";
                  setFiles([...files, ...chosen].slice(0, MAX_EXAMPLES));
                }}
              />
            </label>
            <button
              className="button secondary"
              disabled={blocked || !text.trim()}
            >
              <RefreshCw size={15} />
              {item.state === "generated" ? "Refazer" : "Gerar"} com esta
              orientação{estimateText(1, perImage)}
            </button>
          </div>
          {files.length > 0 && (
            <ul className="art-examples" aria-label={`Exemplos para ${item.title}`}>
              {files.map((file, i) => (
                <li key={`${file.name}-${i}`}>
                  {file.name}
                  <button
                    type="button"
                    aria-label={`Remover ${file.name}`}
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                  >
                    <X size={13} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </form>
      </div>
    </li>
  );
}
