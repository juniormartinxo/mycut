import { useEffect, useState } from "react";
import {
  Check,
  CircleAlert,
  LoaderCircle,
  Play,
  RefreshCw,
} from "lucide-react";
import { request } from "./api";
import type { AgentChoice, AgentRole, AgentTest, Integrations } from "./types";

const roles: { id: AgentRole; title: string; detail: string }[] = [
  {
    id: "research",
    title: "Pesquisa",
    detail: "Abre fontes e reúne os fatos da pauta.",
  },
  {
    id: "writer",
    title: "Roteiro",
    detail: "Transforma os fatos em uma história para narrar.",
  },
  {
    id: "director",
    title: "Direção visual e capa",
    detail: "Planeja as animações, diagramas e a thumbnail.",
  },
  {
    id: "reviewer",
    title: "Conferência",
    detail: "Confere afirmações e pede correções antes da voz.",
  },
];
const active = (test?: AgentTest) =>
  test && ["queued", "running", "cancelling"].includes(test.state);
const labels = { codex: "Codex", claude: "Claude Code", grok: "Grok" };

export function AgentConnections({
  settings,
  agents,
  onChange,
  busy,
}: {
  settings: Integrations;
  agents: Integrations["agents"];
  onChange: (agents: Integrations["agents"]) => void;
  busy: boolean;
}) {
  const [tests, setTests] = useState<Partial<Record<AgentRole, AgentTest>>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let live = true;
    let timer: number;
    const refresh = async () => {
      try {
        const result = await request<Partial<Record<AgentRole, AgentTest>>>(
          "/integrations/agents/tests",
        );
        if (live) {
          setTests((previous) => {
            const next = { ...previous };
            for (const role of roles) {
              const incoming = result[role.id];
              const current = previous[role.id];
              // A poll started before POST must not erase a newer test.
              if (
                incoming &&
                (!current ||
                  incoming.created_at > current.created_at ||
                  (incoming.id === current.id &&
                    active(current) &&
                    !(
                      current.state === "cancelling" &&
                      ["queued", "running"].includes(incoming.state)
                    )))
              )
                next[role.id] = incoming;
            }
            return next;
          });
          setPollError("");
        }
      } catch (e) {
        if (live)
          setPollError(
            `Não foi possível atualizar os testes: ${(e as Error).message}`,
          );
      } finally {
        if (live) timer = window.setTimeout(refresh, 2000);
      }
    };
    void refresh();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, []);

  const perform = async (task: () => Promise<void>) => {
    setPending(true);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  };
  const testing = Object.values(tests).some(active);
  const available = settings.runner.online && settings.runner.protocol >= 2;

  return (
    <>
      <div className="agent-catalog-actions">
        <p>
          Escolha o modelo e teste antes de salvar. Cada teste faz uma
          solicitação curta e usa a cota do CLI; não gera áudio nem vídeo.
        </p>
        <button
          type="button"
          className="button secondary"
          disabled={pending || !available}
          onClick={() =>
            void perform(async () => {
              const result = await request<{ message: string }>(
                "/integrations/agents/models/refresh",
                { method: "POST" },
              );
              setNotice(result.message);
            })
          }
        >
          <RefreshCw size={15} />
          Atualizar modelos
        </button>
      </div>
      {settings.runner.online && settings.runner.protocol < 2 && (
        <p className="runner-instructions">
          Reinicie <code>bash scripts/agents.sh</code> no WSL para carregar os
          modelos e habilitar os testes.
        </p>
      )}
      {error && (
        <p className="notice danger" role="alert">
          {error}
        </p>
      )}
      {pollError && (
        <p className="notice danger" role="alert">
          {pollError}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {roles.map((role) => {
        const choice = agents[role.id];
        const catalog = settings.agent_models[choice.provider];
        const valid =
          !choice.model || catalog.models.some((m) => m.id === choice.model);
        const test = tests[role.id];
        const same =
          test?.provider === choice.provider && test?.model === choice.model;
        const running = active(test);
        const change = (next: AgentChoice) =>
          onChange({ ...agents, [role.id]: next });
        return (
          <div className="agent-setting" key={role.id}>
            <div className="agent-role">
              <h3>{role.title}</h3>
              <p>{role.detail}</p>
            </div>
            <label>
              CLI
              <select
                aria-label={`CLI de ${role.title}`}
                value={choice.provider}
                disabled={busy || !!running}
                onChange={(e) =>
                  change({
                    provider: e.target.value as AgentChoice["provider"],
                    model: "",
                  })
                }
              >
                {(["codex", "claude", "grok"] as const).map((provider) => (
                  <option value={provider} key={provider}>
                    {labels[provider]}
                    {settings.runner.online &&
                    !settings.runner.providers[provider]
                      ? " · não encontrado"
                      : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Modelo
              <select
                aria-label={`Modelo de ${role.title}`}
                value={choice.model}
                disabled={busy || !!running}
                aria-invalid={!valid}
                aria-describedby={`model-help-${role.id}`}
                onChange={(e) => change({ ...choice, model: e.target.value })}
              >
                <option value="">Padrão do CLI</option>
                {!valid && (
                  <option value={choice.model} disabled>
                    {choice.model} · selecione novamente
                  </option>
                )}
                {catalog.models.map((model) => (
                  <option value={model.id} key={model.id}>
                    {model.name} · {model.id}
                  </option>
                ))}
              </select>
            </label>
            <div className="agent-test-area">
              <div className="agent-test-actions">
                <div id={`model-help-${role.id}`} className="agent-model-help">
                  {!valid ? (
                    <p>
                      Esse nome não corresponde a um modelo da lista. Selecione
                      novamente.
                    </p>
                  ) : (
                    <p>
                      {choice.model
                        ? `ID selecionado: ${choice.model}`
                        : "O CLI escolhe o modelo padrão. Selecione um ID para fixar o modelo."}
                    </p>
                  )}
                  <p>
                    {catalog.error ||
                      (!catalog.models.length
                        ? "Lista ainda não carregada. Inicie o executor no WSL."
                        : `${catalog.source === "cache" ? "Lista do cache local" : "Lista informada pelo CLI"} · consultada às ${new Date(catalog.checked_at! * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}. O teste verifica o acesso.`)}
                  </p>
                </div>
                {running ? (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={pending || test?.state === "cancelling"}
                    aria-label={`Cancelar teste de ${role.title}`}
                    onClick={() =>
                      void perform(async () => {
                        const result = await request<AgentTest>(
                          `/integrations/agents/tests/${test!.id}/cancel`,
                          { method: "POST" },
                        );
                        setTests((previous) => ({
                          ...previous,
                          [role.id]: result,
                        }));
                      })
                    }
                  >
                    Cancelar teste
                  </button>
                ) : (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={
                      busy ||
                      pending ||
                      testing ||
                      !available ||
                      !settings.runner.providers[choice.provider] ||
                      !valid
                    }
                    aria-label={`Testar agente de ${role.title}`}
                    onClick={() =>
                      void perform(async () => {
                        const result = await request<AgentTest>(
                          "/integrations/agents/tests",
                          {
                            method: "POST",
                            body: JSON.stringify({ ...choice, role: role.id }),
                          },
                        );
                        setTests((previous) => ({
                          ...previous,
                          [role.id]: result,
                        }));
                      })
                    }
                  >
                    <Play size={15} />
                    Testar agente
                  </button>
                )}
              </div>
              {test && (
                <div
                  className={`agent-test-result ${test.state === "failed" || test.verification === "mismatch" ? "test-warning" : ""}`}
                  role="status"
                  aria-live="polite"
                >
                  <strong>
                    {running ? (
                      <LoaderCircle size={16} className="spin" />
                    ) : test.state === "succeeded" &&
                      test.verification !== "mismatch" ? (
                      <Check size={16} />
                    ) : (
                      <CircleAlert size={16} />
                    )}
                    {test.state === "queued"
                      ? "Na fila do executor…"
                      : test.state === "running"
                        ? "Aguardando resposta do CLI…"
                        : test.state === "cancelling"
                          ? "Cancelando teste…"
                          : test.state === "succeeded"
                            ? test.verification === "match"
                              ? "Respondeu · modelo confirmado pelo CLI"
                              : test.verification === "mismatch"
                                ? "Respondeu · modelo diferente do selecionado"
                                : test.verification === "resolved"
                                  ? "Respondeu · modelo padrão identificado"
                                  : "Respondeu · modelo não informado pelo CLI"
                            : test.state === "cancelled"
                              ? "Teste cancelado"
                              : test.state === "expired"
                                ? "Tempo de teste esgotado"
                                : "O teste falhou"}
                  </strong>
                  {!same && (
                    <p>
                      Resultado da seleção anterior. Teste a seleção atual antes
                      de confiar neste resultado.
                    </p>
                  )}
                  <p>
                    {labels[test.provider]} · solicitado:{" "}
                    <code>{test.model || "padrão do CLI"}</code>
                    {test.elapsed !== null && (
                      <> · {test.elapsed.toLocaleString("pt-BR")} s</>
                    )}
                    {" · "}
                    {new Date(test.created_at * 1000).toLocaleString("pt-BR")}
                  </p>
                  {test.reported_models.length > 0 && (
                    <p>
                      Informado pelo CLI:{" "}
                      <code>{test.reported_models.join(", ")}</code>
                    </p>
                  )}
                  {test.state === "succeeded" &&
                    test.verification === "unknown" && (
                      <p>
                        O teste confirma que houve resposta. Este CLI não trouxe
                        metadados suficientes para confirmar o modelo usado.
                      </p>
                    )}
                  {test.reply && <blockquote>{test.reply}</blockquote>}
                  {test.error && <p>{test.error}</p>}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </>
  );
}
