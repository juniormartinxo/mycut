import { useEffect, useRef, useState } from "react";
import { LoaderCircle, Upload } from "lucide-react";
import { request } from "./api";
import type { EndingClip } from "./types";
import "./EndingStudio.css";

export function EndingStudio({
  value,
  disabled,
  onChange,
}: {
  value: string | null;
  disabled: boolean;
  onChange: (id: string | null) => void;
}) {
  const [clips, setClips] = useState<EndingClip[]>([]);
  const [choice, setChoice] = useState(value || "");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<{ message: string; source: "load" | "upload" } | null>(null);
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const selected = clips.find((clip) => clip.id === (value || choice)) || (!value ? clips[0] : undefined);
  const locked = disabled || uploading;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    request<EndingClip[]>("/endings")
      .then((items) => { if (active) setClips(items); })
      .catch((reason: Error) => { if (active) setError({ message: reason.message, source: "load" }); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 100 * 1024 * 1024) {
      setError({ message: "O vídeo ultrapassa 100 MB. Exporte um arquivo menor.", source: "upload" });
      return;
    }
    setUploading(true);
    setError(null);
    setNotice("");
    try {
      const body = new FormData();
      body.append("file", file);
      const clip = await request<EndingClip>("/endings", { method: "POST", body });
      setClips((items) => [clip, ...items.filter((item) => item.id !== clip.id)]);
      setChoice(clip.id);
      if (value) onChange(clip.id);
      setNotice("Vídeo importado. Ele também fica disponível nas outras produções.");
    } catch (reason) {
      setError({ message: (reason as Error).message, source: "upload" });
    } finally {
      setUploading(false);
    }
  };

  return (
    <section className="ending-studio" aria-label="Encerramento do Short">
      <div className="section-heading">
        <div>
          <h2>Seu convite no final do Short</h2>
          <p>Escolha se esta produção termina com um vídeo de encerramento.</p>
        </div>
      </div>
      <label className="ending-toggle">
        <input
          type="checkbox"
          checked={Boolean(value)}
          disabled={locked || loading || (!value && !selected)}
          onChange={(event) => {
            if (selected) setChoice(selected.id);
            onChange(event.target.checked ? selected?.id || null : null);
          }}
          aria-describedby="ending-effect"
        />
        <span>Incluir no final deste Short</span>
      </label>
      <p id="ending-effect" className="ending-effect">
        {value && selected
          ? `Acrescenta ${selected.duration.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} segundos após a última cena${selected.has_audio ? ", com o áudio do vídeo" : ", sem áudio"}.`
          : value
            ? "O vídeo selecionado não está disponível. Escolha outro ou desative a inclusão."
            : "Este Short termina na última cena. Ative a opção para acrescentar o vídeo abaixo."}
      </p>
      {error && (
        <div className="notice danger" role="alert">
          <span>{error.message}</span>
          <button
            className="text-button"
            disabled={locked || loading}
            onClick={() => error.source === "upload" ? input.current?.click() : setReload((n) => n + 1)}
          >
            {error.source === "upload" ? "Escolher outro vídeo" : "Tentar novamente"}
          </button>
        </div>
      )}
      {notice && <p className="ending-feedback" role="status">{notice}</p>}
      {loading ? <p role="status">Carregando vídeos de encerramento…</p> : (
        <div className="ending-content">
          <div className="ending-controls">
            {clips.length > 0 ? (
              <label>
                Vídeo de encerramento
                <select
                  value={selected?.id || ""}
                  disabled={locked}
                  onChange={(event) => {
                    setChoice(event.target.value);
                    if (value) onChange(event.target.value);
                    setNotice("");
                  }}
                >
                  {!selected && <option value="" disabled>Selecione um vídeo</option>}
                  {clips.map((clip) => <option key={clip.id} value={clip.id}>{clip.name}</option>)}
                </select>
              </label>
            ) : <p className="ending-empty">Importe seu primeiro encerramento para assistir e escolher em quais Shorts ele aparece.</p>}
            <input
              ref={input}
              className="file-input"
              type="file"
              accept=".mp4,.mov,.webm"
              aria-label="Importar vídeo de encerramento"
              disabled={locked}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                void upload(file);
              }}
            />
            <button className="button secondary" disabled={locked} onClick={() => input.current?.click()}>
              {uploading ? <LoaderCircle size={17} className="spin" /> : <Upload size={17} />}
              {uploading ? "Preparando vídeo…" : clips.length ? "Importar outro vídeo" : "Importar vídeo"}
            </button>
            {uploading && <p role="status">Aguarde enquanto o vídeo é preparado para o Short.</p>}
            <p className="ending-help">MP4, MOV ou WebM. Até 100 MB e 60 segundos. A imagem inteira é preservada no formato vertical.</p>
            <p className="ending-help">Salve a escolha ou clique em <strong>Renderizar cenas atuais</strong> para assistir ao Short com a alteração.</p>
          </div>
          {selected && <figure className="ending-player">
            <video key={selected.id} src={selected.url} poster={selected.poster_url} controls playsInline preload="metadata" aria-label="Prévia do encerramento" />
            <figcaption>Prévia somente do encerramento</figcaption>
          </figure>}
        </div>
      )}
    </section>
  );
}
