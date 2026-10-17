import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Clapperboard,
  FileText,
  LoaderCircle,
  Paperclip,
  Settings2,
  X,
} from "lucide-react";
import { request } from "./api";
import { FormatPicker, initialStyle } from "./FormatPicker";
import { money, providers } from "./ProjectCosts";
import { useChannels } from "./ChannelSettings";
import type { ArtMode, ChannelVoice, Integrations, Job, Project, VisualStyle } from "./types";

export function useIntegrations() {
  const [settings, setSettings] = useState<Integrations | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const value = await request<Integrations>("/integrations");
        if (live) {
          setSettings(value);
          setError("");
        }
      } catch (e) {
        if (live) {
          setSettings(null);
          setError((e as Error).message);
        }
      } finally {
        if (live) timer = window.setTimeout(refresh, 4000);
      }
    };
    void refresh();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, []);
  return { settings, error };
}

/** The Arte only counts for a Short livre that generates images; voice is the project's or its channel's, over Conexões. */
export function readiness(
  settings: Integrations | null,
  art = false,
  voice: ChannelVoice | null = null,
) {
  const agents =
    !!settings?.runner.online &&
    Object.entries(settings.agents).every(
      ([role, a]) =>
        (role === "art" && !art) || settings.runner.providers[a.provider],
    );
  return {
    agents,
    voice:
      !!settings?.elevenlabs.connected &&
      !!(voice?.voice_id || settings.elevenlabs.voice_id),
    voiceName: voice?.voice_name || settings?.elevenlabs.voice_name || "",
  };
}

export function ConnectionHint({
  settings,
  onConnect,
  voice = null,
}: {
  settings: Integrations | null;
  onConnect: () => void;
  voice?: ChannelVoice | null;
}) {
  const ready = readiness(settings, false, voice);
  return (
    <div className="automation-connection">
      <p>
        {!settings
          ? "Carregando conexões…"
          : !ready.agents
            ? "Conecte o executor e configure os CLIs para iniciar os agentes."
            : !ready.voice
              ? "Agentes prontos. Conecte sua voz ElevenLabs para produzir o vídeo completo."
              : `Agentes prontos · Voz: ${ready.voiceName}`}
      </p>
      <button type="button" className="text-button" onClick={onConnect}>
        <Settings2 size={16} />
        Configurar conexões
      </button>
    </div>
  );
}

const stepNames: Record<string, string> = {
  research: "Pesquisa",
  writer: "Roteiro",
  director: "Animações",
  reviewer: "Conferência",
  art: "Arte",
  voice: "Narração",
  render: "Vídeo",
};
export function AgentSteps({ job }: { job?: Job }) {
  if (!job || job.kind === "render") return null;
  const started = (name: string) => job.steps.some((s) => s.name === name);
  const names =
    job.kind === "voice"
      ? ["voice"]
      : job.kind === "scenes"
        ? ["director", "reviewer"]
        : job.kind === "art"
          ? ["art", ...["voice", "render"].filter(started)]
          : job.kind === "plan"
            ? ["research", "writer", "director", "reviewer", "art"].filter(
                (name) => name !== "art" || started(name),
              )
            : Object.keys(stepNames).filter(
                (name) => name !== "art" || started(name),
              );
  return (
    <ol className="agent-steps" aria-label="Etapas dos agentes">
      {names.map((name) => {
        const step = job.steps.find((s) => s.name === name);
        const state = step?.state || "pending";
        return (
          <li key={name} className={state}>
            <span className="step-dot" />
            <div>
              <strong>{stepNames[name]}</strong>
              <small>
                {step?.message ||
                  (["failed", "cancelled"].includes(job.state)
                    ? "Não executada"
                    : "Aguardando")}
              </small>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export type ProductionDraft = {
  /** null until the channels load: the default channel. */
  channel_id: string | null;
  title: string;
  brief: string;
  automation: "pipeline" | "plan" | "none";
  accent: string | null;
  visual_style: VisualStyle;
  /** Short livre (ADR 0005): the brief is the prompt and the images go to the agents as references. */
  free: boolean;
  attachments: File[];
  /** Short livre: what the Arte generates before the voice. */
  art: ArtMode;
};

export const emptyDraft = (visual_style: VisualStyle): ProductionDraft => ({
  channel_id: null,
  title: "",
  brief: "",
  automation: "pipeline",
  accent: null,
  visual_style,
  free: false,
  attachments: [],
  art: "bases",
});
const artModes: [ArtMode, string, string][] = [
  [
    "bases",
    "Conferir as imagens-base primeiro",
    "A Arte gera as fichas de personagem e os cenários e espera você conferir e orientar antes das demais imagens.",
  ],
  [
    "all",
    "Gerar todas as imagens",
    "Bases e imagens das cenas de uma vez, sem parar antes da voz.",
  ],
  [
    "none",
    "Sem imagens geradas",
    "As cenas usam só os anexos, textos e animações.",
  ],
];
// The director asks for at most this many images per Short.
const MAX_ART_IMAGES = 12;
const MAX_ATTACHMENTS = 8;
export const FREE_BRIEF_LIMIT = 40000;
const isText = (file: File) => /\.(md|markdown|txt)$/i.test(file.name);

export function NewProduction({
  draft,
  onDraftChange,
  onCreated,
  onCancel,
  onConnect,
}: {
  draft: ProductionDraft;
  onDraftChange: (value: ProductionDraft) => void;
  onCreated: (p: Project) => void;
  onCancel: () => void;
  onConnect: () => void;
}) {
  const {
    channel_id,
    title,
    brief,
    automation,
    accent,
    visual_style,
    free,
    attachments,
    art,
  } = draft;
  const setTitle = (title: string) => onDraftChange({ ...draft, title });
  const setBrief = (brief: string) => onDraftChange({ ...draft, brief });
  const setAutomation = (automation: ProductionDraft["automation"]) =>
    onDraftChange({ ...draft, automation });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const attach = async (files: File[]) => {
    setError("");
    // Text and Markdown join the prompt where the agents and the user can read them.
    let text = brief;
    for (const file of files.filter(isText))
      text += `${text.trim() ? "\n\n" : ""}## Anexo: ${file.name}\n\n${(await file.text()).trim()}`;
    const images = [...attachments, ...files.filter((file) => !isText(file))];
    setError(
      [
        images.length > MAX_ATTACHMENTS &&
          `Anexe até ${MAX_ATTACHMENTS} imagens de referência; as demais ficaram de fora.`,
        text.length > FREE_BRIEF_LIMIT &&
          "O prompt com os anexos de texto passou do limite e foi cortado.",
      ]
        .filter(Boolean)
        .join(" "),
    );
    onDraftChange({
      ...draft,
      brief: text.slice(0, FREE_BRIEF_LIMIT),
      attachments: images.slice(0, MAX_ATTACHMENTS),
    });
  };
  const { settings, error: connectionError } = useIntegrations();
  const { channels, error: channelError } = useChannels();
  const channel =
    channels?.find((item) => item.id === channel_id) ??
    channels?.find((item) => item.default);
  // The format starts with the channel's brand; one the author wrote stays when the channel changes.
  const chooseChannel = (id: string) => {
    const next = channels?.find((item) => item.id === id);
    const inherited = [channel?.brand, initialStyle.channel_name].includes(
      visual_style.channel_name,
    );
    onDraftChange({
      ...draft,
      channel_id: id,
      visual_style: inherited
        ? { ...visual_style, channel_name: next?.brand ?? "" }
        : visual_style,
    });
  };
  useEffect(() => {
    if (channel_id === null && channel) chooseChannel(channel.id);
    // Only the first load of the channels picks the default one.
  }, [channel_id, channel]);
  const ready = readiness(settings, free && art !== "none", channel?.voice);
  const artist = settings?.agents.art?.provider;
  const perImage = artist ? settings?.pricing?.images?.[artist] : null;
  const enabled =
    automation === "none"
      ? !!title.trim()
      : !!brief.trim() &&
        ready.agents &&
        (automation === "plan" || ready.voice);
  return (
    <section className="new-project">
      <button className="text-button" onClick={onCancel}>
        <ArrowLeft size={17} />
        Voltar às produções
      </button>
      <h1>Da pauta ao Short.</h1>
      <p>
        Traga um link ou uma ideia. Os agentes pesquisam, escrevem e produzem.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            if (free) {
              const body = new FormData();
              body.append(
                "project",
                JSON.stringify({
                  channel_id: channel?.id,
                  title: title.trim() || "Short livre",
                  brief,
                  automation,
                  art,
                }),
              );
              attachments.forEach((file) => body.append("files", file));
              onCreated(
                await request<Project>("/projects/free", {
                  method: "POST",
                  body,
                }),
              );
              return;
            }
            onCreated(
              await request<Project>("/projects", {
                method: "POST",
                body: JSON.stringify({
                  channel_id: channel?.id,
                  title: title.trim() || "Nova pauta",
                  brief,
                  automation,
                  accent,
                  visual_style,
                }),
              }),
            );
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Canal
          <select
            value={channel?.id ?? ""}
            onChange={(e) => chooseChannel(e.target.value)}
            disabled={busy || !channels}
          >
            {!channels && <option value="">Carregando canais…</option>}
            {channels?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {free ? "Prompt do Short livre" : "Pauta ou link"}
          <textarea
            autoFocus
            className={free ? "free-prompt" : undefined}
            rows={free ? 16 : 5}
            maxLength={free ? FREE_BRIEF_LIMIT : 12000}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder={
              free
                ? "Cole uma ideia ou um roteiro completo em Markdown: tempos, narração, texto na tela, fichas, tabelas e blocos de código."
                : "Cole a notícia, o link do vídeo ou descreva o assunto. Acrescente o que não pode faltar no Short."
            }
            required={automation !== "none"}
          />
        </label>
        {free && (
          <div className="free-attachments">
            <label className="button secondary">
              <Paperclip size={16} />
              Anexar referências
              <input
                type="file"
                multiple
                accept="image/png,image/jpeg,image/webp,.md,.markdown,.txt"
                disabled={busy}
                onChange={(e) => {
                  const files = [...(e.target.files || [])];
                  e.target.value = "";
                  void attach(files);
                }}
              />
            </label>
            <small>
              Imagens PNG, JPG ou WebP (até {MAX_ATTACHMENTS}, 15 MB cada)
              entram na biblioteca da produção como referência. Textos e
              Markdown são acrescentados ao prompt.
            </small>
            {attachments.length > 0 && (
              <ul aria-label="Imagens anexadas">
                {attachments.map((file, index) => (
                  <li key={`${file.name}-${index}`}>
                    {file.name}
                    <button
                      type="button"
                      aria-label={`Remover ${file.name}`}
                      disabled={busy}
                      onClick={() =>
                        onDraftChange({
                          ...draft,
                          attachments: attachments.filter(
                            (_, i) => i !== index,
                          ),
                        })
                      }
                    >
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <label>
          Título de trabalho {automation !== "none" && "(opcional)"}
          <input
            maxLength={100}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="O agente de roteiro criará o título para publicar"
            required={automation === "none"}
          />
        </label>
        <FormatPicker
          value={visual_style}
          accent={accent || "#BE4D2A"}
          onChange={(visual_style, accent) =>
            onDraftChange({ ...draft, visual_style, accent, free: false })
          }
          disabled={busy}
          free={free}
          onFreeChange={(value) =>
            onDraftChange({
              ...draft,
              free: value,
              // An empty editor has no agents to follow a prompt.
              automation:
                value && automation === "none" ? "pipeline" : automation,
            })
          }
        />
        {free && (
          <fieldset className="template-choice art-choice" disabled={busy}>
            <legend>Imagens da Arte</legend>
            {artModes.map(([value, name, detail]) => (
              <label key={value} className={art === value ? "chosen" : ""}>
                <input
                  type="radio"
                  name="art"
                  checked={art === value}
                  onChange={() => onDraftChange({ ...draft, art: value })}
                />
                <span>
                  <strong>{name}</strong>
                  <small>{detail}</small>
                </span>
              </label>
            ))}
            {art !== "none" && (
              <p className="connection-help" role="status">
                Até {MAX_ART_IMAGES} imagens
                {artist && ` com ${providers[artist]}`}
                {typeof perImage === "number"
                  ? ` · estimativa de até ${money(MAX_ART_IMAGES * perImage)} (${money(perImage)} por imagem)`
                  : " · sem preço por imagem configurado"}
                . A estimativa exata aparece antes de cada geração, e o valor
                registrado fica em Custos.
              </p>
            )}
          </fieldset>
        )}
        <fieldset className="template-choice" disabled={busy}>
          <legend>O que produzir</legend>
          {(
            [
              [
                "pipeline",
                "Short completo",
                "Pesquisa, roteiro, animações, capa, conferência, voz e vídeo.",
              ],
              [
                "plan",
                "Roteiro e cenas primeiro",
                "Os agentes pesquisam e preparam a produção, sem gerar voz.",
              ],
              [
                "none",
                "Abrir editor vazio",
                "Edição manual opcional para um roteiro que você já tem.",
              ],
            ] as const
          )
            .filter(([value]) => !free || value !== "none")
            .map(([value, name, detail]) => (
              <label
                key={value}
                className={automation === value ? "chosen" : ""}
              >
                <input
                  type="radio"
                  name="automation"
                  checked={automation === value}
                  onChange={() => setAutomation(value)}
                />
                <span>
                  <strong>{name}</strong>
                  <small>{detail}</small>
                </span>
              </label>
            ))}
        </fieldset>
        {automation !== "none" && (
          <ConnectionHint
            settings={settings}
            onConnect={onConnect}
            voice={channel?.voice}
          />
        )}
        {automation === "pipeline" && (
          <p className="connection-help">
            A narração consome créditos ElevenLabs.{" "}
            {free
              ? "Os agentes compõem as cenas e planos a partir do prompt; o vídeo fica pronto para revisão."
              : "O vídeo usa animações e diagramas e fica pronto para revisão."}
          </p>
        )}
        {(error || connectionError || channelError) && (
          <div className="notice danger" role="alert">
            {error || connectionError || channelError}
          </div>
        )}
        <button className="button primary" disabled={busy || !enabled}>
          {busy ? (
            <LoaderCircle size={18} className="spin" />
          ) : automation === "none" ? (
            <FileText size={18} />
          ) : (
            <Clapperboard size={18} />
          )}
          {automation === "none"
            ? "Criar produção"
            : automation === "plan"
              ? "Criar roteiro com agentes"
              : "Produzir com agentes"}
        </button>
      </form>
    </section>
  );
}
