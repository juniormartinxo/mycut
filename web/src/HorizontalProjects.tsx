import { useEffect, useState } from "react";
import { ArrowRight, LoaderCircle, MonitorPlay, Plus } from "lucide-react";
import { request } from "./api";
import { useChannels } from "./ChannelSettings";
import { HUMAN, clock } from "./EditFields";
import type { EditProject, EditSummary } from "./types";
import "./EditTimeline.css";

const formats = {
  "1920x1080": { width: 1920, height: 1080, fps: 30, label: "Horizontal 16:9 · 1920×1080 · 30 fps" },
  "1080x1920": { width: 1080, height: 1920, fps: 30, label: "Vertical 9:16 · 1080×1920 · 30 fps" },
};

/** Projects on the new editing document, beside the Shorts, whose editor stays as it is (Q42). */
export function HorizontalProjects({ onOpen }: { onOpen: (id: string) => void }) {
  const [projects, setProjects] = useState<EditSummary[] | null>(null);
  const { channels } = useChannels();
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [channelId, setChannelId] = useState("");
  const [format, setFormat] = useState<keyof typeof formats>("1920x1080");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const chosen = channelId || channels?.find((channel) => channel.default)?.id || "";
  useEffect(() => {
    let live = true;
    request<EditSummary[]>("/edit-projects")
      .then((items) => live && setProjects(items))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, []);
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const { label: _, ...size } = formats[format];
      const project = await request<EditProject>("/edit-projects", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim() || "Novo vídeo",
          channel_id: chosen || null,
          format: size,
          author: HUMAN,
        }),
      });
      onOpen(project.id);
    } catch (e) {
      setError((e as Error).message);
      setPending(false);
    }
  };
  return (
    <section className="horizontal-projects" aria-labelledby="horizontal-heading">
      <div className="horizontal-heading">
        <div>
          <h2 id="horizontal-heading">Vídeos horizontais</h2>
          <p>Cenas em sequência e faixas por conteúdo, com desfazer e histórico.</p>
        </div>
        {!creating && (
          <button type="button" className="button secondary" onClick={() => setCreating(true)}>
            <Plus size={17} />
            Novo vídeo horizontal
          </button>
        )}
      </div>
      {creating && (
        <form className="horizontal-form" aria-label="Novo vídeo horizontal" onSubmit={create}>
          <label>
            Título
            <input value={title} maxLength={120} placeholder="Novo vídeo" onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label>
            Canal
            <select value={chosen} onChange={(e) => setChannelId(e.target.value)}>
              {(channels ?? []).map((channel) => (
                <option key={channel.id} value={channel.id}>
                  {channel.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Formato
            <select value={format} onChange={(e) => setFormat(e.target.value as keyof typeof formats)}>
              {Object.entries(formats).map(([key, value]) => (
                <option key={key} value={key}>
                  {value.label}
                </option>
              ))}
            </select>
          </label>
          <div className="horizontal-form-actions">
            <button className="button primary" disabled={pending}>
              {pending ? <LoaderCircle className="spin" size={16} /> : <MonitorPlay size={16} />}
              Criar vídeo
            </button>
            <button type="button" className="text-button muted" onClick={() => setCreating(false)}>
              Cancelar
            </button>
          </div>
        </form>
      )}
      {error && (
        <p className="notice danger" role="alert">
          {error}
        </p>
      )}
      {projects && projects.length > 0 && (
        <ul className="horizontal-list" aria-label="Vídeos horizontais">
          {projects.map((project) => (
            <li key={project.id}>
              <button type="button" onClick={() => onOpen(project.id)}>
                <span>
                  <strong>{project.title}</strong>
                  <small>
                    {project.channel.name} · {project.format.width}×{project.format.height} · {project.scenes}{" "}
                    {project.scenes === 1 ? "cena" : "cenas"} · {clock(project.duration_ms)}
                  </small>
                </span>
                <ArrowRight size={18} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
