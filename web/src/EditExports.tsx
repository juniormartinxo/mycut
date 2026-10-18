import { useCallback, useEffect, useState } from "react";
import { Download, Film, LoaderCircle, Trash2 } from "lucide-react";
import { request } from "./api";
import { HUMAN, bytes, clock } from "./EditFields";
import type { EditExport, EditProject } from "./types";

const states: Record<EditExport["state"], string> = {
  queued: "Na fila",
  running: "Exportando",
  done: "Pronta",
  failed: "Falhou",
};

/**
 * Exports of frozen revisions (Q47): editing goes on during an export, and every file stays until the author
 * removes it.
 */
export function EditExports({ project, onError }: { project: EditProject; onError: (message: string) => void }) {
  const [exports, setExports] = useState<EditExport[]>([]);
  const [pending, setPending] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const path = `/edit-projects/${project.id}/exports`;
  const refresh = useCallback(
    async () => setExports((await request<{ exports: EditExport[] }>(path)).exports),
    [path],
  );
  useEffect(() => {
    refresh().catch((e: Error) => onError(e.message));
  }, [refresh, onError]);
  const active = exports.some((e) => e.state === "queued" || e.state === "running");
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => void refresh().catch(() => undefined), 1500);
    return () => window.clearInterval(timer);
  }, [active, refresh]);

  const run = async (action: () => Promise<unknown>) => {
    setPending(true);
    try {
      await action();
      await refresh();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="edit-panel" aria-labelledby="exports-heading">
      <h2 id="exports-heading">
        <Film size={18} />
        Exportações
      </h2>
      <p className="edit-help">
        MP4 H.264/AAC 48 kHz em {project.format.width}×{project.format.height}, {project.format.fps} fps. A revisão
        exportada fica congelada: você pode continuar editando.
      </p>
      <button
        type="button"
        className="button primary"
        disabled={pending}
        onClick={() =>
          void run(() => request(path, { method: "POST", body: JSON.stringify({ revision: project.revision, author: HUMAN }) }))
        }
      >
        <Film size={16} />
        Exportar revisão {project.revision}
      </button>
      {exports.length > 0 && (
        <ul className="edit-list" aria-label="Exportações do projeto">
          {exports.map((item) => (
            <li key={item.id}>
              <span>
                <strong>{item.name}</strong>
                <small>
                  Revisão {item.revision} · {clock(item.duration_ms)} · {states[item.state]}
                  {item.state === "running" && ` · ${item.progress}% · ${item.message}`}
                  {item.state === "failed" && ` · ${item.message}`}
                  {item.size !== null && ` · ${bytes(item.size)}`}
                </small>
              </span>
              <span className="edit-list-actions">
                {(item.state === "queued" || item.state === "running") && <LoaderCircle size={16} className="spin" />}
                {item.state === "done" && (
                  <a className="text-button" href={`/api${path}/${item.id}/file`} download={item.name}>
                    <Download size={15} />
                    Baixar
                  </a>
                )}
                {removing === item.id ? (
                  <>
                    <button
                      type="button"
                      className="text-button destructive"
                      disabled={pending}
                      onClick={() =>
                        void run(() =>
                          request(`${path}/${item.id}`, { method: "DELETE", body: JSON.stringify({ author: HUMAN }) }),
                        ).then(() => setRemoving(null))
                      }
                    >
                      Confirmar remoção
                    </button>
                    <button type="button" className="text-button muted" onClick={() => setRemoving(null)}>
                      Manter
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="text-button muted"
                    disabled={pending}
                    aria-label={`Remover ${item.name}`}
                    onClick={() => setRemoving(item.id)}
                  >
                    <Trash2 size={15} />
                    Remover
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
