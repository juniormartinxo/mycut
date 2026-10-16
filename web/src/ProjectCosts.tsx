import { useEffect, useState } from "react";
import { CircleAlert, Coins } from "lucide-react";
import { request } from "./api";
import type { Project, ProjectUsage, UsageCall, UsageTotal } from "./types";
import "./ProjectCosts.css";

const steps: Record<UsageCall["step"], string> = {
  research: "Pesquisa",
  writer: "Roteiro",
  director: "Direção visual",
  reviewer: "Conferência",
  voice: "Narração",
  cover: "Capa",
  art: "Arte",
};
export const providers: Record<UsageCall["provider"], string> = {
  codex: "Codex",
  claude: "Claude Code",
  grok: "Grok",
  elevenlabs: "ElevenLabs",
};
const kinds: Record<ProjectUsage["versions"][number]["kind"], string> = {
  pipeline: "Produção com agentes",
  plan: "Roteiro e cenas",
  scenes: "Cenas",
  scene_edit: "Conversa sobre a cena",
  cover: "Capa",
  voice: "Narração",
  render: "Renderização",
  art: "Arte",
};
const states: Partial<Record<UsageCall["state"], string>> = {
  running: "em andamento",
  failed: "falhou",
  interrupted: "interrompida",
};
const sources = {
  cli: "informado pelo CLI",
  tabela: "tabela de preços",
  plano: "preço do seu plano",
  imagem: "preço por imagem",
};
const numbers = new Intl.NumberFormat("pt-BR");

export function tokens(total: UsageTotal) {
  return total.input + total.cache_read + total.cache_write + total.output;
}

export function money(usd: number, currency: "USD" | "BRL" = "USD") {
  // Single calls often cost fractions of a cent.
  const digits = usd !== 0 && Math.abs(usd) < 0.01 ? 4 : 2;
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(usd);
}

function Value({ usd, rate }: { usd: number | null; rate: number | null }) {
  if (usd === null) return <span className="cost-missing">sem preço</span>;
  return (
    <>
      {money(usd)}
      {rate !== null && <small>{money(usd * rate, "BRL")}</small>}
    </>
  );
}

export function ProjectCosts({ project }: { project: Project }) {
  const [usage, setUsage] = useState<ProjectUsage | null>(null);
  const [error, setError] = useState("");
  const active = project.jobs.some((j) =>
    ["queued", "running"].includes(j.state),
  );
  const stamp = project.jobs.map((j) => j.id + j.state).join();
  useEffect(() => {
    let live = true;
    let timer: number;
    const refresh = async () => {
      try {
        const result = await request<ProjectUsage>(
          `/projects/${project.id}/usage`,
        );
        if (live) {
          setUsage(result);
          setError("");
        }
      } catch (e) {
        if (live) setError((e as Error).message);
      } finally {
        if (live && active) timer = window.setTimeout(refresh, 4000);
      }
    };
    void refresh();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [project.id, stamp, active]);

  if (error)
    return (
      <p className="notice danger" role="alert">
        <CircleAlert size={18} />
        Não foi possível carregar os custos: {error}
      </p>
    );
  if (!usage) return <p role="status">Carregando custos…</p>;
  const rate = usage.usd_brl;
  const { total } = usage;
  return (
    <div className="project-costs">
      <div className="section-heading">
        <div>
          <h2>Quanto este projeto consumiu</h2>
          <p>Tokens e valor aproximado de cada chamada aos agentes e à voz.</p>
        </div>
      </div>
      <dl className="cost-summary">
        <div>
          <dt>Valor aproximado</dt>
          <dd>
            {money(total.usd)}
            {rate !== null && <small>{money(total.usd * rate, "BRL")}</small>}
          </dd>
        </div>
        <div>
          <dt>Tokens</dt>
          <dd>
            {numbers.format(tokens(total))}
            <small>
              {numbers.format(total.output)} de saída ·{" "}
              {numbers.format(total.cache_read)} em cache
            </small>
          </dd>
        </div>
        <div>
          <dt>Créditos ElevenLabs</dt>
          <dd>{numbers.format(total.credits)}</dd>
        </div>
        <div>
          <dt>Buscas na web</dt>
          <dd>{numbers.format(total.web_searches)}</dd>
        </div>
      </dl>
      <p className="cost-note">
        Equivalente ao preço de tabela das APIs; em plano de assinatura não é o
        que você paga.
        {total.unpriced > 0 &&
          ` ${total.unpriced} ${total.unpriced === 1 ? "chamada ficou" : "chamadas ficaram"} sem preço e fora do total.`}{" "}
        Claude Code e Grok informam o valor. O Codex usa a tabela de preços, a
        ElevenLabs, o preço por 1.000 créditos, e as imagens da Arte, o preço por
        imagem, todos em Configurações › Custos.
        {rate !== null &&
          ` Reais pela cotação de ${rate.toLocaleString("pt-BR")}.`}
      </p>
      {!usage.versions.length ? (
        <p className="cost-empty">Nenhuma versão gerada ainda.</p>
      ) : (
        usage.versions.map((version) => (
          <section className="cost-version" key={version.id}>
            <header>
              <div>
                <h3>{kinds[version.kind]}</h3>
                <p>
                  {new Date(version.created_at * 1000).toLocaleString("pt-BR")}
                </p>
              </div>
              {version.calls.length > 0 && (
                <strong>
                  <Value usd={version.total.usd} rate={rate} />
                </strong>
              )}
            </header>
            {!version.recorded ? (
              <p className="cost-empty">
                Consumo não registrado: versão anterior ao controle de custos.
              </p>
            ) : !version.calls.length ? (
              <p className="cost-empty">
                Sem uso de IA: só renderização local.
              </p>
            ) : (
              <div className="cost-table-wrap">
                <table className="cost-table">
                  <thead>
                    <tr>
                      <th scope="col">Etapa</th>
                      <th scope="col">CLI e modelo</th>
                      <th scope="col">Entrada</th>
                      <th scope="col">Cache lido</th>
                      <th scope="col">Cache gravado</th>
                      <th scope="col">Saída</th>
                      <th scope="col">Raciocínio</th>
                      <th scope="col">Buscas</th>
                      <th scope="col">Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {version.calls.map((call, i) => (
                      <tr key={i} className={`cost-${call.state}`}>
                        <th scope="row">
                          {steps[call.step]}
                          {call.attempt > 1 && (
                            <small>{call.attempt}ª tentativa</small>
                          )}
                          {states[call.state] && (
                            <small>{states[call.state]}</small>
                          )}
                        </th>
                        <td>
                          {providers[call.provider]}
                          <small>
                            <code>{call.model || "padrão do CLI"}</code>
                          </small>
                        </td>
                        {call.provider === "elevenlabs" ? (
                          <td colSpan={6}>
                            {call.credits === null
                              ? "Créditos não informados"
                              : `${numbers.format(call.credits)} créditos${call.credits_estimated ? " (estimado pelo texto)" : ""}`}
                          </td>
                        ) : call.unreported ? (
                          <td colSpan={6} className="cost-missing">
                            {call.state === "running"
                              ? "Aguardando o fim da chamada"
                              : "O CLI não informou o consumo"}
                          </td>
                        ) : (
                          <>
                            <td>{numbers.format(call.input)}</td>
                            <td>{numbers.format(call.cache_read)}</td>
                            <td>{numbers.format(call.cache_write)}</td>
                            <td>{numbers.format(call.output)}</td>
                            <td>{numbers.format(call.reasoning)}</td>
                            <td>{numbers.format(call.web_searches)}</td>
                          </>
                        )}
                        <td>
                          <Value usd={call.usd} rate={rate} />
                          {!!call.images && (
                            <small>
                              {call.images} {call.images === 1 ? "imagem" : "imagens"}
                            </small>
                          )}
                          {call.cost_source && (
                            <small>{sources[call.cost_source]}</small>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ))
      )}
      <p className="cost-note">
        <Coins size={14} /> Raciocínio já está incluído na saída. Entrada não
        inclui cache.
      </p>
    </div>
  );
}
