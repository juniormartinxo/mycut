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
import { SettingsMenu, settingsSections } from "./SettingsMenu";
import type { SettingsSection } from "./navigation";
import { AgentConnections } from "./AgentConnections";
import { BrowserSettings } from "./BrowserSettings";
import { CliCommands } from "./CliCommands";
import { PricingSettings } from "./PricingSettings";
import { VoicePreview, VoiceTests } from "./VoiceSamples";
import {
  languageName,
  matchesLanguage,
  savedVoiceLanguage,
  saveVoiceLanguage,
  voiceDescription,
} from "./voiceLanguages";
import type { Health, Integrations, VoiceCatalog } from "./types";

export function Connections({
  health,
  section,
  onNavigate,
}: {
  health: Health | null;
  section: SettingsSection;
  onNavigate: (section: SettingsSection) => void;
}) {
  const currentSection = settingsSections.find((item) => item.id === section)!;
  const [settings, setSettings] = useState<Integrations | null>(null);
  const [agents, setAgents] = useState<Integrations["agents"] | null>(null);
  const [commands, setCommands] = useState<Integrations["commands"] | null>(
    null,
  );
  const [browser, setBrowser] = useState<Integrations["browser"] | null>(null);
  const [voice, setVoice] = useState<Integrations["elevenlabs"] | null>(null);
  const [catalog, setCatalog] = useState<VoiceCatalog | null>(null);
  const [voiceSession, setVoiceSession] = useState(0);
  const [voiceLanguage, setVoiceLanguage] = useState(savedVoiceLanguage);
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
          setCommands((previous) => previous || result.commands);
          setBrowser((previous) => previous || result.browser);
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
  const connected = settings?.elevenlabs.connected ?? false;
  useEffect(() => {
    if (section !== "voices" || !connected || catalog) return;
    let live = true;
    request<VoiceCatalog>("/integrations/elevenlabs/catalog")
      .then((result) => {
        if (live) setCatalog(result);
      })
      .catch((e: Error) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [connected, catalog, section]);
  useEffect(() => {
    setError("");
    setNotice("");
  }, [section]);
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
  const visibleVoices =
    catalog?.voices.filter((v) => matchesLanguage(v, voiceLanguage)) || [];
  const selectedVoice = visibleVoices.find((v) => v.id === voice?.voice_id);
  const languageCodes = Array.from(
    new Set([
      "pt",
      ...(catalog?.voices.flatMap((v) => (v.language ? [v.language] : [])) ||
        []),
      ...(!["all", "unknown"].includes(voiceLanguage) ? [voiceLanguage] : []),
    ]),
  ).sort((a, b) => languageName(a).localeCompare(languageName(b), "pt-BR"));
  return (
    <section className="connections-page settings-page">
      <div className="page-heading">
        <div>
          <span className="settings-eyebrow">Configurações</span>
          <h1>{currentSection.label}</h1>
          <p>{currentSection.description}</p>
        </div>
      </div>
      <SettingsMenu
        placement="page"
        section={section}
        onNavigate={onNavigate}
      />
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
      {!settings || !agents || !commands || !browser || !voice ? (
        <p role="status">Carregando configurações…</p>
      ) : (
        <>
          {section === "agents" && (
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
          )}
          {section === "voices" && (
            <section className="connection-section">
              <div className="connection-title">
                <div>
                  <h2>
                    <Headphones size={21} />
                    ElevenLabs
                  </h2>
                  <p>
                    Sua voz selecionada, gerada diretamente no fluxo de
                    produção.
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
              <details className="elevenlabs-connection" open={!connected}>
                <summary>
                  {connected ? "Gerenciar conexão" : "Conectar conta"}
                </summary>
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
                      setVoiceSession((previous) => previous + 1);
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
                  <button
                    className="button primary"
                    disabled={busy || !key.trim()}
                  >
                    {busy ? (
                      <LoaderCircle className="spin" size={16} />
                    ) : (
                      <Plug size={16} />
                    )}
                    Conectar ElevenLabs
                  </button>
                </form>
                <p className="connection-help">
                  Crie uma chave na sua conta com acesso a vozes, modelos e
                  geração de fala.{" "}
                  <a
                    href="https://elevenlabs.io/docs/api-reference/authentication"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Como obter a chave
                  </a>
                  . Ela fica no servidor local e não é exibida novamente.
                </p>
                {connected && (
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
                )}
              </details>
              {settings.elevenlabs.connected && (
                <>
                  <div className="connection-actions voice-catalog-actions">
                    <h3>Voz da narração</h3>
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
                      Atualizar vozes e modelos
                    </button>
                  </div>
                  {catalog ? (
                    <>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          void action(async () => {
                            if (!selectedVoice)
                              throw new Error(
                                "Selecione uma voz disponível no idioma escolhido.",
                              );
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
                        <fieldset disabled={busy} className="voice-selectors">
                          <label htmlFor="voice-language">
                            Idioma da voz
                            <select
                              id="voice-language"
                              value={voiceLanguage}
                              disabled={busy}
                              aria-describedby="voice-language-help"
                              onChange={(e) => {
                                const language = e.target.value;
                                setVoiceLanguage(language);
                                saveVoiceLanguage(language);
                                if (
                                  !catalog.voices.some(
                                    (v) =>
                                      v.id === voice.voice_id &&
                                      matchesLanguage(v, language),
                                  )
                                ) {
                                  setVoice({
                                    ...voice,
                                    voice_id: "",
                                    voice_name: "",
                                  });
                                }
                              }}
                            >
                              {languageCodes.map((code) => (
                                <option key={code} value={code}>
                                  {languageName(code)} (
                                  {
                                    catalog.voices.filter(
                                      (v) => v.language === code,
                                    ).length
                                  }
                                  )
                                </option>
                              ))}
                              <option value="all">
                                Todos os idiomas ({catalog.voices.length})
                              </option>
                              <option value="unknown">
                                Idioma não informado (
                                {
                                  catalog.voices.filter((v) => !v.language)
                                    .length
                                }
                                )
                              </option>
                            </select>
                          </label>
                          <label>
                            Voz
                            <select
                              required
                              disabled={!visibleVoices.length}
                              value={voice.voice_id}
                              onChange={(e) =>
                                setVoice({ ...voice, voice_id: e.target.value })
                              }
                            >
                              <option value="">Selecione sua voz</option>
                              {voice.voice_id && !selectedVoice && (
                                <option value={voice.voice_id} disabled>
                                  {catalog.voices.find(
                                    (v) => v.id === voice.voice_id,
                                  )?.name ||
                                    voice.voice_name ||
                                    "Voz atual"}{" "}
                                  · fora deste filtro
                                </option>
                              )}
                              {visibleVoices.map((v) => (
                                <option key={v.id} value={v.id}>
                                  {voiceDescription(v)}
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
                        </fieldset>
                        <div className="voice-filter-help">
                          <p id="voice-language-help">
                            Filtra pelo idioma cadastrado da voz. Não altera a
                            língua do texto nem a voz padrão salva.
                          </p>
                          {visibleVoices.length === 0 && (
                            <p role="status">
                              Nenhuma voz neste idioma. Escolha outro idioma ou
                              veja Todos os idiomas.
                            </p>
                          )}
                          {voice.voice_id && !selectedVoice && (
                            <p role="status">
                              A voz atual está fora deste filtro. Escolha uma
                              voz da lista ou mude o idioma.
                            </p>
                          )}
                        </div>
                        <VoicePreview
                          key={
                            voice.voice_id + (selectedVoice?.preview_url || "")
                          }
                          voice={selectedVoice}
                        />
                        <fieldset
                          disabled={busy}
                          className="voice-settings voice-tuning"
                        >
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
                            Semelhança (
                            {Math.round(voice.similarity_boost * 100)}
                            %)
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
                          disabled={busy || !selectedVoice}
                        >
                          <Save size={16} />
                          Salvar voz
                        </button>
                      </form>
                      <VoiceTests
                        key={voiceSession}
                        voice={voice}
                        catalog={{ ...catalog, voices: visibleVoices }}
                        disabled={busy}
                      />
                    </>
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
                Conectar e listar vozes não gera áudio. Produzir a narração usa
                os créditos da sua conta ElevenLabs. A geração usa o roteiro
                completo para preservar a continuidade da fala.
              </p>
            </section>
          )}
          {section === "costs" && (
            <section className="connection-section">
              <PricingSettings
                settings={settings}
                busy={busy}
                onSaved={(result) => {
                  setSettings(result);
                  setNotice(
                    "Preços salvos. Os custos dos projetos foram recalculados.",
                  );
                }}
              />
            </section>
          )}
          {section === "environment" && (
            <>
              <section className="connection-section environment-tools">
                <form
                  className="cli-commands-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void action(async () => {
                      const result = await request<Integrations>(
                        "/integrations/commands",
                        { method: "PUT", body: JSON.stringify(commands) },
                      );
                      setSettings(result);
                      setCommands(result.commands);
                      setNotice(
                        "Comandos salvos. O executor passa a usá-los na próxima chamada e atualiza a lista de modelos.",
                      );
                    });
                  }}
                >
                  <CliCommands
                    settings={settings}
                    commands={commands}
                    onChange={setCommands}
                    busy={busy}
                  />
                  <button className="button secondary" disabled={busy}>
                    <Save size={16} />
                    Salvar comandos
                  </button>
                </form>
                <BrowserSettings
                  settings={settings}
                  draft={browser}
                  onChange={setBrowser}
                  onSaved={(result) => {
                    setSettings(result);
                    setBrowser(result.browser);
                    setNotice("Navegador salvo.");
                  }}
                  busy={busy}
                />
              </section>
              <section className="connection-section">
                <h2>Serviços de produção</h2>
                <p>
                  API {health ? "conectada" : "desconectada"} · Worker{" "}
                  {health?.worker_online ? "conectado" : "desconectado"} ·
                  FFmpeg {health?.ffmpeg ? "disponível" : "indisponível"}.
                </p>
                <p className="connection-help">
                  O envio ao YouTube e o agendamento diário ainda não estão
                  conectados. O resultado desta produção fica disponível para
                  revisão e download.
                </p>
              </section>
            </>
          )}
        </>
      )}
    </section>
  );
}
