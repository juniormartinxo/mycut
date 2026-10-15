import { useCallback, useEffect, useRef, useState } from "react";
import brandLogo from "./assets/brand/mycut-logo-dark.webp";
import brandMark from "./assets/brand/mycut-mark-dark.webp";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  ChevronRight,
  CircleAlert,
  Clapperboard,
  Download,
  FileText,
  Coins,
  Film,
  FolderOpen,
  Headphones,
  ImagePlus,
  Layers,
  LoaderCircle,
  Monitor,
  Plus,
  Save,
  Settings2,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import type { ProductionDraft } from "./Automation";
import { Connections } from "./Connections";
import { CoverStudio } from "./CoverStudio";
import { SceneEditor } from "./SceneEditor";
import { SceneEditorDialog } from "./SceneEditorDialog";
import { newScene } from "./sceneLayout";
import { EndingStudio } from "./EndingStudio";
import { FormatPicker, RenderedScene, initialStyle } from "./FormatPicker";
import { money, ProjectCosts, tokens } from "./ProjectCosts";
import { SettingsMenu } from "./SettingsMenu";
import {
  AgentSteps,
  ConnectionHint,
  NewProduction,
  readiness,
  useIntegrations,
} from "./Automation";
import { request, fileUrl } from "./api";
import type { Health, Job, Project, Scene } from "./types";
import { useNavigation } from "./navigation";
import type { Page, Route, Tab } from "./navigation";

const activeJob = (p: Project) =>
  p.jobs.find((j) => ["running", "queued"].includes(j.state));
const completedJob = (p: Project) =>
  p.jobs.find((j) => j.state === "succeeded" && j.output);
const date = (time: number) =>
  new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(time * 1000));
const seconds = (time: number) =>
  `${Math.floor(time / 60)}:${Math.round(time % 60)
    .toString()
    .padStart(2, "0")}`;
const jobState: Record<Job["state"], string> = {
  queued: "Na fila",
  running: "Produzindo",
  succeeded: "Pronto para revisar",
  failed: "Precisa de atenção",
  cancelled: "Cancelado",
};
const tabs: { id: Tab; name: string; icon: typeof FileText }[] = [
  { id: "brief", name: "Pauta e agentes", icon: Clapperboard },
  { id: "script", name: "Roteiro", icon: FileText },
  { id: "scenes", name: "Cenas", icon: Layers },
  { id: "audio", name: "Áudio", icon: Headphones },
  { id: "cover", name: "Capa", icon: ImagePlus },
  { id: "ending", name: "Encerramento", icon: Film },
  { id: "publication", name: "Publicação", icon: Upload },
  { id: "versions", name: "Versões", icon: Film },
  { id: "costs", name: "Custos", icon: Coins },
];

function status(project: Project) {
  const active = activeJob(project);
  if (active) return { label: jobState[active.state], tone: "working" };
  const latest = project.jobs[0];
  if (latest?.state === "failed")
    return { label: "Precisa de atenção", tone: "error" };
  const done = completedJob(project);
  if (done && done.revision === project.revision)
    return {
      label: (done.output?.has_narration ?? done.output?.has_audio) ? "Pronto para revisar" : "Prévia sem voz",
      tone: "ready",
    };
  if (done) return { label: "Alterações para produzir", tone: "draft" };
  return { label: "Em edição", tone: "draft" };
}

function Brand() {
  return (
    <picture className="brand">
      <source
        media="(min-width: 761px) and (max-width: 1000px)"
        srcSet={brandMark}
        width="192"
        height="192"
      />
      <img src={brandLogo} alt="MyCut" width="909" height="250" />
    </picture>
  );
}
function Notice({
  error,
  children,
}: {
  error?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`notice ${error ? "danger" : ""}`}
      role={error ? "alert" : "status"}
    >
      <CircleAlert size={18} />
      <span>{children}</span>
    </div>
  );
}
function Empty({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <Clapperboard size={36} strokeWidth={1.4} />
      <h2>{title}</h2>
      <p>{detail}</p>
      {action}
    </div>
  );
}

export default function App() {
  const [newDraft, setNewDraft] = useState<ProductionDraft>({
    title: "",
    brief: "",
    automation: "pipeline",
    accent: null,
    visual_style: initialStyle,
  });
  const [projects, setProjects] = useState<Project[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const unsaved = useRef(false);
  const canLeave = useCallback((from: Route, to: Route) => {
    // Changing editor tabs keeps the same draft, including through browser history.
    if (from.projectId && from.projectId === to.projectId) return true;
    if (
      unsaved.current &&
      !confirm("Sair e descartar as alterações não salvas?")
    )
      return false;
    unsaved.current = false;
    return true;
  }, []);
  const { route, navigate } = useNavigation(canLeave);
  const { page, projectId: selected } = route;
  const reportDirty = useCallback((value: boolean) => {
    unsaved.current = value;
  }, []);
  useEffect(() => {
    let live = true;
    let timer: number | undefined;
    const refresh = async () => {
      try {
        const [items, state] = await Promise.all([
          request<Project[]>("/projects"),
          request<Health>("/health"),
        ]);
        if (live) {
          setProjects(items);
          setHealth(state);
          setError("");
        }
      } catch (e) {
        if (live) {
          setError(
            (e as Error).message === "Failed to fetch"
              ? "Não foi possível conectar ao estúdio. Confira se a API está em execução."
              : (e as Error).message,
          );
          setHealth(null);
        }
      } finally {
        if (live) {
          setLoading(false);
          timer = window.setTimeout(refresh, 2500);
        }
      }
    };
    void refresh();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, []);
  const select = (id: string | null, destination: Page = "projects") => {
    navigate({ page: destination, projectId: id });
  };
  const update = (project: Project) =>
    setProjects((old) => [project, ...old.filter((p) => p.id !== project.id)]);
  const project = projects.find((p) => p.id === selected);
  const queue = projects
    .flatMap((p) => p.jobs)
    .filter((j) => ["queued", "running"].includes(j.state));
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace-name">Estúdio de Shorts</div>
        <nav aria-label="Navegação principal">
          <button
            className={page === "projects" ? "nav-item active" : "nav-item"}
            onClick={() => select(null)}
          >
            <FolderOpen size={19} />
            Produções
          </button>
          <button
            className={page === "queue" ? "nav-item active" : "nav-item"}
            onClick={() => select(null, "queue")}
          >
            <Layers size={19} />
            Fila de produção
            {queue.length > 0 && (
              <span className="nav-count">{queue.length}</span>
            )}
          </button>
          <button
            className={page === "environment" ? "nav-item active" : "nav-item"}
            onClick={() => select(null, "environment")}
            aria-expanded={page === "environment"}
            aria-controls={
              page === "environment" ? "settings-sidebar-menu" : undefined
            }
            title="Configurações"
          >
            <Settings2 size={19} />
            Configurações
          </button>
          {page === "environment" && (
            <SettingsMenu
              placement="sidebar"
              section={route.settings ?? "agents"}
              onNavigate={(settings) =>
                navigate({ page: "environment", projectId: null, settings })
              }
            />
          )}
        </nav>
        <div className="sidebar-note">
          <Clapperboard size={24} strokeWidth={1.3} />
          <p>
            Da ideia ao
            <br />
            <strong>último frame.</strong>
          </p>
          <span>
            Seu espaço para criar,
            <br />
            revisar e publicar melhor.
          </span>
        </div>
        <div className="local-status">
          <span className={`status-dot ${health ? "online" : ""}`} />
          <div>
            Estúdio local
            <small>
              {health ? "Arquivos no seu computador" : "Aguardando conexão"}
            </small>
          </div>
        </div>
      </aside>
      <main className="main">
        <div className="topbar">
          <span>
            <span className="topbar-muted">Workspace</span>
            <ChevronRight size={15} />
            Meu canal
          </span>
          <span className="topbar-right">
            <Monitor size={15} /> MyCut Studio{" "}
            <span className="version">v0.1</span>
          </span>
        </div>
        {error && (
          <div className="global-error">
            <Notice error>{error}</Notice>
          </div>
        )}
        {loading ? (
          <div className="loading">
            <LoaderCircle className="spin" />
            Abrindo seu estúdio…
          </div>
        ) : project ? (
          <Editor
            key={project.id}
            project={project}
            health={health}
            onUpdate={update}
            onBack={() => select(null)}
            onDirtyChange={reportDirty}
            onConnect={() => select(null, "environment")}
            tab={route.tab ?? (project.audio ? "script" : "brief")}
            onTabChange={(tab) => navigate({ ...route, tab })}
          />
        ) : page === "new" ? (
          <NewProduction
            draft={newDraft}
            onDraftChange={setNewDraft}
            onConnect={() => select(null, "environment")}
            onCancel={() => select(null)}
            onCreated={(p) => {
              setNewDraft({
                title: "",
                brief: "",
                automation: "pipeline",
                accent: null,
                visual_style: initialStyle,
              });
              update(p);
              select(p.id);
            }}
          />
        ) : page === "queue" ? (
          <Queue
            projects={projects}
            health={health}
            onOpen={(id) => select(id)}
            onUpdate={update}
          />
        ) : page === "environment" ? (
          <Connections
            health={health}
            section={route.settings ?? "agents"}
            onNavigate={(settings) =>
              navigate({ page: "environment", projectId: null, settings })
            }
          />
        ) : (
          <section className="library">
            <div className="page-heading">
              <div>
                <h1>Suas produções</h1>
                <p>Uma ideia, várias etapas. Tudo no mesmo lugar.</p>
              </div>
              <button
                className="button primary"
                onClick={() => select(null, "new")}
              >
                <Plus size={18} />
                Novo Short
              </button>
            </div>
            <div className="library-toolbar">
              <span>
                {projects.length}{" "}
                {projects.length === 1
                  ? "produção no estúdio"
                  : "produções no estúdio"}
              </span>
              <input
                aria-label="Buscar produção"
                placeholder="Buscar pelo título…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            {projects.length === 0 ? (
              <Empty
                title="Sua primeira produção começa aqui"
                detail="Crie um Short, escreva o roteiro e dê forma à sua ideia."
                action={
                  <button
                    className="button primary"
                    onClick={() => select(null, "new")}
                  >
                    Criar primeiro Short
                    <ArrowRight size={17} />
                  </button>
                }
              />
            ) : (
              <div className="project-grid">
                {projects
                  .filter((p) =>
                    p.title
                      .toLocaleLowerCase()
                      .includes(search.toLocaleLowerCase()),
                  )
                  .map((p) => {
                    const done = completedJob(p);
                    const state = status(p);
                    const cover =
                      p.cover?.url || (done && fileUrl(done.id, "capa.png"));
                    return (
                      <button
                        className="project-card"
                        key={p.id}
                        onClick={() => select(p.id)}
                      >
                        <div
                          className="project-art"
                          style={
                            {
                              "--project-accent": p.accent,
                            } as React.CSSProperties
                          }
                        >
                          {cover ? (
                            <img src={cover} alt={`Capa de ${p.title}`} />
                          ) : (
                            <div className="cover-placeholder">
                              <Clapperboard size={40} strokeWidth={1.2} />
                              <span>
                                {p.scenes[0]?.title || "Uma nova ideia"}
                              </span>
                            </div>
                          )}
                          <span className="format-badge">
                            9:16 <span>SHORT</span>
                          </span>
                          {done?.output && (
                            <span className="duration-badge">
                              {seconds(done.output.duration)}
                            </span>
                          )}
                        </div>
                        <div className="project-card-body">
                          <span className={`badge ${state.tone}`}>
                            <span />
                            {state.label}
                          </span>
                          <h2>{p.title}</h2>
                          <div className="project-meta">
                            <span>{p.scenes.length} cenas</span>
                            <span>
                              {p.audio ? "Com narração" : "Adicionar voz"}
                            </span>
                            {tokens(p.usage_total) + p.usage_total.credits >
                              0 && (
                              <span
                                className="project-cost"
                                title="Valor aproximado em preço de tabela das APIs"
                              >
                                ≈ {money(p.usage_total.usd)}
                                {p.usage_total.unpriced > 0 && " + sem preço"}
                              </span>
                            )}
                          </div>
                          <div className="project-card-footer">
                            <span>{date(p.updated_at)}</span>
                            <ArrowRight size={19} />
                          </div>
                        </div>
                      </button>
                    );
                  })}
              </div>
            )}
            {projects.length > 0 &&
              !projects.some((p) =>
                p.title.toLowerCase().includes(search.toLowerCase()),
              ) && (
                <Empty
                  title="Nenhuma produção encontrada"
                  detail="Tente buscar por outra palavra do título."
                />
              )}
            <div className="library-bottom">
              <span>
                <Film size={17} /> Animações, fluxos e histórias que explicam.
              </span>
              <span>Publicação manual nesta versão</span>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function Editor({
  project,
  health,
  onUpdate,
  onBack,
  onDirtyChange,
  onConnect,
  tab,
  onTabChange,
}: {
  project: Project;
  health: Health | null;
  onUpdate: (p: Project) => void;
  onBack: () => void;
  onDirtyChange: (value: boolean) => void;
  onConnect: () => void;
  tab: Tab;
  onTabChange: (tab: Tab) => void;
}) {
  const legacyLink = project.scenes
    .map((s) => s.narration)
    .join(" ")
    .trim();
  const initialBrief =
    project.brief || (/^https?:\/\/\S+$/.test(legacyLink) ? legacyLink : "");
  const [draft, setDraft] = useState({ ...project, brief: initialBrief });
  const { settings, error: connectionError } = useIntegrations();
  const ready = readiness(settings);
  const visualReady =
    !!settings?.runner.online &&
    [settings.agents.director, settings.agents.reviewer].every(
      (a) => settings.runner.providers[a.provider],
    );
  const [dirty, setDirty] = useState(false);
  const [selectedScene, setSceneIndex] = useState(0);
  const [sceneEditorOpen, setSceneEditorOpen] = useState(false);
  const sceneIndex = Math.min(selectedScene, draft.scenes.length - 1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mode, setMode] = useState<"preview" | "final">(
    project.audio ? "final" : "preview",
  );
  const [viewedJob, setViewedJob] = useState<string | null>(null);
  const running = activeJob(project);
  const locked = busy || Boolean(running);
  const done =
    (viewedJob &&
      project.jobs.find(
        (j) => j.id === viewedJob && j.state === "succeeded" && j.output,
      )) ||
    completedJob(project);
  const previewJob =
    !dirty && tab !== "brief" && (tab !== "scenes" || draft.scenes[sceneIndex]?.blocks) ? done : null;
  const wordCount = draft.scenes.reduce(
    (n, s) => n + s.narration.trim().split(/\s+/).filter(Boolean).length,
    0,
  );
  useEffect(() => {
    if (!dirty && project.revision !== draft.revision) setDraft(project);
  }, [project, dirty, draft.revision]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  useEffect(() => {
    onDirtyChange(dirty);
    return () => onDirtyChange(false);
  }, [dirty, onDirtyChange]);
  const change = (values: Partial<Project>) => {
    setDraft((p) => ({ ...p, ...values }));
    setDirty(true);
    setNotice("");
  };
  const changeScene = (index: number, values: Partial<Scene>) =>
    change({
      scenes: draft.scenes.map((s, i) =>
        i === index ? { ...s, ...values } : s,
      ),
    });
  const accept = (p: Project) => {
    setDraft(p);
    setDirty(false);
    onUpdate(p);
  };
  const action = async (run: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await run();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    const {
      title,
      description,
      tags,
      sources,
      brief,
      accent,
      accent_locked = true,
      visual_style = null,
      ending_id = null,
      scenes,
      revision,
    } = draft;
    const saved = await request<Project>(`/projects/${project.id}`, {
      method: "PUT",
      body: JSON.stringify({
        title,
        description,
        tags,
        sources,
        brief,
        accent,
        accent_locked,
        visual_style,
        ending_id,
        scenes,
        revision,
      }),
    });
    accept(saved);
    return saved;
  };
  const runAgents = (kind: "pipeline" | "plan" | "voice" | "scenes") =>
    void action(async () => {
      const current =
        dirty || draft.brief !== project.brief ? await save() : draft;
      await request(`/projects/${project.id}/run`, {
        method: "POST",
        body: JSON.stringify({
          kind,
          mode: "final",
          revision: current.revision,
        }),
      });
      onUpdate(await request<Project>(`/projects/${project.id}`));
      setNotice("Produção adicionada à fila. Acompanhe cada etapa abaixo.");
      setViewedJob(null);
    });
  const upload = (kind: string, file: File | undefined) => {
    if (!file) return;
    void action(async () => {
      const current = dirty ? await save() : draft;
      const data = new FormData();
      data.append("file", file);
      accept(
        await request<Project>(
          `/projects/${project.id}/assets/${kind}?revision=${current.revision}`,
          { method: "POST", body: data },
        ),
      );
      setNotice(
        kind === "audio"
          ? "Narração importada. A sincronização será feita ao produzir."
          : "Capa atualizada.",
      );
    });
  };
  const scene = draft.scenes[sceneIndex] || draft.scenes[0];
  const editScene = (index: number) => {
    if (locked || index < 0 || index >= draft.scenes.length) return;
    setSceneIndex(index);
    setError("");
    if (draft.scenes[index].blocks) return;
    void action(async () => {
      const result = await request<{ project: Project; scene: Scene }>(`/projects/${project.id}/scene-layout/convert?revision=${draft.revision}`, {
        method: "POST", body: JSON.stringify({ scene: draft.scenes[index], project_id: project.id,
          accent: draft.accent, visual_style: draft.visual_style || null }),
      });
      onUpdate(result.project);
      setDraft(current => ({ ...current, revision: result.project.revision, images: result.project.images,
        scenes: current.scenes.map((item, position) => position === index ? result.scene : item) }));
      setDirty(true);
    });
  };
  const openSceneEditor = () => {
    setSceneEditorOpen(true);
    editScene(sceneIndex);
  };
  const incompleteScenes = draft.scenes.filter((s) => {
    if (s.blocks) return false;
    const count = s.items.filter((item) => item.trim()).length;
    return s.layout === "comparison"
      ? count !== 2
      : count < (s.layout === "flow" ? 2 : 1);
  }).length;
  const reset = () => {
    setDraft(project);
    setDirty(false);
    setError("");
    setSceneIndex(0);
  };
  return (
    <section className="editor">
      <div className="editor-heading">
        <div className="editor-title">
          <button
            className="back-button"
            aria-label="Voltar às produções"
            onClick={onBack}
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1>{draft.title}</h1>
            <p>
              <span className={`badge ${status(project).tone}`}>
                {status(project).label}
              </span>
              <span>{draft.scenes.length} cenas · 9:16</span>
            </p>
          </div>
        </div>
        <div className="editor-actions">
          <button
            className="button secondary"
            disabled={locked || !dirty}
            onClick={() =>
              void action(async () => {
                await save();
                setNotice("Alterações salvas.");
              })
            }
          >
            <Save size={16} />
            {dirty ? "Salvar alterações" : "Salvo"}
          </button>
          <div className="render-action">
            <select
              aria-label="Qualidade de produção"
              value={mode}
              onChange={(e) => setMode(e.target.value as "preview" | "final")}
              disabled={locked}
            >
              <option value="preview">Prévia · 540p</option>
              <option value="final">Final · 1080p</option>
            </select>
            <button
              className="button primary"
              disabled={locked}
              onClick={() =>
                void action(async () => {
                  const current = dirty ? await save() : draft;
                  await request(`/projects/${project.id}/renders`, {
                    method: "POST",
                    body: JSON.stringify({ mode, revision: current.revision }),
                  });
                  onUpdate(await request<Project>(`/projects/${project.id}`));
                  setViewedJob(null);
                  setNotice(
                    "Produção adicionada à fila. Você pode continuar acompanhando por aqui.",
                  );
                })
              }
            >
              <Clapperboard size={17} />
              Renderizar cenas atuais
            </button>
          </div>
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
      {notice && (
        <div className="success-message" role="status">
          <Check size={17} />
          {notice}
        </div>
      )}
      {running && (
        <div className="job-progress">
          <div>
            <LoaderCircle className="spin" size={18} />
            <strong>{running.message}</strong>
            <span>{running.progress}%</span>
            <button
              className="text-button"
              onClick={() =>
                void action(async () => {
                  await request(`/jobs/${running.id}/cancel`, {
                    method: "POST",
                  });
                  onUpdate(await request<Project>(`/projects/${project.id}`));
                })
              }
            >
              Cancelar
            </button>
          </div>
          <progress
            aria-label="Progresso da produção"
            max={100}
            value={running.progress}
          />
          {!health?.worker_online && (
            <small>Worker desconectado. Sua produção está salva na fila.</small>
          )}
        </div>
      )}
      {!running && project.jobs[0]?.state === "failed" && (
        <Notice error>
          {project.jobs[0].message} Confira as conexões ou ajuste o conteúdo
          antes de tentar novamente.
        </Notice>
      )}
      <div className="editor-workspace">
        <div className="editing-pane">
          <div
            className="editor-tabs"
            role="tablist"
            aria-label="Etapas da produção"
          >
            {tabs.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                aria-controls={`panel-${t.id}`}
                id={`tab-${t.id}`}
                className={tab === t.id ? "selected" : ""}
                onClick={() => onTabChange(t.id)}
              >
                <t.icon size={17} />
                {t.name}
                {t.id === "versions" && <span>{project.jobs.length}</span>}
              </button>
            ))}
          </div>
          <div
            role="tabpanel"
            id={`panel-${tab}`}
            aria-labelledby={`tab-${tab}`}
            className="tab-content"
          >
            {tab === "brief" && (
              <>
                <div className="section-heading">
                  <div>
                    <h2>O ponto de partida dos agentes</h2>
                    <p>
                      Cole a fonte ou descreva a ideia. O roteiro será criado a
                      partir dela.
                    </p>
                  </div>
                </div>
                <label>
                  Pauta ou link
                  <textarea
                    rows={7}
                    maxLength={12000}
                    disabled={locked}
                    value={draft.brief}
                    onChange={(e) => change({ brief: e.target.value })}
                    placeholder="Link da notícia, vídeo ou assunto do Short…"
                  />
                </label>
                <FormatPicker
                  value={draft.visual_style || null}
                  accent={draft.accent}
                  onChange={(visual_style, accent) =>
                    change({
                      visual_style,
                      accent,
                      accent_locked: true,
                    })
                  }
                  disabled={locked}
                />
                <ConnectionHint settings={settings} onConnect={onConnect} />
                {connectionError && <Notice error>{connectionError}</Notice>}
                <div className="automation-actions">
                  <button
                    className="button primary"
                    disabled={
                      locked ||
                      !draft.brief.trim() ||
                      !ready.agents ||
                      !ready.voice
                    }
                    onClick={() => runAgents("pipeline")}
                  >
                    <Clapperboard size={17} />
                    Produzir com agentes
                  </button>
                  <button
                    className="button secondary"
                    disabled={locked || !draft.brief.trim() || !ready.agents}
                    onClick={() => runAgents("plan")}
                  >
                    <FileText size={17} />
                    Gerar roteiro e cenas
                  </button>
                </div>
                <p className="connection-help">
                  Os agentes substituem o roteiro e as cenas atuais. As versões
                  anteriores ficam preservadas. O fluxo completo também gera a
                  voz ElevenLabs e renderiza o vídeo em 1080p. A voz consome
                  créditos da sua conta. A capa é criada à parte, na aba Capa.
                </p>
                <AgentSteps job={running || project.jobs[0]} />
              </>
            )}
            {tab === "script" && (
              <>
                <div className="section-heading">
                  <div>
                    <h2>A história que você vai contar</h2>
                    <p>Um trecho de narração para cada cena.</p>
                  </div>
                  <span className="word-count">
                    {wordCount} palavras
                    <br />
                    <small>~{Math.round(wordCount / 2.7)}s de leitura</small>
                  </span>
                </div>
                <fieldset disabled={locked} className="script-fields">
                  {draft.scenes.map((s, i) => (
                    <label className="script-scene" key={i}>
                      <span className="scene-number">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div>
                        <span className="script-scene-title">
                          {s.title || `Cena ${i + 1}`}
                        </span>
                        <textarea
                          aria-label={`Narração da cena ${i + 1}`}
                          value={s.narration}
                          maxLength={1400}
                          rows={3}
                          onChange={(e) =>
                            changeScene(i, { narration: e.target.value })
                          }
                          placeholder="Escreva o que será narrado nesta cena…"
                        />
                      </div>
                    </label>
                  ))}
                </fieldset>
                <div className="section-footer">
                  <button
                    className="text-button"
                    disabled={locked || draft.scenes.length >= 12}
                    onClick={() =>
                      change({
                        scenes: [
                          ...draft.scenes,
                          newScene(),
                        ],
                      })
                    }
                  >
                    <Plus size={17} />
                    Adicionar cena
                  </button>
                  {dirty && (
                    <button className="text-button muted" onClick={reset}>
                      Descartar alterações
                    </button>
                  )}
                </div>
              </>
            )}
            {tab === "scenes" && (
              <>
                <div className="section-heading">
                  <div>
                    <h2>Revise as cenas do seu Short</h2>
                    <p>
                      Edite textos e mídias de cada cena e revise as propostas dos agentes.
                    </p>
                  </div>
                  <label className="color-field">
                    <input
                      type="color"
                      aria-label="Cor de destaque do vídeo"
                      value={draft.accent}
                      disabled={locked}
                      onChange={(e) =>
                        change({ accent: e.target.value, accent_locked: true })
                      }
                    />
                    Cor do vídeo
                  </label>
                </div>
                {draft.scenes.every(s => !s.blocks) && <div className="scene-agent-actions">
                  {incompleteScenes > 0 && (
                    <Notice>
                      {incompleteScenes === 1
                        ? "Uma cena está sem o conteúdo visual completo."
                        : `${incompleteScenes} cenas estão sem o conteúdo visual completo.`}{" "}
                      Os agentes podem completá-las a partir do roteiro.
                    </Notice>
                  )}
                  <button
                    className="button secondary"
                    disabled={
                      locked ||
                      !visualReady ||
                      draft.scenes.some((s) => !s.narration.trim())
                    }
                    onClick={() => runAgents("scenes")}
                  >
                    <Layers size={17} />
                    {incompleteScenes
                      ? "Criar cenas com agentes"
                      : "Refazer cenas com agentes"}
                  </button>
                  {!visualReady && (
                    <button className="text-button" onClick={onConnect}>
                      Configurar agentes
                    </button>
                  )}
                  <p>
                    Direção visual e conferência recriam as cenas. O roteiro, a
                    voz e a capa são preservados. Usa a cota dos CLIs.
                  </p>
                  {project.jobs[0]?.kind === "scenes" && (
                    <AgentSteps job={project.jobs[0]} />
                  )}
                </div>}
                <div className="scene-selector" aria-label="Selecionar cena">
                  {draft.scenes.map((s, i) => (
                    <button
                      key={i}
                      disabled={locked}
                      aria-label={`Editar cena ${i + 1}`}
                      aria-pressed={i === sceneIndex}
                      onClick={() => setSceneIndex(i)}
                      className={i === sceneIndex ? "selected" : ""}
                    >
                      {String(i + 1).padStart(2, "0")}
                    </button>
                  ))}
                </div>
                <div className="scene-editor-launch">
                  <button type="button" className="button primary" disabled={locked} onClick={openSceneEditor}>
                    <Settings2 size={18} /> Editar cena
                  </button>
                  <p>Abra o editor para ajustar textos, imagens, vídeos e o tamanho de cada área.</p>
                </div>
                <fieldset className="scene-form" disabled={locked}>
                  {!scene.blocks && <>
                  {draft.visual_style?.media_mode === "mixed" && (
                    <div className="scene-image-controls">
                      <label>
                        Conteúdo desta cena
                        <select
                          value={scene.image_id || ""}
                          onChange={(e) =>
                            changeScene(sceneIndex, {
                              image_id: e.target.value || null,
                            })
                          }
                        >
                          <option value="">Animação e diagrama</option>
                          {(draft.images || []).map((image) => (
                            <option key={image.id} value={image.id}>
                              {image.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="button secondary scene-image-upload">
                        <ImagePlus size={16} aria-hidden="true" />
                        Adicionar imagem à cena
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            e.target.value = "";
                            if (!file) return;
                            void action(async () => {
                              const current = dirty ? await save() : draft;
                              const data = new FormData();
                              data.append("file", file);
                              const saved = await request<Project>(
                                `/projects/${project.id}/images?revision=${current.revision}`,
                                { method: "POST", body: data },
                              );
                              const uploaded = saved.images?.at(-1);
                              accept(saved);
                              if (uploaded) {
                                setDraft({
                                  ...saved,
                                  scenes: saved.scenes.map((s, index) =>
                                    index === sceneIndex
                                      ? {
                                          ...s,
                                          image_id: uploaded.id,
                                          image_fit: "contain",
                                        }
                                      : s,
                                  ),
                                });
                                setDirty(true);
                              }
                            });
                          }}
                        />
                      </label>
                      {scene.image_id && (
                        <label>
                          Enquadramento da imagem
                          <select
                            value={scene.image_fit || "contain"}
                            onChange={(e) =>
                              changeScene(sceneIndex, {
                                image_fit: e.target.value as
                                  "contain" | "cover",
                              })
                            }
                          >
                            <option value="contain">
                              Mostrar imagem inteira
                            </option>
                            <option value="cover">
                              Preencher área (pode cortar)
                            </option>
                          </select>
                        </label>
                      )}
                      <p>
                        PNG, JPG ou WebP · até 15 MB. Os agentes também podem
                        reutilizar as imagens desta produção.
                      </p>
                      {(draft.image_notes || []).map((note, i) => (
                        <p key={i}>{note}</p>
                      ))}
                    </div>
                  )}
                  <label>
                    Título em tela
                    <input
                      value={scene.title}
                      maxLength={100}
                      onChange={(e) =>
                        changeScene(sceneIndex, { title: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Formato visual
                    <select
                      value={scene.layout}
                      onChange={(e) =>
                        changeScene(sceneIndex, {
                          layout: e.target.value as Scene["layout"],
                          items:
                            e.target.value === "comparison"
                              ? scene.items.slice(0, 2)
                              : scene.items,
                        })
                      }
                    >
                      <option value="flow">Fluxo · etapas conectadas</option>
                      <option value="comparison">
                        Comparação · duas opções
                      </option>
                      <option value="statement">
                        Destaque · uma ideia central
                      </option>
                    </select>
                  </label>
                  {scene.layout === "comparison" ? (
                    [0, 1].map((side) => (
                      <label key={side}>
                        Opção {side + 1} da comparação
                        <textarea
                          rows={3}
                          maxLength={100}
                          value={scene.items[side] || ""}
                          onChange={(e) => {
                            const items = [
                              scene.items[0] || "",
                              scene.items[1] || "",
                            ];
                            items[side] = e.target.value;
                            changeScene(sceneIndex, { items });
                          }}
                        />
                      </label>
                    ))
                  ) : (
                    <label>
                      Textos do diagrama (um por linha, até 4)
                      <textarea
                        rows={5}
                        value={scene.items.join("\n")}
                        onChange={(e) =>
                          changeScene(sceneIndex, {
                            items: e.target.value.split("\n").slice(0, 4),
                          })
                        }
                      />
                    </label>
                  )}
                  </>}
                  <div className="scene-form-bottom">
                    <div>
                      <button
                        className="button secondary"
                        disabled={sceneIndex === 0}
                        aria-label="Mover cena para cima"
                        onClick={() => {
                          const scenes = [...draft.scenes];
                          [scenes[sceneIndex - 1], scenes[sceneIndex]] = [
                            scenes[sceneIndex],
                            scenes[sceneIndex - 1],
                          ];
                          change({ scenes });
                          setSceneIndex(sceneIndex - 1);
                        }}
                      >
                        <ArrowUp size={17} />
                      </button>
                      <button
                        className="button secondary"
                        disabled={sceneIndex >= draft.scenes.length - 1}
                        aria-label="Mover cena para baixo"
                        onClick={() => {
                          const scenes = [...draft.scenes];
                          [scenes[sceneIndex + 1], scenes[sceneIndex]] = [
                            scenes[sceneIndex],
                            scenes[sceneIndex + 1],
                          ];
                          change({ scenes });
                          setSceneIndex(sceneIndex + 1);
                        }}
                      >
                        <ArrowDown size={17} />
                      </button>
                    </div>
                    <button
                      className="text-button destructive"
                      disabled={draft.scenes.length <= 1}
                      onClick={() => {
                        change({
                          scenes: draft.scenes.filter(
                            (_, i) => i !== sceneIndex,
                          ),
                        });
                        setSceneIndex(Math.max(0, sceneIndex - 1));
                      }}
                    >
                      <Trash2 size={16} />
                      Remover cena
                    </button>
                  </div>
                </fieldset>
                <div className="scene-note">
                  <Layers size={18} />
                  {scene.blocks ? "A composição usa o mesmo renderizador da exportação. Vídeos são reproduzidos no arquivo final." : "Animações e legendas são aplicadas na renderização."}
                </div>
              </>
            )}
            {tab === "audio" && (
              <>
                <div className="section-heading">
                  <div>
                    <h2>Uma voz. Sua identidade.</h2>
                    <p>
                      Gere a narração com sua voz ElevenLabs ou importe um
                      áudio.
                    </p>
                  </div>
                </div>
                <ConnectionHint settings={settings} onConnect={onConnect} />
                <div className="automation-actions">
                  <button
                    className="button primary"
                    disabled={
                      locked ||
                      !ready.voice ||
                      !draft.scenes.every((s) => s.narration.trim())
                    }
                    onClick={() => runAgents("voice")}
                  >
                    <Headphones size={17} />
                    Gerar narração ElevenLabs
                  </button>
                </div>
                <p className="connection-help">
                  {draft.scenes.map((s) => s.narration).join("\n\n").length}{" "}
                  caracteres de roteiro · usa créditos ElevenLabs. Gere a voz
                  depois de revisar o texto.
                </p>
                <div className="media-block">
                  <h3>
                    <Headphones size={18} />
                    Narração
                  </h3>
                  {draft.audio ? (
                    <>
                      <div className="file-info">
                        <div>
                          <strong>{draft.audio.name}</strong>
                          <span>
                            {seconds(draft.audio.duration || 0)} · áudio da
                            produção
                          </span>
                        </div>
                        <Check size={20} />
                      </div>
                      <audio
                        controls
                        src={draft.audio.url}
                        preload="metadata"
                      />
                      <UploadControl
                        kind="audio"
                        label="Substituir narração"
                        disabled={locked}
                        onFile={(file) => upload("audio", file)}
                      />
                    </>
                  ) : (
                    <UploadControl
                      kind="audio"
                      label="Importar narração"
                      disabled={locked}
                      onFile={(file) => upload("audio", file)}
                      large
                    />
                  )}
                  {draft.audio && !draft.audio_matches_script && !dirty && (
                    <>
                      <Notice>
                        O roteiro mudou depois da importação. Ouça o áudio e
                        confira se ele corresponde ao texto atual.
                      </Notice>
                      <button
                        className="button secondary"
                        disabled={locked}
                        onClick={() =>
                          void action(async () => {
                            accept(
                              await request<Project>(
                                `/projects/${project.id}/confirm-audio?revision=${draft.revision}`,
                                { method: "POST" },
                              ),
                            );
                            setNotice(
                              "Correspondência confirmada. O alinhamento ainda será verificado ao produzir.",
                            );
                          })
                        }
                      >
                        Conferi: este áudio corresponde ao roteiro
                      </button>
                    </>
                  )}
                  <p className="helper">
                    MP3, WAV, M4A, FLAC ou OGG. Até 100 MB e 3 minutos. A voz
                    não é enviada a um serviço externo.
                  </p>
                </div>
              </>
            )}
            {tab === "cover" && (
              <CoverStudio
                project={draft}
                locked={locked}
                settings={settings}
                onConnect={onConnect}
                onUpload={(file) => upload("cover", file)}
                onChoose={(job, image) =>
                  void action(async () => {
                    const current = dirty ? await save() : draft;
                    accept(
                      await request<Project>(
                        `/projects/${project.id}/cover/select`,
                        {
                          method: "POST",
                          body: JSON.stringify({
                            job_id: job,
                            image_id: image,
                            revision: current.revision,
                          }),
                        },
                      ),
                    );
                    setNotice("Capa atualizada.");
                  })
                }
              />
            )}
            {tab === "ending" && (
              <EndingStudio
                value={draft.ending_id || null}
                disabled={locked}
                onChange={(ending_id) => change({ ending_id })}
              />
            )}
            {tab === "publication" && (
              <>
                <div className="section-heading">
                  <div>
                    <h2>Pronto para encontrar seu público</h2>
                    <p>Prepare os textos que vão acompanhar o Short.</p>
                  </div>
                </div>
                <fieldset disabled={locked} className="publication-form">
                  <label>
                    Título no YouTube
                    <span className="field-hint">{draft.title.length}/100</span>
                    <input
                      value={draft.title}
                      maxLength={100}
                      onChange={(e) => change({ title: e.target.value })}
                    />
                  </label>
                  <label>
                    Descrição
                    <textarea
                      rows={6}
                      maxLength={5000}
                      value={draft.description}
                      onChange={(e) => change({ description: e.target.value })}
                      placeholder="Explique o assunto e acrescente suas hashtags."
                    />
                  </label>
                  <label>
                    Tags
                    <input
                      value={draft.tags}
                      maxLength={500}
                      onChange={(e) => change({ tags: e.target.value })}
                      placeholder="Claude Code, inteligência artificial, programação"
                    />
                  </label>
                  <label>
                    Fontes e referências
                    <textarea
                      rows={4}
                      maxLength={8000}
                      value={draft.sources}
                      onChange={(e) => change({ sources: e.target.value })}
                      placeholder="Cole as referências usadas no roteiro."
                    />
                  </label>
                </fieldset>
                <div className="scene-note">
                  <Upload size={17} />O pacote inclui esses textos. O envio ao
                  YouTube é manual nesta versão.
                </div>
              </>
            )}
            {tab === "costs" && <ProjectCosts project={project} />}
            {tab === "versions" && (
              <>
                <div className="section-heading">
                  <div>
                    <h2>Cada versão, preservada</h2>
                    <p>Revise os resultados e acompanhe suas tentativas.</p>
                  </div>
                </div>
                {!project.jobs.length ? (
                  <Empty
                    title="O primeiro frame está por vir"
                    detail="Gere uma prévia para ver sua primeira versão aqui."
                  />
                ) : (
                  <div className="history">
                    {project.jobs.map((j, i) => (
                      <div className="history-item" key={j.id}>
                        <div className={`history-symbol ${j.state}`}>
                          <Film size={18} />
                        </div>
                        <div>
                          <strong>
                            {j.kind === "plan"
                              ? "Roteiro e cenas"
                              : j.kind === "scenes"
                                ? "Cenas"
                                : j.kind === "voice"
                                  ? "Narração"
                                  : j.mode === "final"
                                    ? "Vídeo final"
                                    : "Prévia"}{" "}
                            <span>· versão {project.jobs.length - i}</span>
                          </strong>
                          <p>{j.message}</p>
                          <div className="version-materials">
                            {j.materials.map((name) => (
                              <a
                                key={name}
                                href={`/api/jobs/${j.id}/materials/${name}`}
                                download
                              >
                                {{
                                  "input.json": "Entrada anterior",
                                  "roteiro.txt": "Roteiro",
                                  "publicacao.txt": "Publicação",
                                  "capa.png": "Capa",
                                  "narracao.wav": "Áudio",
                                }[name] || name}
                              </a>
                            ))}
                          </div>
                          <small>
                            {date(j.created_at)} · revisão {j.revision}
                            {j.revision !== project.revision
                              ? " · conteúdo anterior"
                              : ""}
                          </small>
                        </div>
                        {j.state === "succeeded" && j.output && (
                          <button
                            className="button secondary"
                            onClick={() => setViewedJob(j.id)}
                          >
                            Assistir
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
        <aside className="preview-pane">
          <div className="preview-heading">
            <h2>Na tela</h2>
            <span>9:16</span>
          </div>
          <div className="preview-stage">
            {previewJob ? (
              <video
                key={previewJob.id}
                controls
                playsInline
                preload="metadata"
                poster={fileUrl(previewJob.id, "capa.png")}
                src={fileUrl(previewJob.id, "short.mp4")}
                aria-label="Prévia do Short"
              />
            ) : draft.visual_style || scene.blocks ? (
              <RenderedScene
                scene={scene}
                style={draft.visual_style || null}
                accent={draft.accent}
                projectId={project.id}
              />
            ) : (
              <div
                className="live-scene"
                style={
                  { "--project-accent": draft.accent } as React.CSSProperties
                }
              >
                <span>MYCUT</span>
                <h3>{scene.title}</h3>
                <SceneDiagram scene={scene} />
                <div className="preview-narration">
                  {scene.narration || "Sua narração aparece aqui."}
                </div>
              </div>
            )}
          </div>
          <div className="preview-details">
            <span>
              {previewJob?.output
                ? `${previewJob.output.width} × ${previewJob.output.height}`
                : "Composição da cena"}
              {previewJob?.output
                ? ` · ${seconds(previewJob.output.duration)}`
                : ""}
            </span>
            <small>
              {previewJob
                ? previewJob.revision !== project.revision
                  ? "Versão anterior. Gere novamente após salvar."
                  : previewJob.output?.has_narration === false && previewJob.output?.ending?.has_audio
                    ? "Cenas sem narração · encerramento com áudio"
                  : previewJob.output?.has_audio
                    ? "Com narração · revisão final pendente"
                    : "Sem narração · tempos estimados"
                : "Gere uma prévia para assistir à animação."}
            </small>
          </div>
          {done && (
            <div className="download-actions">
              <a
                className="button secondary"
                href={fileUrl(done.id, "short.mp4", true)}
              >
                <Download size={16} />
                MP4
              </a>
              <a
                className="button secondary"
                href={`/api/jobs/${done.id}/package`}
              >
                <FolderOpen size={16} />
                Pacote completo
              </a>
            </div>
          )}
          <div className="shot-list">
            <div>
              <h3>Sequência de cenas</h3>
              <span>{draft.scenes.length}</span>
            </div>
            {draft.scenes.map((s, i) => (
              <button
                key={i}
                className={sceneIndex === i ? "selected" : ""}
                onClick={() => {
                  setSceneIndex(i);
                  onTabChange("scenes");
                }}
              >
                <span>{String(i + 1).padStart(2, "0")}</span>
                <span>{s.title || "Cena sem título"}</span>
                <ChevronRight size={14} />
              </button>
            ))}
          </div>
        </aside>
      </div>
      {sceneEditorOpen && <SceneEditorDialog sceneNumber={sceneIndex + 1} busy={locked} dirty={dirty} error={error}
        scenes={draft.scenes} onSceneChange={editScene}
        onSave={() => void action(async () => { await save(); setNotice("Alterações das cenas salvas."); })}
        onClose={() => { setSceneEditorOpen(false); if (dirty) setNotice("Alterações mantidas no rascunho. Salve quando estiver pronto."); }}>
        {scene.blocks ? <SceneEditor key={scene.id || sceneIndex} project={draft} scene={scene} disabled={locked}
          onChange={next => changeScene(sceneIndex, next)} save={save} onProject={accept} onBusy={setBusy} />
          : error ? <button type="button" className="button secondary" disabled={locked} onClick={() => editScene(sceneIndex)}>Tentar abrir novamente</button>
            : <p role="status">Abrindo editor…</p>}
      </SceneEditorDialog>}
    </section>
  );
}

function SceneDiagram({ scene }: { scene: Scene }) {
  const values = scene.items.filter((item) => item.trim());
  const items =
    scene.layout === "statement" && values.length ? [values.join(" ")] : values;
  return (
    <div className={`scene-diagram ${scene.layout}`}>
      {(items.length ? items : ["Aguardando conteúdo visual"]).map(
        (item, i) => (
          <div key={i}>
            <span>{item}</span>
            {scene.layout === "flow" && i < items.length - 1 && (
              <ArrowDown size={20} />
            )}
          </div>
        ),
      )}
    </div>
  );
}
function UploadControl({
  kind,
  label,
  disabled,
  onFile,
  large,
}: {
  kind: string;
  label: string;
  disabled: boolean;
  onFile: (file?: File) => void;
  large?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={input}
        type="file"
        className="file-input"
        tabIndex={-1}
        aria-label={label}
        accept={
          kind === "audio"
            ? ".mp3,.wav,.m4a,.flac,.ogg"
            : ".png,.jpg,.jpeg,.webp"
        }
        onChange={(e) => {
          onFile(e.target.files?.[0]);
          e.target.value = "";
        }}
        disabled={disabled}
      />
      <button
        className={large ? "upload-zone" : "button secondary"}
        disabled={disabled}
        onClick={() => input.current?.click()}
      >
        <Upload size={large ? 28 : 16} />
        <span>{label}</span>
        {large && <small>Escolha um arquivo do seu computador</small>}
      </button>
    </>
  );
}
function Queue({
  projects,
  health,
  onOpen,
  onUpdate,
}: {
  projects: Project[];
  health: Health | null;
  onOpen: (id: string) => void;
  onUpdate: (p: Project) => void;
}) {
  const jobs = projects
    .flatMap((p) => p.jobs.map((j) => ({ ...j, title: p.title })))
    .sort((a, b) => b.created_at - a.created_at);
  const [error, setError] = useState("");
  return (
    <section className="queue-page">
      <div className="page-heading">
        <div>
          <h1>Fila de produção</h1>
          <p>
            Seu estúdio continua trabalhando enquanto você cuida da próxima
            ideia.
          </p>
        </div>
        <span className={`badge ${health?.worker_online ? "ready" : "draft"}`}>
          <span />
          {health?.worker_online ? "Worker conectado" : "Worker desconectado"}
        </span>
      </div>
      {error && <Notice error>{error}</Notice>}
      {!jobs.length ? (
        <Empty
          title="Tudo tranquilo por aqui"
          detail="Suas produções aparecem aqui quando você gera uma prévia ou vídeo final."
        />
      ) : (
        <div className="queue-list">
          {jobs.map((j) => (
            <article key={j.id}>
              <div className={`queue-icon ${j.state}`}>
                <Clapperboard size={23} />
              </div>
              <div className="queue-content">
                <button
                  className="text-button"
                  onClick={() => onOpen(j.project_id)}
                >
                  {j.title}
                </button>
                <p>{j.message}</p>
                {j.state === "running" && (
                  <progress
                    value={j.progress}
                    max={100}
                    aria-label="Progresso da produção"
                  />
                )}
                <small>
                  {date(j.created_at)} ·{" "}
                  {j.kind === "plan"
                    ? "Roteiro e cenas"
                    : j.kind === "scenes"
                      ? "Cenas"
                      : j.kind === "voice"
                        ? "Narração"
                        : j.mode === "final"
                          ? "1080p"
                          : "540p"}
                </small>
              </div>
              <span
                className={`badge ${j.state === "succeeded" ? "ready" : j.state === "failed" ? "error" : "draft"}`}
              >
                {jobState[j.state]}
              </span>
              {["queued", "running"].includes(j.state) && (
                <button
                  className="icon-button"
                  aria-label="Cancelar produção"
                  onClick={async () => {
                    try {
                      await request(`/jobs/${j.id}/cancel`, { method: "POST" });
                      onUpdate(
                        await request<Project>(`/projects/${j.project_id}`),
                      );
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  <X size={18} />
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
