import "./VideoTheme.css";

export function VideoTheme({
  accent,
  onChange,
  disabled = false,
}: {
  accent: string | null;
  onChange: (accent: string | null) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset className="video-theme" disabled={disabled}>
      <legend>Cor do vídeo</legend>
      <div className="video-theme-controls">
        <label>
          Escolha da cor
          <select
            value={accent === null ? "auto" : "custom"}
            onChange={(e) =>
              onChange(e.target.value === "auto" ? null : "#bd4b28")
            }
          >
            <option value="auto">O agente escolhe</option>
            <option value="custom">Eu escolho a cor</option>
          </select>
        </label>
        {accent !== null && (
          <label className="video-theme-color">
            Cor de destaque
            <span>
              <input
                type="color"
                value={accent}
                aria-label="Cor de destaque"
                onChange={(e) => onChange(e.target.value)}
              />
              <code>{accent.toUpperCase()}</code>
            </span>
          </label>
        )}
      </div>
      <p>
        {accent === null
          ? "O agente define uma cor para as cenas e a capa."
          : "O agente usará esta cor nas cenas e na capa desde a geração."}
      </p>
    </fieldset>
  );
}
