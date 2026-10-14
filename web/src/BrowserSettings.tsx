import { useState } from "react";
import { Check, CircleAlert, Globe, LoaderCircle, Save } from "lucide-react";
import { request } from "./api";
import type { BrowserSettings as Settings, Integrations } from "./types";

export function BrowserSettings({
  settings,
  draft,
  onChange,
  onSaved,
  busy,
}: {
  settings: Integrations;
  draft: Settings;
  onChange: (draft: Settings) => void;
  onSaved: (settings: Integrations) => void;
  busy: boolean;
}) {
  const [pending, setPending] = useState(false);
  const [testId, setTestId] = useState("");
  const [error, setError] = useState("");
  const { runner, browser_test: result } = settings;
  const saved = settings.browser;
  const changed =
    draft.enabled !== saved.enabled ||
    draft.chrome_path.trim() !== saved.chrome_path ||
    draft.port !== saved.port;
  const waiting = !!testId && result?.id !== testId;
  const perform = async (task: () => Promise<void>) => {
    setPending(true);
    setError("");
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  };
  const state = !runner.online
    ? "Executor desconectado."
    : !saved.enabled
      ? "Desativado. A pesquisa usa só a busca e a leitura dos próprios CLIs."
      : runner.protocol < 3
        ? "Reinicie bash scripts/agents.sh no WSL para habilitar o navegador."
        : runner.browser.available
          ? `Chrome conectado · ${runner.browser.version}`
          : "Fechado. O executor abre o Chrome quando a pesquisa precisar.";
  return (
    <form
      className="browser-form"
      onSubmit={(e) => {
        e.preventDefault();
        void perform(async () => {
          onSaved(
            await request<Integrations>("/integrations/browser", {
              method: "PUT",
              body: JSON.stringify({
                ...draft,
                chrome_path: draft.chrome_path.trim(),
              }),
            }),
          );
        });
      }}
    >
      <div className="cli-commands-heading">
        <h3>
          <Globe size={16} />
          Navegador para pesquisa
        </h3>
        <p>
          Quando um site bloqueia a leitura automática, a pesquisa abre a página
          no Chrome do Windows, como uma pessoa. O Chrome usa um perfil separado
          do MyCut, sem os seus logins. Os agentes só navegam, clicam e leem:
          não preenchem formulários nem executam scripts.
        </p>
        <p role="status" className="browser-state">
          {state}
        </p>
      </div>
      <fieldset disabled={busy || pending} className="browser-settings">
        <label className="browser-toggle">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(e) => onChange({ ...draft, enabled: e.target.checked })}
          />
          Usar o navegador na pesquisa
        </label>
        <label>
          Caminho do chrome.exe
          <input
            value={draft.chrome_path}
            maxLength={500}
            spellCheck={false}
            autoComplete="off"
            placeholder="Detectar automaticamente (Chrome Canary ou Chrome)"
            onChange={(e) =>
              onChange({ ...draft, chrome_path: e.target.value })
            }
          />
        </label>
        <label>
          Porta de depuração
          <input
            type="number"
            min={1024}
            max={65535}
            required
            value={draft.port}
            onChange={(e) =>
              onChange({ ...draft, port: Number(e.target.value) })
            }
          />
        </label>
      </fieldset>
      {error && (
        <p className="notice danger" role="alert">
          {error}
        </p>
      )}
      {(waiting || result) && (
        <div
          className={`agent-test-result ${!waiting && result?.error ? "test-warning" : ""}`}
          role="status"
          aria-live="polite"
        >
          <strong>
            {waiting ? (
              <LoaderCircle size={16} className="spin" />
            ) : result?.error ? (
              <CircleAlert size={16} />
            ) : (
              <Check size={16} />
            )}
            {waiting
              ? "Abrindo o Chrome e conectando…"
              : result?.error
                ? "O navegador não conectou"
                : "Navegador pronto para a pesquisa"}
          </strong>
          {!waiting && result && (
            <p>
              {result.error || result.version} ·{" "}
              {new Date(result.checked_at * 1000).toLocaleString("pt-BR")}
            </p>
          )}
        </div>
      )}
      <div className="browser-actions">
        <button className="button secondary" disabled={busy || pending}>
          <Save size={16} />
          Salvar navegador
        </button>
        <button
          type="button"
          className="button secondary"
          disabled={
            busy ||
            pending ||
            waiting ||
            changed ||
            !saved.enabled ||
            !runner.online ||
            runner.protocol < 3
          }
          title={changed ? "Salve antes de testar." : undefined}
          onClick={() =>
            void perform(async () => {
              const started = await request<{ id: string }>(
                "/integrations/browser/test",
                { method: "POST" },
              );
              setTestId(started.id);
            })
          }
        >
          <Globe size={16} />
          Abrir e testar
        </button>
        {changed && (
          <span className="cli-command-help">Alteração não salva.</span>
        )}
      </div>
    </form>
  );
}
