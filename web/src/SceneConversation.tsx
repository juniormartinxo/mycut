import { useCallback, useEffect, useState } from "react";
import { MessageSquare, Flag, Check, X } from "lucide-react";
import { request } from "./api";
import { RenderedScene } from "./FormatPicker";
import type { Project, Scene, SceneMessage, SceneThread } from "./types";

type Conversations = { threads: SceneThread[]; messages: SceneMessage[] };
export function SceneConversation({ project, scene, blockId, objectId, disabled, save, onAccepted, onBusy, onThreads }: {
  project: Project; scene: Scene; blockId: string; objectId?: string; disabled: boolean;
  save: () => Promise<Project>; onAccepted: (project: Project) => void; onBusy: (busy: boolean) => void; onThreads: (threads: SceneThread[]) => void;
}) {
  const [data, setData] = useState<Conversations>({ threads: [], messages: [] });
  const [scope, setScope] = useState<SceneThread["scope"]>(objectId ? "object" : "block");
  const [historyId, setHistoryId] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => { setScope(objectId ? "object" : "block"); setHistoryId(""); setPreview(null); }, [objectId, blockId, scene.id]);
  const refresh = useCallback(async () => {
    const result = await request<Conversations>(`/projects/${project.id}/scene-conversations`);
    setData(result); onThreads(result.threads); setPollError("");
  }, [project.id, onThreads]);
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try { const result = await request<Conversations>(`/projects/${project.id}/scene-conversations`); if (alive) { setData(result); onThreads(result.threads); setPollError(""); } }
      catch (e) { if (alive) setPollError((e as Error).message); }
    };
    void poll();
    const timer = setInterval(() => void poll(), 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [project.id, project.revision, onThreads]);
  const targetId = scope === "scene" ? scene.id! : scope === "object" ? objectId! : blockId;
  const selectedThread = data.threads.find(t => t.scene_id === scene.id && t.scope === scope && t.target_id === targetId);
  const activeThread = historyId ? data.threads.find(t => t.id === historyId) : selectedThread;
  const messages = data.messages.filter(m => m.thread_id === activeThread?.id);
  const running = data.messages.find(m => m.state === "queued" || m.state === "running");
  const target = { scene_id: scene.id, scope, target_id: targetId };
  const action = async (run: () => Promise<void>) => {
    setBusy(true); onBusy(true); setError("");
    try { await run(); await refresh(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); onBusy(false); }
  };
  const mark = (marked: boolean, resolved: boolean) => void action(async () => {
    await save();
    await request(`/projects/${project.id}/scene-conversations`, { method: "PUT", body: JSON.stringify({ ...target, marked, resolved }) });
  });
  return <section className="scene-conversation" aria-label="Conversa sobre a cena">
    <h3><MessageSquare size={18} /> Conversar com o agente</h3>
    <div className="block-field-grid">
      <label>Alcance do pedido<select value={scope} disabled={busy || disabled} onChange={e => { setScope(e.target.value as SceneThread["scope"]); setHistoryId(""); setPreview(null); }}>
        {objectId && <option value="object">Objeto selecionado</option>}
        {!objectId && <option value="block">Bloco vazio</option>}
        <option value="scene">Cena inteira</option>
      </select></label>
      <label>Histórico<select value={historyId} onChange={e => { setHistoryId(e.target.value); setPreview(null); }}>
        <option value="">Conversa do alvo atual</option>
        {data.threads.filter(t => t.id !== selectedThread?.id).map((t, i) => <option key={t.id} value={t.id}>
          {t.archived ? "Arquivada" : t.resolved ? "Resolvida" : t.marked ? "Marcada" : "Conversa"} · {t.scope === "object" ? "objeto" : t.scope === "block" ? "bloco" : "cena"} {i + 1}
        </option>)}
      </select></label>
    </div>
    {!historyId && <div className="block-actions">
      <button type="button" className="button secondary" disabled={disabled || busy} aria-pressed={Boolean(selectedThread?.marked)} onClick={() => mark(!selectedThread?.marked, Boolean(selectedThread?.resolved))}>
        <Flag size={15} /> {selectedThread?.marked ? "Desmarcar conversa" : "Marcar para conversar"}
      </button>
      {selectedThread && <button type="button" className="text-button" disabled={disabled || busy} onClick={() => mark(Boolean(selectedThread.marked), !selectedThread.resolved)}>
        {selectedThread.resolved ? "Reabrir conversa" : "Marcar como resolvida"}
      </button>}
    </div>}
    {(error || pollError) && <p className="notice danger" role="alert">{error || pollError}</p>}
    <div className="scene-messages" aria-live="polite">
      {!messages.length && <p className="block-hint">Discuta o objeto ou peça uma alteração. O agente usa a cena como contexto; você revisa antes de aplicar.</p>}
      {messages.map(message => <article key={message.id}>
        <p><strong>Você</strong> {message.text}</p>
        {message.reply && <p><strong>Agente</strong> {message.reply}</p>}
        {message.state !== "succeeded" && <p role={message.state === "failed" ? "alert" : "status"}>{message.status}</p>}
        {message.decision ? <small>{message.decision === "accepted" ? "Proposta aceita" : "Proposta descartada"}</small> : message.blocks && !historyId && <>
          {message.stale && <p className="notice">Proposta desatualizada. Peça uma nova com a edição atual.</p>}
          <button type="button" className="text-button" onClick={() => setPreview(preview === message.id ? null : message.id)}>{preview === message.id ? "Fechar prévia" : "Revisar proposta"}</button>
          {preview === message.id && <div className="proposal-review">
            <div className="proposal-pair">
              <figure><figcaption>Cena atual</figcaption><RenderedScene scene={scene} style={project.visual_style || null} accent={project.accent} projectId={project.id} /></figure>
              <figure><figcaption>Proposta do agente</figcaption><RenderedScene scene={{ ...scene, blocks: message.blocks }} style={project.visual_style || null} accent={project.accent} projectId={project.id} /></figure>
            </div>
            <p>{message.blocks.length} blocos · alturas {message.blocks.map(b => `${b.height.toFixed(1)}%`).join(" / ")}. Aceitar aplica o conjunto.</p>
            <div className="block-actions">
              <button type="button" className="button primary" disabled={disabled || busy || message.stale || Boolean(historyId)} onClick={() => void action(async () => {
                const current = await save();
                const result = await request<Project>(`/projects/${project.id}/scene-proposals/${message.id}`, { method: "POST", body: JSON.stringify({ decision: "accepted", revision: current.revision }) });
                onAccepted(result); setPreview(null);
              })}><Check size={15} /> Aceitar proposta</button>
              <button type="button" className="button secondary" disabled={busy || Boolean(historyId)} onClick={() => void action(async () => {
                await request(`/projects/${project.id}/scene-proposals/${message.id}`, { method: "POST", body: JSON.stringify({ decision: "discarded", revision: project.revision }) });
                setPreview(null);
              })}><X size={15} /> Descartar</button>
            </div>
          </div>}
        </>}
      </article>)}
    </div>
    {!historyId && <form onSubmit={e => { e.preventDefault(); void action(async () => {
      const current = await save();
      await request(`/projects/${project.id}/scene-conversations`, { method: "POST", body: JSON.stringify({ ...target, text, revision: current.revision, marked: true, resolved: false }) });
      setText("");
    }); }}>
      <label>Mensagem para o agente<textarea rows={3} maxLength={4000} value={text} disabled={disabled || busy} onChange={e => setText(e.target.value)} placeholder="Por exemplo: deixe este título mais direto, sem mudar o sentido." /></label>
      <div className="block-actions">
        <button className="button primary" disabled={disabled || busy || Boolean(running) || !text.trim()}>{busy ? "Enviando…" : "Enviar ao agente"}</button>
        {running && <button type="button" className="text-button" onClick={() => void action(async () => { await request(`/jobs/${running.id}/cancel`, { method: "POST" }); })}>Cancelar pedido</button>}
      </div>
      <small>Usa o agente de direção visual configurado em Conexões. O pedido continua com a aba fechada.</small>
    </form>}
    {historyId && <p className="block-hint">Histórico somente para consulta. Volte ao alvo atual para enviar um pedido.</p>}
  </section>;
}
