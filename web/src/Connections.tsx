import { useEffect, useState } from "react";
import {
  Check,
  CircleAlert,
  Headphones,
  LoaderCircle,
  Plug,
  Save,
} from "lucide-react";
import { request } from "./api";
import { AgentConnections } from "./AgentConnections";
import type { Health, Integrations, VoiceCatalog } from "./types";

export function Connections({ health }: { health: Health | null }) {
  const [settings, setSettings] = useState<Integrations | null>(null);
  const [agents, setAgents] = useState<Integrations["agents"] | null>(null);
  const [voice, setVoice] = useState<Integrations["elevenlabs"] | null>(null);
  const [catalog, setCatalog] = useState<VoiceCatalog | null>(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let live = true;
    let timer: number;
    const refresh = async () => {
      try {
        const result = await request<Integrations>("/integrations");
        if (live) {
          setSettings(result);
          setAgents((previous) => previous || result.agents);
          setVoice((previous) => previous || result.elevenlabs);
          setPollError("");
        }
      } catch (e) {
        if (live) setPollError((e as Error).message);
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
  const action = async (task: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="connections-page">
      <div className="page-heading">
        <div>
          <h1>Conexões e agentes</h1>
          <p>Escolha quem pesquisa, escreve, cria e dá voz aos seus Shorts.</p>
        </div>
      </div>
      {error && (
        <div className="notice danger" role="alert">
          <CircleAlert size={18} />
          {error}
        </div>
      )}
      {pollError && (
        <div className="notice danger" role="alert">
          <CircleAlert size={18} />
          Não foi possível atualizar as conexões: {pollError}
        </div>
      )}
      {notice && (
        <div className="success-message" role="status">
          <Check size={18} />
          {notice}
        </div>
      )}
      {!settings || !agents || !voice ? (
        <p>Carregando conexões…</p>
      ) : (
        <>
          <section className="connection-section">
            <div className="connection-title">
              <div>
                <h2>
                  <Plug size={21} />
                  Agentes no seu computador
                </h2>
                <p>Usam os CLIs e os logins que você já tem no WSL.</p>
              </div>
              <span
                className={`badge ${settings.runner.online ? "ready" : "draft"}`}
              >
                {settings.runner.online
                  ? "Executor conectado"
                  : "Executor desconectado"}
              </span>
            </div>
            {!settings.runner.online && (
              <div className="runner-instructions">
                <p>
                  Na pasta do MyCut, abra um terminal e mantenha este comando
                  rodando:
                </p>
                <code>bash scripts/agents.sh</code>
                <p>
                  Entre na sua conta em cada CLI escolhido antes de iniciar. O
                  executor conecta os CLIs à fila do Docker.
                </p>
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(async () => {
                  const result = await request<Integrations>(
                    "/integrations/agents",
                    { method: "PUT", body: JSON.stringify(agents) },
                  );
                  setSettings(result);
                  setAgents(result.agents);
                  setNotice("Agentes configurados.");
                });
              }}
            >
              <AgentConnections
                settings={settings}
                agents={agents}
                onChange={setAgents}
                busy={busy}
              />
              <button className="button secondary" disabled={busy}>
                <Save size={16} />
                Salvar agentes
              </button>
            </form>
          </section>
          <section className="connection-section">
            <div className="connection-title">
              <div>
                <h2>
                  <Headphones size={21} />
                  ElevenLabs
                </h2>
                <p>
                  Sua voz selecionada, gerada diretamente no fluxo de produção.
                </p>
              </div>
              <span
                className={`badge ${settings.elevenlabs.connected ? "ready" : "draft"}`}
              >
                {settings.elevenlabs.connected
                  ? "Chave conectada"
                  : "Não conectada"}
              </span>
            </div>
            <form
              className="key-form"
              onSubmit={(e) => {
                e.preventDefault();
                void action(async () => {
                  const result = await request<
                    VoiceCatalog & { settings: Integrations }
                  >("/integrations/elevenlabs/connect", {
                    method: "POST",
                    body: JSON.stringify({ api_key: key }),
                  });
                  setSettings(result.settings);
                  setVoice(result.settings.elevenlabs);
                  setCatalog(result);
                  setKey("");
                  setNotice("Conta conectada. Selecione sua voz e salve.");
                });
              }}
            >
              <label>
                Chave de API da ElevenLabs
                <input
                  type="password"
                  autoComplete="off"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  maxLength={300}
                  placeholder={
                    settings.elevenlabs.connected
                      ? "Digite uma nova chave para trocar a conexão"
                      : "Cole sua chave aqui"
                  }
                />
              </label>
              <button className="button primary" disabled={busy || !key.trim()}>
                {busy ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <Plug size={16} />
                )}
                Conectar ElevenLabs
              </button>
            </form>
            <p className="connection-help">
              Crie uma chave na sua conta com acesso a vozes, modelos e geração
              de fala.{" "}
              <a
                href="https://elevenlabs.io/docs/api-reference/authentication"
                target="_blank"
                rel="noreferrer"
              >
                Como obter a chave
              </a>
              . Ela fica no servidor local e não é exibida novamente.
            </p>
            {settings.elevenlabs.connected && (
              <>
                <div className="connection-actions">
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        setCatalog(
                          await request<VoiceCatalog>(
                            "/integrations/elevenlabs/catalog",
                          ),
                        );
                        setNotice("Vozes e modelos atualizados.");
                      })
                    }
                  >
                    Carregar minhas vozes e modelos
                  </button>
                  <button
                    className="text-button destructive"
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        const result = await request<Integrations>(
                          "/integrations/elevenlabs/disconnect",
                          { method: "POST" },
                        );
                        setSettings(result);
                        setVoice(result.elevenlabs);
                        setCatalog(null);
                        setNotice("ElevenLabs desconectada.");
                      })
                    }
                  >
                    Desconectar
                  </button>
                </div>
                {catalog ? (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      void action(async () => {
                        const { connected: _, ...values } = voice;
                        const result = await request<Integrations>(
                          "/integrations/elevenlabs",
                          { method: "PUT", body: JSON.stringify(values) },
                        );
                        setSettings(result);
                        setVoice(result.elevenlabs);
                        setNotice(
                          "Voz padrão salva para as próximas produções.",
                        );
                      });
                    }}
                  >
                    <fieldset disabled={busy} className="voice-settings">
                      <label>
                        Voz
                        <select
                          required
                          value={voice.voice_id}
                          onChange={(e) =>
                            setVoice({ ...voice, voice_id: e.target.value })
                          }
                        >
                          <option value="">Selecione sua voz</option>
                          {catalog.voices.map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.name}
                              {v.category === "cloned" ? " · clonada" : ""}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Modelo de voz
                        <select
                          required
                          value={voice.model_id}
                          onChange={(e) =>
                            setVoice({ ...voice, model_id: e.target.value })
                          }
                        >
                          {catalog.models.map((m) => (
                            <option value={m.id} key={m.id}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Estabilidade ({Math.round(voice.stability * 100)}%)
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={voice.stability}
                          onChange={(e) =>
                            setVoice({
                              ...voice,
                              stability: Number(e.target.value),
                            })
                          }
                        />
                      </label>
                      <label>
                        Semelhança ({Math.round(voice.similarity_boost * 100)}%)
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={voice.similarity_boost}
                          onChange={(e) =>
                            setVoice({
                              ...voice,
                              similarity_boost: Number(e.target.value),
                            })
                          }
                        />
                      </label>
                      <label>
                        Velocidade ({voice.speed.toFixed(2)}×)
                        <input
                          type="range"
                          min={0.7}
                          max={1.2}
                          step={0.05}
                          value={voice.speed}
                          onChange={(e) =>
                            setVoice({
                              ...voice,
                              speed: Number(e.target.value),
                            })
                          }
                        />
                      </label>
                    </fieldset>
                    <button
                      className="button secondary"
                      disabled={busy || !voice.voice_id}
                    >
                      <Save size={16} />
                      Salvar voz
                    </button>
                  </form>
                ) : (
                  settings.elevenlabs.voice_id && (
                    <p className="selected-voice">
                      Voz atual:{" "}
                      <strong>{settings.elevenlabs.voice_name}</strong> ·{" "}
                      {settings.elevenlabs.model_id}
                    </p>
                  )
                )}
              </>
            )}
            <p className="connection-help">
              Conectar e listar vozes não gera áudio. Produzir a narração usa os
              créditos da sua conta ElevenLabs. A geração usa o roteiro completo
              para preservar a continuidade da fala.
            </p>
          </section>
          <section className="connection-section">
            <h2>Produção</h2>
            <p>
              API {health ? "conectada" : "desconectada"} · Worker{" "}
              {health?.worker_online ? "conectado" : "desconectado"} · FFmpeg{" "}
              {health?.ffmpeg ? "disponível" : "indisponível"}.
            </p>
            <p className="connection-help">
              O envio ao YouTube e o agendamento diário ainda não estão
              conectados. O resultado desta produção fica disponível para
              revisão e download.
            </p>
          </section>
        </>
      )}
    </section>
  );
}
