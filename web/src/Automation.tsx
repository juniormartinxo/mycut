import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Clapperboard,
  FileText,
  LoaderCircle,
  Settings2,
} from "lucide-react";
import { request } from "./api";
import { FormatPicker } from "./FormatPicker";
import type { Integrations, Job, Project, VisualStyle } from "./types";

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

export function readiness(settings: Integrations | null) {
  const agents =
    !!settings?.runner.online &&
    Object.values(settings.agents).every(
      (a) => settings.runner.providers[a.provider],
    );
  const voice =
    !!settings?.elevenlabs.connected && !!settings.elevenlabs.voice_id;
  return { agents, voice };
}

export function ConnectionHint({
  settings,
  onConnect,
}: {
  settings: Integrations | null;
  onConnect: () => void;
}) {
  const ready = readiness(settings);
  return (
    <div className="automation-connection">
      <p>
        {!settings
          ? "Carregando conexões…"
          : !ready.agents
            ? "Conecte o executor e configure os CLIs para iniciar os agentes."
            : !ready.voice
              ? "Agentes prontos. Conecte sua voz ElevenLabs para produzir o vídeo completo."
              : `Agentes prontos · Voz: ${settings.elevenlabs.voice_name}`}
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
  voice: "Narração",
  render: "Vídeo",
};
export function AgentSteps({ job }: { job?: Job }) {
  if (!job || job.kind === "render") return null;
  const names =
    job.kind === "voice"
      ? ["voice"]
      : job.kind === "scenes"
        ? ["director", "reviewer"]
        : job.kind === "plan"
          ? ["research", "writer", "director", "reviewer"]
          : Object.keys(stepNames);
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
  title: string;
  brief: string;
  automation: "pipeline" | "plan" | "none";
  accent: string | null;
  visual_style: VisualStyle;
};

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
  const { title, brief, automation, accent, visual_style } = draft;
  const setTitle = (title: string) => onDraftChange({ ...draft, title });
  const setBrief = (brief: string) => onDraftChange({ ...draft, brief });
  const setAutomation = (automation: ProductionDraft["automation"]) =>
    onDraftChange({ ...draft, automation });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { settings, error: connectionError } = useIntegrations();
  const ready = readiness(settings);
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
            onCreated(
              await request<Project>("/projects", {
                method: "POST",
                body: JSON.stringify({
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
          Pauta ou link
          <textarea
            autoFocus
            rows={5}
            maxLength={12000}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="Cole a notícia, o link do vídeo ou descreva o assunto. Acrescente o que não pode faltar no Short."
            required={automation !== "none"}
          />
        </label>
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
            onDraftChange({ ...draft, visual_style, accent })
          }
          disabled={busy}
        />
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
          ).map(([value, name, detail]) => (
            <label key={value} className={automation === value ? "chosen" : ""}>
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
          <ConnectionHint settings={settings} onConnect={onConnect} />
        )}
        {automation === "pipeline" && (
          <p className="connection-help">
            A narração consome créditos ElevenLabs. O vídeo usa animações e
            diagramas e fica pronto para revisão.
          </p>
        )}
        {(error || connectionError) && (
          <div className="notice danger" role="alert">
            {error || connectionError}
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
