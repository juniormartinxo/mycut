import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  CircleAlert,
  ImagePlus,
  LoaderCircle,
  Paperclip,
  Send,
  Upload,
  X,
} from "lucide-react";
import { request } from "./api";
import type {
  AgentChoice,
  CoverMessage,
  Integrations,
  Project,
} from "./types";
import "./CoverStudio.css";

const providers: AgentChoice["provider"][] = ["grok", "codex", "claude"];
const names: Record<AgentChoice["provider"], string> = {
  codex: "Codex",
  claude: "Claude Code",
  grok: "Grok",
};
const pending = (m: CoverMessage) => ["queued", "running"].includes(m.state);
const MAX_ATTACHMENTS = 4;

export function CoverStudio({
  project,
  locked,
  settings,
  onConnect,
  onUpload,
  onChoose,
}: {
  project: Project;
  locked: boolean;
  settings: Integrations | null;
  onConnect: () => void;
  onUpload: (file?: File) => void;
  onChoose: (message: string, image: string) => void;
}) {
  const [messages, setMessages] = useState<CoverMessage[] | null>(null);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [choice, setChoice] = useState<AgentChoice | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const coverInput = useRef<HTMLInputElement>(null);
  const attachInput = useRef<HTMLInputElement>(null);
  const end = useRef<HTMLLIElement>(null);
  const load = useCallback(async () => {
    const value = await request<CoverMessage[]>(
      `/projects/${project.id}/cover/messages`,
    );
    setMessages(value);
    return value;
  }, [project.id]);
  const waiting = !!messages?.some(pending);
  useEffect(() => {
    let live = true;
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const value = await load();
        if (live && value.some(pending))
          timer = window.setTimeout(refresh, 2000);
      } catch (e) {
        if (live) setError((e as Error).message);
      }
    };
    void refresh();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [load, waiting]);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages?.length, waiting]);
  // The last agent used in this production is the default for the next message.
  const last = messages?.at(-1);
  const selected: AgentChoice = choice ??
    (last && { provider: last.provider, model: last.model }) ?? {
      provider: "grok",
      model: "",
    };
  const catalog = settings?.agent_models[selected.provider];
  const runner = settings?.runner;
  const unavailable = !runner?.online
    ? "O executor de agentes está desconectado. Rode bash scripts/agents.sh no WSL."
    : runner.protocol < 4
      ? "Reinicie bash scripts/agents.sh no WSL para gerar imagens com os agentes."
      : !runner.providers[selected.provider]
        ? `${names[selected.provider]} não foi encontrado no executor.`
        : "";
  const send = async () => {
    if (!text.trim() || sending || waiting || unavailable) return;
    setSending(true);
    setError("");
    try {
      const data = new FormData();
      data.append("text", text.trim());
      data.append("provider", selected.provider);
      data.append("model", selected.model);
      files.forEach((file) => data.append("files", file));
      const message = await request<CoverMessage>(
        `/projects/${project.id}/cover/messages`,
        { method: "POST", body: data },
      );
      setMessages((current) => [...(current ?? []), message]);
      setText("");
      setFiles([]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };
  const cancel = async (id: string) => {
    setError("");
    try {
      await request(`/jobs/${id}/cancel`, { method: "POST" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Uma capa que faz parar o dedo.</h2>
          <p>
            Converse com um agente para criar imagens e escolha uma delas como
            capa do Short.
          </p>
        </div>
      </div>
      <div className="cover-studio">
        <aside className="cover-current" aria-label="Capa atual">
          {project.cover ? (
            <img src={project.cover.url} alt="Capa selecionada" />
          ) : (
            <div className="cover-current-empty">
              <ImagePlus size={30} />
            </div>
          )}
          <p>
            {project.cover
              ? project.cover.name
              : "Sem capa escolhida, o pacote usa a primeira cena."}
          </p>
          <input
            ref={coverInput}
            type="file"
            className="file-input"
            tabIndex={-1}
            aria-label={project.cover ? "Trocar capa" : "Importar capa"}
            accept=".png,.jpg,.jpeg,.webp"
            disabled={locked}
            onChange={(e) => {
              onUpload(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <button
            className="button secondary"
            disabled={locked}
            onClick={() => coverInput.current?.click()}
          >
            <Upload size={16} />
            {project.cover ? "Trocar capa" : "Importar capa"}
          </button>
          <small>PNG, JPG ou WebP · até 15 MB · formato 9:16</small>
        </aside>
        <section className="cover-chat" aria-label="Chat da capa">
          <div className="cover-chat-header">
            <span>Agente</span>
            <select
              aria-label="Agente da capa"
              value={selected.provider}
              onChange={(e) =>
                setChoice({
                  provider: e.target.value as AgentChoice["provider"],
                  model: "",
                })
              }
            >
              {providers.map((provider) => (
                <option value={provider} key={provider}>
                  {names[provider]}
                  {runner?.online && !runner.providers[provider]
                    ? " · não encontrado"
                    : ""}
                </option>
              ))}
            </select>
            <select
              aria-label="Modelo do agente da capa"
              value={selected.model}
              onChange={(e) =>
                setChoice({ ...selected, model: e.target.value })
              }
            >
              <option value="">Padrão do CLI</option>
              {selected.model &&
                !catalog?.models.some((m) => m.id === selected.model) && (
                  <option value={selected.model}>{selected.model}</option>
                )}
              {catalog?.models.map((model) => (
                <option value={model.id} key={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
          </div>
          <ol className="cover-messages" aria-live="polite">
            {messages === null && (
              <li className="cover-empty">
                <LoaderCircle className="spin" size={18} />
                Carregando a conversa…
              </li>
            )}
            {messages?.length === 0 && (
              <li className="cover-empty">
                Descreva a capa que você imagina: cena, cores, texto e clima.
                Você também pode enviar imagens de referência.
              </li>
            )}
            {messages?.map((m) => (
              <li className="cover-turn" key={m.id}>
                <div className="cover-bubble user">
                  <p>{m.text}</p>
                  {m.attachments.length > 0 && (
                    <div className="cover-attachments">
                      {m.attachments.map((a) => (
                        <img key={a.url} src={a.url} alt={a.name} />
                      ))}
                    </div>
                  )}
                </div>
                <div className={`cover-bubble agent ${m.state}`}>
                  <span className="cover-agent">
                    {names[m.provider]}
                    {m.model ? ` · ${m.model}` : ""}
                  </span>
                  {pending(m) && (
                    <p className="cover-working">
                      <LoaderCircle className="spin" size={16} />
                      {m.status}
                      <button
                        className="text-button"
                        onClick={() => void cancel(m.id)}
                      >
                        Cancelar
                      </button>
                    </p>
                  )}
                  {["failed", "cancelled"].includes(m.state) && (
                    <p className="cover-failed" role="alert">
                      <CircleAlert size={16} />
                      {m.status}
                    </p>
                  )}
                  {m.state === "succeeded" && (
                    <>
                      <p>{m.reply}</p>
                      <div className="cover-images">
                        {m.images.map((image) => {
                          const current =
                            project.cover?.chat_image === `${m.id}/${image.id}`;
                          return (
                            <figure key={image.id}>
                              <a href={image.url} target="_blank" rel="noreferrer">
                                <img
                                  src={image.url}
                                  alt={`Imagem criada pelo ${names[m.provider]}`}
                                  width={image.width}
                                  height={image.height}
                                />
                              </a>
                              {current ? (
                                <span className="cover-chosen">
                                  <Check size={15} />
                                  Capa atual
                                </span>
                              ) : (
                                <button
                                  className="button secondary"
                                  disabled={locked}
                                  onClick={() => onChoose(m.id, image.id)}
                                >
                                  Usar como capa
                                </button>
                              )}
                            </figure>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              </li>
            ))}
            <li ref={end} aria-hidden="true" />
          </ol>
          {error && (
            <p className="cover-failed" role="alert">
              <CircleAlert size={16} />
              {error}
            </p>
          )}
          <form
            className="cover-composer"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            {files.length > 0 && (
              <ul className="cover-files" aria-label="Imagens anexadas">
                {files.map((file, i) => (
                  <li key={`${file.name}-${i}`}>
                    <span>{file.name}</span>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`Remover ${file.name}`}
                      onClick={() =>
                        setFiles(files.filter((_, index) => index !== i))
                      }
                    >
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <textarea
              aria-label="Mensagem para o agente da capa"
              placeholder="Ex.: fundo escuro, um robô laranja segurando um celular e o texto “IA no bolso”."
              value={text}
              maxLength={2000}
              rows={3}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <div className="cover-composer-bar">
              <input
                ref={attachInput}
                type="file"
                multiple
                className="file-input"
                tabIndex={-1}
                aria-label="Anexar imagens"
                accept=".png,.jpg,.jpeg,.webp"
                onChange={(e) => {
                  const added = Array.from(e.target.files ?? []);
                  setFiles([...files, ...added].slice(0, MAX_ATTACHMENTS));
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                className="button secondary"
                disabled={files.length >= MAX_ATTACHMENTS}
                onClick={() => attachInput.current?.click()}
              >
                <Paperclip size={16} />
                Anexar imagem
              </button>
              <button
                type="submit"
                className="button primary"
                disabled={sending || waiting || !text.trim() || !!unavailable}
              >
                {sending ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <Send size={16} />
                )}
                Enviar
              </button>
            </div>
            <p className="connection-help">
              {unavailable ? (
                <>
                  {unavailable}{" "}
                  <button
                    type="button"
                    className="text-button"
                    onClick={onConnect}
                  >
                    Configurar agentes
                  </button>
                </>
              ) : selected.provider === "claude" ? (
                "O Claude Code não tem gerador de imagens: ele desenha a capa em SVG, com formas e texto. Usa a cota do CLI."
              ) : (
                `O ${names[selected.provider]} gera a imagem com o próprio gerador. Usa a cota do CLI.`
              )}
            </p>
          </form>
        </section>
      </div>
    </>
  );
}
