import { useEffect, useRef, useState } from "react";
import { Check, ImagePlus, RotateCcw } from "lucide-react";
import { request } from "./api";
import type { Scene, ShortFormat, VisualStyle } from "./types";
import "./FormatPicker.css";

export const initialStyle: VisualStyle = {
  format_id: "editorial",
  channel_name: "MYCUT",
  font: null,
  background: null,
  text_color: null,
  media_mode: "animations",
  image_source: "both",
};
const sample: Scene = {
  title: "Da ideia à ação",
  layout: "flow",
  narration: "",
  items: [
    "Você define a tarefa",
    "O agente executa",
    "Você revisa o resultado",
  ],
};

export function RenderedScene({
  scene,
  style,
  accent,
  projectId,
  label = "Composição da cena",
}: {
  scene: Scene;
  style: VisualStyle;
  accent: string;
  projectId?: string;
  label?: string;
}) {
  const [source, setSource] = useState("");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const currentUrl = useRef("");
  const body = JSON.stringify({
    scene,
    visual_style: style,
    accent,
    project_id: projectId,
  });
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    const timer = setTimeout(async () => {
      try {
        const response = await fetch("/api/scene-preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("preview");
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        const next = URL.createObjectURL(blob);
        URL.revokeObjectURL(currentUrl.current);
        currentUrl.current = next;
        setSource(next);
      } catch {
        if (!controller.signal.aborted) setError(true);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [body, retry]);
  useEffect(() => () => URL.revokeObjectURL(currentUrl.current), []);
  return (
    <div className="rendered-scene" aria-busy={loading}>
      {source && <img src={source} alt={label} />}
      {loading && (
        <span className="preview-state" role="status">
          Atualizando prévia…
        </span>
      )}
      {error && (
        <div className="preview-state" role="alert">
          Prévia indisponível.
          <button type="button" onClick={() => setRetry((v) => v + 1)}>
            Tentar novamente
          </button>
        </div>
      )}
    </div>
  );
}

function ColorControl({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <label className="format-color">
      {label}
      <span>
        <input
          type="color"
          aria-label={label}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
        />
        <code>{value.toUpperCase()}</code>
      </span>
    </label>
  );
}

export function FormatPicker({
  value,
  accent,
  onChange,
  disabled = false,
}: {
  value: VisualStyle | null;
  accent: string;
  onChange: (style: VisualStyle, accent: string) => void;
  disabled?: boolean;
}) {
  const [catalog, setCatalog] = useState<{
    formats: ShortFormat[];
    fonts: Record<string, string>;
  } | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const style = value || { ...initialStyle, font: "sans" as const };
  useEffect(() => {
    let live = true;
    setError("");
    request<{ formats: ShortFormat[]; fonts: Record<string, string> }>(
      "/short-formats",
    )
      .then((data) => {
        if (live) setCatalog(data);
      })
      .catch(() => {
        if (live) setError("Não foi possível carregar os formatos.");
      });
    return () => {
      live = false;
    };
  }, [retry]);
  const selected = catalog?.formats.find((item) => item.id === style.format_id);
  const apply = (format: ShortFormat) =>
    onChange(
      {
        ...style,
        format_id: format.id,
        font: format.font,
        background: format.background,
        text_color: format.text_color,
      },
      format.accent,
    );
  const change = (delta: Partial<VisualStyle>) =>
    onChange({ ...style, ...delta }, accent);
  return (
    <section className="format-section" aria-label="Formato e aparência">
      <fieldset className="format-picker" disabled={disabled}>
        <legend>Formato do Short</legend>
        <p>
          Escolha um ponto de partida. Depois, ajuste as cores e a fonte do seu
          jeito.
        </p>
        {error ? (
          <div className="notice danger" role="alert">
            {error}{" "}
            <button
              type="button"
              className="text-button"
              onClick={() => setRetry((n) => n + 1)}
            >
              Tentar novamente
            </button>
          </div>
        ) : !catalog ? (
          <p role="status">Carregando formatos…</p>
        ) : (
          <div className="format-gallery">
            {catalog.formats.map((format) => (
              <label
                key={format.id}
                className={`format-option ${style.format_id === format.id ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="short-format"
                  value={format.id}
                  checked={style.format_id === format.id}
                  onChange={() => apply(format)}
                  aria-label={format.name}
                />
                <div className="format-thumbnail">
                  {style.format_id === format.id ? (
                    <RenderedScene
                      scene={sample}
                      style={style}
                      accent={accent}
                      label={`Exemplo do formato ${format.name}`}
                    />
                  ) : (
                    <img
                      src={format.preview_url}
                      alt={`Exemplo do formato ${format.name}`}
                      loading="lazy"
                    />
                  )}
                </div>
                <span className="format-name">
                  {format.name}
                  {style.format_id === format.id && (
                    <Check size={14} aria-hidden="true" />
                  )}
                </span>
                <span className="format-purpose">{format.use_case}</span>
              </label>
            ))}
          </div>
        )}
      </fieldset>
      {selected && (
        <>
          <p className="format-description">
            {selected.description} As prévias mostram o mesmo exemplo nos quatro
            formatos.
          </p>
          <details className="format-customize" open>
            <summary>Personalizar aparência</summary>
            <fieldset disabled={disabled}>
              <label className="format-channel">
                Nome do canal no vídeo
                <input
                  type="text"
                  value={style.channel_name ?? "MYCUT"}
                  onChange={(event) => change({ channel_name: event.target.value })}
                  maxLength={40}
                  placeholder="Nome ou @ do canal"
                  aria-describedby="channel-name-hint"
                />
                <small id="channel-name-hint">
                  Aparece no topo das cenas e nas capas geradas. Deixe vazio para ocultar.
                </small>
              </label>
              <label>
                Fonte do vídeo
                <select
                  value={style.font || selected.font}
                  onChange={(e) =>
                    change({ font: e.target.value as VisualStyle["font"] })
                  }
                >
                  {Object.entries(catalog!.fonts).map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="format-colors">
                <ColorControl
                  label="Cor de fundo"
                  value={style.background || selected.background}
                  onChange={(background) => change({ background })}
                  disabled={disabled}
                />
                <ColorControl
                  label="Cor do texto"
                  value={style.text_color || selected.text_color}
                  onChange={(text_color) => change({ text_color })}
                  disabled={disabled}
                />
                <ColorControl
                  label="Cor de destaque"
                  value={accent}
                  onChange={(color) => onChange(style, color)}
                  disabled={disabled}
                />
              </div>
              <button
                type="button"
                className="text-button"
                onClick={() => apply(selected)}
              >
                <RotateCcw size={14} />
                Restaurar aparência do formato
              </button>
            </fieldset>
          </details>
        </>
      )}
      <fieldset className="format-media" disabled={disabled}>
        <label>
          Conteúdo visual
          <select
            value={style.media_mode}
            onChange={(e) =>
              change({
                media_mode: e.target.value as VisualStyle["media_mode"],
              })
            }
          >
            <option value="animations">Só animações e diagramas</option>
            <option value="mixed">Animações com imagens</option>
          </select>
        </label>
        {style.media_mode === "mixed" && (
          <label>
            Origem das imagens
            <select
              value={style.image_source}
              onChange={(e) =>
                change({
                  image_source: e.target.value as VisualStyle["image_source"],
                })
              }
            >
              <option value="both">Fontes da pauta e minha biblioteca</option>
              <option value="sources">Buscar nas fontes da pauta</option>
              <option value="library">Usar minha biblioteca</option>
            </select>
          </label>
        )}
        <p>
          <ImagePlus size={15} aria-hidden="true" />
          {style.media_mode === "mixed"
            ? "Os agentes escolhem imagens pertinentes para algumas cenas. Você pode trocar a imagem ou voltar à animação em cada cena."
            : "Todas as cenas usam animações, textos e fluxos. Nenhuma imagem externa será buscada."}
        </p>
        {style.media_mode === "mixed" && style.image_source === "library" && (
          <p>
            Importe suas imagens na aba Cenas antes de pedir aos agentes para
            recriar os visuais.
          </p>
        )}
      </fieldset>
    </section>
  );
}
