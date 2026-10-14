import { useEffect, useRef, useState } from "react";
import { CircleAlert, LoaderCircle, Play } from "lucide-react";
import { request } from "./api";
import type { Integrations, VoiceCatalog, VoiceTest } from "./types";
import "./VoiceSamples.css";

function pauseOtherAudio(current: HTMLAudioElement) {
  document.querySelectorAll("audio").forEach((audio) => {
    if (audio !== current) audio.pause();
  });
}

export function VoicePreview({
  voice,
}: {
  voice?: VoiceCatalog["voices"][number];
}) {
  const audio = useRef<HTMLAudioElement>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  if (!voice) return null;
  return (
    <div className="voice-preview">
      <button
        type="button"
        className="button secondary"
        disabled={!voice.preview_url || loading}
        onClick={async () => {
          setError("");
          setLoading(true);
          try {
            await audio.current?.play();
          } catch {
            setError(
              "Não foi possível reproduzir a amostra. Atualize a lista de vozes e tente novamente.",
            );
          } finally {
            setLoading(false);
          }
        }}
      >
        {loading ? (
          <LoaderCircle size={16} className="spin" />
        ) : (
          <Play size={16} />
        )}
        {loading ? "Carregando amostra…" : "Ouvir amostra · grátis"}
      </button>
      <p>
        {voice.preview_url
          ? "Áudio pronto da voz. Não aplica o modelo e os ajustes selecionados."
          : "Esta voz não tem uma amostra pronta disponível. Nenhum áudio será gerado ao selecionar a voz."}
      </p>
      {voice.preview_url && (
        <audio
          ref={audio}
          controls
          preload="none"
          src={voice.preview_url}
          aria-label={`Amostra gratuita de ${voice.name}`}
          onPlay={(event) => pauseOtherAudio(event.currentTarget)}
          onError={() => {
            setLoading(false);
            setError(
              "A amostra está indisponível. Atualize a lista de vozes e tente novamente.",
            );
          }}
        />
      )}
      {error && (
        <p className="voice-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function VoiceTests({
  voice,
  catalog,
  disabled,
}: {
  voice: Integrations["elevenlabs"];
  catalog: VoiceCatalog;
  disabled: boolean;
}) {
  const [text, setText] = useState(
    "Você fecha o notebook e a inteligência artificial continua trabalhando. Depois, é só revisar o resultado.",
  );
  const [results, setResults] = useState<VoiceTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const inFlight = useRef(false);
  const historyVersion = useRef(0);
  useEffect(() => {
    let live = true;
    const version = historyVersion.current;
    request<VoiceTest[]>("/integrations/elevenlabs/tests")
      .then((items) => {
        if (live && version === historyVersion.current) setResults(items);
      })
      .catch(() => {
        if (live)
          setError(
            "Não foi possível carregar os testes salvos. Recarregue a página para tentar novamente.",
          );
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, []);
  const choice = catalog.voices.find((v) => v.id === voice.voice_id);
  const model = catalog.models.find((m) => m.id === voice.model_id);
  const characters = Array.from(text.trim()).length;

  async function generate() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    historyVersion.current++;
    try {
      const result = await request<VoiceTest>(
        "/integrations/elevenlabs/tests",
        {
          method: "POST",
          body: JSON.stringify({
            text: text.trim(),
            settings: {
              voice_id: voice.voice_id,
              model_id: voice.model_id,
              stability: voice.stability,
              similarity_boost: voice.similarity_boost,
              speed: voice.speed,
            },
          }),
        },
      );
      setResults((previous) =>
        [result, ...previous.filter((item) => item.id !== result.id)].slice(
          0,
          5,
        ),
      );
      setNotice(
        result.cached
          ? "Teste já salvo. Áudio reutilizado sem uma nova geração."
          : "Teste gerado e salvo. Você pode reouvir sem gastar novos créditos.",
      );
    } catch (e) {
      setError(
        `${(e as Error).message} Não repetimos a geração automaticamente. Se a ElevenLabs chegou a processá-la, pode haver consumo de créditos.`,
      );
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <section className="voice-tests" aria-labelledby="voice-tests-title">
      <h3 id="voice-tests-title">Testar com meu texto</h3>
      <p>
        Usa a voz, o modelo e os ajustes selecionados acima, mesmo antes de
        salvar a voz padrão.
      </p>
      <label htmlFor="voice-test-text">Texto do teste</label>
      <textarea
        id="voice-test-text"
        value={text}
        disabled={busy}
        rows={3}
        maxLength={300}
        onChange={(event) => setText(event.target.value)}
        aria-describedby="voice-test-cost"
      />
      <p id="voice-test-cost">
        <strong>{characters}/300 caracteres.</strong> Gerar uma fala nova
        consome créditos da ElevenLabs. O valor depende do modelo, da voz e do
        seu plano. Reouvir um teste salvo é grátis.
      </p>
      <div className="voice-test-action">
        <button
          type="button"
          className="button primary"
          disabled={
            disabled ||
            loading ||
            busy ||
            !choice ||
            !model ||
            !characters ||
            characters > 300
          }
          onClick={() => void generate()}
        >
          {busy ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <Play size={16} />
          )}
          {busy ? "Gerando teste…" : "Gerar teste (usa créditos)"}
        </button>
        <p>
          {choice && model
            ? `${choice.name} · ${model.name}`
            : "Selecione uma voz e um modelo acima."}
        </p>
      </div>
      <p>
        Texto, voz e ajustes iguais reutilizam o áudio já salvo nesta conexão,
        sem outra geração.
      </p>
      {notice && (
        <p className="success-message" role="status">
          {notice}
        </p>
      )}
      {error && (
        <div className="notice danger" role="alert">
          <CircleAlert size={18} />
          {error}
        </div>
      )}
      {loading && <p role="status">Carregando testes salvos…</p>}
      {results.length > 0 && (
        <div className="voice-test-results" aria-label="Testes salvos">
          <h3>Últimos testes salvos</h3>
          <p>
            Áudios das configurações indicadas em cada teste. Reproduzir não
            gera outra fala.
          </p>
          {results.map((result) => (
            <article key={result.id}>
              <strong>
                {result.voice_name} · {result.model_name}
              </strong>
              <p>
                {new Date(result.created_at * 1000).toLocaleString("pt-BR")} ·
                Velocidade {result.settings.speed.toFixed(2)}× · Estabilidade{" "}
                {Math.round(result.settings.stability * 100)}% · Semelhança{" "}
                {Math.round(result.settings.similarity_boost * 100)}%
              </p>
              <p className="voice-test-quote">{result.text}</p>
              <audio
                controls
                preload="none"
                src={result.url}
                aria-label={`Teste salvo de ${result.voice_name} com ${result.model_name}`}
                onPlay={(event) => pauseOtherAudio(event.currentTarget)}
                onError={() =>
                  setError(
                    "Não foi possível carregar um teste salvo. Recarregue a página para verificar sua conexão.",
                  )
                }
              />
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
