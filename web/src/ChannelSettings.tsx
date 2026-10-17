import { useEffect, useState } from "react";
import { LoaderCircle, Pencil, Plus, Save, Tv } from "lucide-react";
import { request } from "./api";
import type { Channel, ChannelVoice, Integrations, VoiceCatalog } from "./types";
import "./ChannelSettings.css";

type Draft = { id: string | null; name: string; brand: string; voice: ChannelVoice | null };
const blank: Draft = { id: null, name: "", brand: "MYCUT", voice: null };

export function useChannels() {
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    request<Channel[]>("/channels")
      .then((result) => live && setChannels(result))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, []);
  return { channels, setChannels, error };
}

/** Name, brand and voice every new production inherits from its channel (ADR 0018). */
export function ChannelSettings({ settings }: { settings: Integrations }) {
  const { channels, setChannels, error: loadError } = useChannels();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [catalog, setCatalog] = useState<VoiceCatalog | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const connected = settings.elevenlabs.connected;
  useEffect(() => {
    if (!draft || !connected || catalog) return;
    let live = true;
    request<VoiceCatalog>("/integrations/elevenlabs/catalog")
      .then((result) => live && setCatalog(result))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [draft, connected, catalog]);
  const fallback = settings.elevenlabs.voice_name
    ? `Voz das Conexões (${settings.elevenlabs.voice_name})`
    : "Voz das Conexões";
  const chooseVoice = (voiceId: string) => {
    if (!draft) return;
    if (!voiceId) return setDraft({ ...draft, voice: null });
    // A new choice starts from the narration settings tuned in Vozes.
    const { connected: _, ...tuned } = settings.elevenlabs;
    const base = draft.voice ?? tuned;
    const name = catalog?.voices.find((v) => v.id === voiceId)?.name ?? "";
    setDraft({ ...draft, voice: { ...base, voice_id: voiceId, voice_name: name } });
  };
  const voices = catalog?.voices ?? [];
  const current = draft?.voice;
  // A saved voice the account no longer offers stays visible until another is chosen.
  const missing = !!catalog && !!current && !voices.some((v) => v.id === current.voice_id);
  return (
    <section className="connection-section channel-settings">
      <div className="connection-title">
        <div>
          <h2>
            <Tv size={21} />
            Seus canais
          </h2>
          <p>
            Cada produção pertence a um canal. Uma produção nova copia a marca
            e a voz do canal e as mantém em todas as versões. Mudar um canal
            vale para as próximas produções.
          </p>
        </div>
        {!draft && (
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setNotice("");
              setDraft(blank);
            }}
          >
            <Plus size={16} />
            Novo canal
          </button>
        )}
      </div>
      {(error || loadError) && (
        <div className="notice danger" role="alert">
          {error || loadError}
        </div>
      )}
      {notice && (
        <p className="success-message" role="status">
          {notice}
        </p>
      )}
      {draft && (
        <form
          className="channel-form"
          aria-label={draft.id ? "Editar canal" : "Novo canal"}
          onSubmit={(e) => {
            e.preventDefault();
            setPending(true);
            setError("");
            request<Channel>(draft.id ? `/channels/${draft.id}` : "/channels", {
              method: draft.id ? "PUT" : "POST",
              body: JSON.stringify({ name: draft.name, brand: draft.brand, voice: draft.voice }),
            })
              .then((saved) => {
                setChannels((list) =>
                  draft.id
                    ? (list ?? []).map((item) => (item.id === saved.id ? saved : item))
                    : [...(list ?? []), saved],
                );
                setNotice(draft.id ? `Canal ${saved.name} salvo.` : `Canal ${saved.name} criado.`);
                setDraft(null);
              })
              .catch((e: Error) => setError(e.message))
              .finally(() => setPending(false));
          }}
        >
          <fieldset disabled={pending}>
            <label>
              Nome do canal
              <input
                autoFocus
                required
                maxLength={60}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="Ex.: Histórias dark"
              />
            </label>
            <label>
              Marca do canal
              <input
                maxLength={40}
                value={draft.brand}
                onChange={(e) => setDraft({ ...draft, brand: e.target.value })}
                placeholder="Nome ou @ do canal"
                aria-describedby="channel-brand-hint"
              />
              <small id="channel-brand-hint">
                Texto no topo das cenas e nas capas das novas produções. Deixe
                vazio para ocultar.
              </small>
            </label>
            <label>
              Voz da narração
              <select
                value={current?.voice_id ?? ""}
                onChange={(e) => chooseVoice(e.target.value)}
                disabled={!connected && !current}
                aria-invalid={missing || undefined}
              >
                <option value="">{fallback}</option>
                {current && !voices.some((v) => v.id === current.voice_id) && (
                  <option value={current.voice_id} disabled={missing}>
                    {current.voice_name || current.voice_id}
                    {missing && " · selecione novamente"}
                  </option>
                )}
                {voices.map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.name}
                  </option>
                ))}
              </select>
              <small>
                {connected
                  ? "Ajustes de modelo, estabilidade e velocidade vêm de Vozes."
                  : "Conecte a ElevenLabs em Vozes para escolher outra voz."}
              </small>
            </label>
          </fieldset>
          <div className="channel-form-actions">
            <button className="button primary" disabled={pending || !draft.name.trim()}>
              {pending ? <LoaderCircle size={16} className="spin" /> : <Save size={16} />}
              {draft.id ? "Salvar canal" : "Criar canal"}
            </button>
            <button
              type="button"
              className="text-button"
              disabled={pending}
              onClick={() => {
                setError("");
                setDraft(null);
              }}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}
      {!channels ? (
        !loadError && <p role="status">Carregando canais…</p>
      ) : (
        <ul className="channel-list" aria-label="Canais">
          {channels.map((channel) => (
            <li key={channel.id}>
              <div>
                <strong>
                  <span>{channel.name}</span>
                  {channel.default && <small className="channel-default">Padrão</small>}
                </strong>
                <small>
                  Marca: {channel.brand || "oculta"} · Voz:{" "}
                  {channel.voice?.voice_name || fallback}
                </small>
              </div>
              <button
                type="button"
                className="text-button"
                aria-label={`Editar ${channel.name}`}
                disabled={pending}
                onClick={() => {
                  setNotice("");
                  setError("");
                  setDraft({ id: channel.id, name: channel.name, brand: channel.brand, voice: channel.voice });
                }}
              >
                <Pencil size={15} />
                Editar
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
