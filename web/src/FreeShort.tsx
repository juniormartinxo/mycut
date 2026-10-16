import { useState } from "react";
import { Check, Copy } from "lucide-react";
import type { Pause, Publication, VisualStyle } from "./types";
import "./FreeShort.css";

const seconds = (value: number) => `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;
const positions = { top: "no alto", middle: "no meio", bottom: "embaixo" } as const;

/** Palette, font and captions the director drew from the prompt's tone (ADR 0005). */
export function GeneratedStyle({ style, accent }: { style: VisualStyle; accent: string }) {
  const swatches = [
    ["Fundo", style.background],
    ["Texto", style.text_color],
    ["Destaque", accent],
  ] as const;
  const captions = style.captions;
  return (
    <section className="generated-style" aria-label="Estilo gerado">
      <strong>Estilo gerado pelo diretor</strong>
      <ul className="generated-swatches">
        {swatches.map(([name, color]) => color && (
          <li key={name}>
            <span className="generated-swatch" style={{ background: color }} aria-hidden="true" />
            {name} <code>{color.toUpperCase()}</code>
          </li>
        ))}
      </ul>
      <p>
        Fonte {style.google_font || "Roboto"}
        {captions && <> · Legenda com até {captions.words} palavras por vez, {positions[captions.position]}
          {captions.keywords.length > 0 && <>, destaque em {captions.keywords.join(", ")}</>}</>}
        {style.loop && <> · Loop: o último quadro volta ao primeiro</>}
      </p>
    </section>
  );
}

// Same word matching as the backend's anchors (flow.resolve_anchors): accents, case and punctuation do not count.
const normalized = (word: string) => word.normalize("NFKD").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
const words = (text: string) => text.split(/\s+/).map(normalized).filter(Boolean);

/** Whether each pause's passage is found in the narration, searched in order; a pause that is not has no silence. */
function applied(narration: string, pauses: Pause[]) {
  const spoken = words(narration);
  let cursor = 0;
  return pauses.map((pause) => {
    const needle = words(pause.after);
    if (!needle.length) return false;
    for (let i = cursor; i + needle.length <= spoken.length; i++) {
      if (needle.every((word, k) => spoken[i + k] === word)) {
        cursor = i + 1;
        return true;
      }
    }
    return false;
  });
}

export function ScenePauses({ narration, pauses }: { narration: string; pauses?: Pause[] }) {
  if (!pauses?.length) return null;
  const found = applied(narration, pauses);
  return (
    <ul className="scene-pauses">
      {pauses.map((pause, i) => (
        <li key={i} className={found[i] ? undefined : "not-applied"}>
          Pausa de {seconds(pause.seconds)} depois de “{pause.after}”
          {!found[i] && " · não aplicada: o trecho não está na narração"}
        </li>
      ))}
    </ul>
  );
}

export function CopyButton({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button type="button" className="button secondary" aria-label={label}
      onClick={() => void navigator.clipboard.writeText(text).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })}>
      {copied ? <Check size={15} /> : <Copy size={15} />}
      {copied ? "Copiado" : "Copiar"}
    </button>
  );
}

/** The free Short's publication package: title options, hashtags and the pinned comment. */
export function PublicationPackage({ publication, title, onTitle, disabled }: {
  publication: Publication; title: string; onTitle: (title: string) => void; disabled: boolean;
}) {
  const hashtags = publication.hashtags.join(" ");
  return (
    <section className="publication-package" aria-label="Pacote de publicação">
      <h3>Pacote de publicação</h3>
      <div>
        <strong id="title-options">Opções de título</strong>
        <ol aria-labelledby="title-options">
          {publication.titles.map((option, i) => (
            <li key={i}>
              <span>{option}</span>
              {option === title ? <small>Em uso</small> : (
                <button type="button" className="button secondary" disabled={disabled}
                  aria-label={`Usar o título “${option}”`} onClick={() => onTitle(option)}>Usar este título</button>
              )}
            </li>
          ))}
        </ol>
      </div>
      {hashtags && (
        <div className="publication-copy">
          <strong>Hashtags</strong>
          <p>{hashtags}</p>
          <CopyButton label="Copiar hashtags" text={hashtags} />
        </div>
      )}
      {publication.pinned_comment && (
        <div className="publication-copy">
          <strong>Comentário fixado</strong>
          <pre>{publication.pinned_comment}</pre>
          <CopyButton label="Copiar comentário fixado" text={publication.pinned_comment} />
        </div>
      )}
    </section>
  );
}
