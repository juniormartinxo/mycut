import { useState } from "react";
import { Coins, Plus, Save, Trash2 } from "lucide-react";
import { request } from "./api";
import type { Integrations, Pricing } from "./types";
import { providers } from "./ProjectCosts";
import "./ProjectCosts.css";

type Row = { model: string; input: string; cache_read: string; output: string };
const toRows = (pricing: Pricing): Row[] =>
  Object.entries(pricing.models).map(([model, price]) => ({
    model,
    input: String(price.input),
    cache_read: String(price.cache_read),
    output: String(price.output),
  }));
const optional = (value: string) =>
  value.trim() === "" ? null : Number(value.replace(",", "."));
const number = (value: string) => Number(value.replace(",", "."));

export function PricingSettings({
  settings,
  onSaved,
  busy,
}: {
  settings: Integrations;
  onSaved: (settings: Integrations) => void;
  busy: boolean;
}) {
  const { pricing } = settings;
  const [rows, setRows] = useState(() => toRows(pricing));
  const [rate, setRate] = useState(String(pricing.usd_brl ?? ""));
  const [credits, setCredits] = useState(
    String(pricing.elevenlabs_usd_per_1k_credits ?? ""),
  );
  const [images, setImages] = useState({
    codex: String(pricing.images?.codex ?? ""),
    grok: String(pricing.images?.grok ?? ""),
  });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const missing = settings.agent_models.codex.models.filter(
    (m) => !rows.some((row) => row.model === m.id),
  );
  const update = (index: number, change: Partial<Row>) =>
    setRows(rows.map((row, i) => (i === index ? { ...row, ...change } : row)));
  return (
    <form
      className="pricing-form"
      onSubmit={(e) => {
        e.preventDefault();
        setPending(true);
        setError("");
        const models = Object.fromEntries(
          rows
            .filter((row) => row.model.trim())
            .map((row) => [
              row.model.trim(),
              {
                input: number(row.input),
                cache_read: number(row.cache_read),
                output: number(row.output),
              },
            ]),
        );
        request<Integrations>("/integrations/pricing", {
          method: "PUT",
          body: JSON.stringify({
            usd_brl: optional(rate),
            elevenlabs_usd_per_1k_credits: optional(credits),
            models,
            images: { codex: optional(images.codex), grok: optional(images.grok) },
          }),
        })
          .then((result) => {
            setRows(toRows(result.pricing));
            onSaved(result);
          })
          .catch((e) => setError((e as Error).message))
          .finally(() => setPending(false));
      }}
    >
      <p>
        Claude Code e Grok informam o valor de cada chamada. O Codex informa só
        os tokens: o valor vem da tabela abaixo, em US$ por 1 milhão de tokens.
        Os padrões são os{" "}
        <a
          href="https://developers.openai.com/api/docs/pricing"
          target="_blank"
          rel="noreferrer"
        >
          preços oficiais da OpenAI
        </a>{" "}
        (Standard, contexto curto) consultados em{" "}
        {pricing.checked_at
          ? new Date(pricing.checked_at + "T12:00").toLocaleDateString("pt-BR")
          : "data não informada"}
        . Os valores equivalem ao preço de tabela das APIs; em plano de
        assinatura não é o que você paga.
      </p>
      <fieldset disabled={busy || pending}>
        <div className="pricing-rates">
          <label>
            Cotação do dólar (R$ por US$ 1)
            <input
              inputMode="decimal"
              value={rate}
              placeholder="Sem conversão para reais"
              onChange={(e) => setRate(e.target.value)}
            />
          </label>
          <label>
            ElevenLabs: US$ por 1.000 créditos
            <input
              inputMode="decimal"
              value={credits}
              placeholder="Mostrar só os créditos"
              onChange={(e) => setCredits(e.target.value)}
            />
          </label>
          {(["codex", "grok"] as const).map((provider) => (
            <label key={provider}>
              Arte com {providers[provider]}: US$ por imagem
              <input
                inputMode="decimal"
                value={images[provider]}
                placeholder="Sem preço"
                onChange={(e) =>
                  setImages({ ...images, [provider]: e.target.value })
                }
              />
            </label>
          ))}
        </div>
        <p className="cost-note">
          Os CLIs não informam o custo das imagens. O preço por imagem serve só
          para ter uma ideia: os padrões são GPT Image 1.5 (qualidade média,
          1024×1536) e grok-imagine na qualidade alta.
        </p>
        <div className="cost-table-wrap">
          <table className="cost-table">
            <thead>
              <tr>
                <th scope="col">Modelo do Codex</th>
                <th scope="col">Entrada</th>
                <th scope="col">Entrada em cache</th>
                <th scope="col">Saída</th>
                <th scope="col">
                  <span className="cost-sr-only">Remover</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  <th scope="row">
                    <input
                      aria-label="Modelo"
                      value={row.model}
                      required
                      maxLength={150}
                      pattern="[a-zA-Z0-9._:/\-]+"
                      spellCheck={false}
                      onChange={(e) => update(i, { model: e.target.value })}
                    />
                  </th>
                  {(["input", "cache_read", "output"] as const).map((key) => (
                    <td key={key}>
                      <input
                        aria-label={`${row.model || "Modelo"}: ${key === "input" ? "entrada" : key === "cache_read" ? "entrada em cache" : "saída"}`}
                        inputMode="decimal"
                        required
                        value={row[key]}
                        onChange={(e) => update(i, { [key]: e.target.value })}
                      />
                    </td>
                  ))}
                  <td>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`Remover ${row.model || "modelo"}`}
                      onClick={() => setRows(rows.filter((_, j) => j !== i))}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {missing.length > 0 && (
          <p className="cost-note">
            Modelos do Codex sem preço:{" "}
            {missing.map((m) => (
              <button
                type="button"
                className="text-button"
                key={m.id}
                onClick={() =>
                  setRows([
                    ...rows,
                    { model: m.id, input: "", cache_read: "", output: "" },
                  ])
                }
              >
                <Plus size={13} /> {m.id}
              </button>
            ))}
          </p>
        )}
      </fieldset>
      {error && (
        <p className="notice danger" role="alert">
          {error}
        </p>
      )}
      <div className="pricing-actions">
        <button
          type="button"
          className="button secondary"
          disabled={busy || pending}
          onClick={() =>
            setRows([
              ...rows,
              { model: "", input: "", cache_read: "", output: "" },
            ])
          }
        >
          <Plus size={16} />
          Adicionar modelo
        </button>
        <button className="button secondary" disabled={busy || pending}>
          <Save size={16} />
          Salvar preços
        </button>
      </div>
      <p className="cost-note">
        <Coins size={14} /> Mudanças valem também para o consumo já registrado:
        o valor é recalculado a partir dos tokens.
      </p>
    </form>
  );
}
