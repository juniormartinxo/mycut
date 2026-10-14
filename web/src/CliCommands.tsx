import type { Integrations } from "./types";

const providers = [
  { id: "codex", label: "Codex" },
  { id: "claude", label: "Claude Code" },
  { id: "grok", label: "Grok" },
] as const;

export function CliCommands({
  settings,
  commands,
  onChange,
  busy,
}: {
  settings: Integrations;
  commands: Integrations["commands"];
  onChange: (commands: Integrations["commands"]) => void;
  busy: boolean;
}) {
  return (
    <>
      <div className="cli-commands-heading">
        <h3>Comandos dos CLIs</h3>
        <p>
          Como o executor chama cada CLI. Para usar outro perfil ou login,
          inclua variáveis antes do executável, por exemplo{" "}
          <code>CLAUDE_CONFIG_DIR=~/.config/perfil claude</code>, ou use um
          wrapper como <code>cloak exec --profile amjr claude</code>. O comando
          roda sem shell: aliases e funções não funcionam.
        </p>
      </div>
      <div className="cli-commands">
        {providers.map(({ id, label }) => {
          const missing =
            settings.runner.online && !settings.runner.providers[id];
          const changed = commands[id].trim() !== settings.commands[id];
          return (
            <label key={id}>
              {label}
              <input
                aria-label={`Comando do ${label}`}
                value={commands[id]}
                maxLength={500}
                required
                spellCheck={false}
                autoComplete="off"
                disabled={busy}
                placeholder={id}
                aria-invalid={missing && !changed}
                aria-describedby={`command-help-${id}`}
                onChange={(e) =>
                  onChange({ ...commands, [id]: e.target.value })
                }
              />
              <span id={`command-help-${id}`} className="cli-command-help">
                {changed
                  ? "Alteração não salva."
                  : missing
                    ? "Executável não encontrado pelo executor."
                    : commands[id].trim() === id
                      ? "Comando padrão."
                      : "Comando personalizado."}
                {commands[id].trim() !== id && (
                  <button
                    type="button"
                    className="text-button"
                    disabled={busy}
                    onClick={() => onChange({ ...commands, [id]: id })}
                  >
                    Restaurar padrão
                  </button>
                )}
              </span>
            </label>
          );
        })}
      </div>
    </>
  );
}
