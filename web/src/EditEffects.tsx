import { Plus, Trash2 } from "lucide-react";
import { isAudio, valueAt } from "./engine/timeline";
import type { Easing, Keyframe } from "./engine/timeline";
import { NumberField, snapToFrame } from "./EditFields";
import type { EditItem, EditProject, EditTrack } from "./types";

type Operation = Record<string, unknown>;

export const propertyNames: Record<string, string> = {
  x: "Posição X",
  y: "Posição Y",
  opacity: "Opacidade",
  scale: "Escala",
  rotation: "Rotação (graus)",
  brightness: "Brilho",
  contrast: "Contraste",
  saturation: "Saturação",
  blur: "Desfoque (px)",
  zoom: "Zoom",
  pan_x: "Panorâmica horizontal",
  pan_y: "Panorâmica vertical",
};
const LOOK = ["opacity", "scale", "rotation", "brightness", "contrast", "saturation", "blur"];
// Properties that change over an item through points in time, as the service accepts them (Q22).
const animated: Record<string, string[]> = {
  visual: ["x", "y", ...LOOK, "zoom", "pan_x", "pan_y"],
  text: ["x", "y", ...LOOK],
};
const steps: Record<string, number> = { x: 1, y: 1, rotation: 1, blur: 1 };
const easings: Record<Easing, string> = { linear: "Linear", ease: "Suave", hold: "Degrau" };
const entrances: Record<string, Record<string, string>> = {
  visual: { fade: "Fade", dissolve: "Fusão" },
  text: { fade: "Fade", rise: "Subir", pop: "Surgir", type: "Digitar" },
  audio: { fade: "Fade" },
};
const exits: Record<string, Record<string, string>> = {
  visual: { fade: "Fade" },
  text: { fade: "Fade", sink: "Descer", pop: "Sumir" },
  audio: { fade: "Fade" },
};

/** Transitions, speed and freeze, and the points in time of an item; every change is one operation. */
export function EditEffects({
  project,
  item,
  track,
  cursor,
  pending,
  onChange,
  onKeyframes,
  property,
  onProperty,
}: {
  project: EditProject;
  item: EditItem;
  track: EditTrack;
  cursor: number;
  pending: boolean;
  onChange: (changes: Operation) => void;
  onKeyframes: (property: string, points: Keyframe[] | null) => void;
  /** The property whose points are open; it stays chosen across revisions. */
  property: string | null;
  onProperty: (property: string) => void;
}) {
  const group = isAudio(track.kind) ? "audio" : track.kind;
  const frame = 1000 / project.format.fps;
  const ms = (seconds: number) => snapToFrame(seconds * 1000, project.format.fps);
  const local = cursor - item.start_ms;
  const inside = local >= 0 && local <= item.duration_ms;
  return (
    <>
      <fieldset className="inspector-style">
        <legend>Transições</legend>
        {(["enter", "exit"] as const).map((side) => {
          const current = item[side];
          const options = (side === "enter" ? entrances : exits)[group];
          const label = side === "enter" ? "Entrada" : "Saída";
          return (
            <div className="inspector-grid" key={side}>
              <label>
                {label}
                <select
                  value={current?.kind ?? ""}
                  disabled={pending}
                  onChange={(e) =>
                    onChange({
                      [side]: e.target.value
                        ? { kind: e.target.value, duration_ms: current?.duration_ms ?? Math.min(500, item.duration_ms) }
                        : null,
                    })
                  }
                >
                  <option value="">Corte seco</option>
                  {Object.entries(options).map(([kind, name]) => (
                    <option key={kind} value={kind}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              {current && (
                <NumberField
                  label={`Duração da ${label.toLowerCase()} (s)`}
                  value={current.duration_ms / 1000}
                  step={frame / 1000}
                  min={frame / 1000}
                  disabled={pending}
                  onCommit={(v) => onChange({ [side]: { ...current, duration_ms: Math.max(1, ms(v)) } })}
                />
              )}
            </div>
          );
        })}
      </fieldset>
      {group === "visual" && (
        <fieldset className="inspector-style">
          <legend>Velocidade e congelamento</legend>
          <div className="inspector-grid">
            <NumberField
              label="Velocidade (×)"
              value={item.speed}
              step={0.05}
              min={0.25}
              disabled={pending}
              onCommit={(v) => onChange({ speed: v })}
            />
            {item.freeze && (
              <>
                <NumberField
                  label="Congelar em (s)"
                  value={item.freeze.at_ms / 1000}
                  step={frame / 1000}
                  min={0}
                  disabled={pending}
                  onCommit={(v) => onChange({ freeze: { ...item.freeze!, at_ms: ms(v) } })}
                />
                <NumberField
                  label="Quadro parado por (s)"
                  value={item.freeze.duration_ms / 1000}
                  step={frame / 1000}
                  min={frame / 1000}
                  disabled={pending}
                  onCommit={(v) => onChange({ freeze: { ...item.freeze!, duration_ms: Math.max(1, ms(v)) } })}
                />
              </>
            )}
          </div>
          <p className="edit-help">
            A velocidade e o quadro parado mudam o tempo que o clipe ocupa; os itens seguintes ficam onde estão.
          </p>
          {item.freeze ? (
            <button type="button" className="text-button" disabled={pending} onClick={() => onChange({ freeze: null })}>
              Tirar o congelamento
            </button>
          ) : (
            <button
              type="button"
              className="button secondary"
              disabled={pending || !inside || local >= item.duration_ms}
              title={inside ? undefined : "Coloque o cursor dentro do clipe"}
              onClick={() => onChange({ freeze: { at_ms: ms(local / 1000), duration_ms: 1000 } })}
            >
              Congelar quadro no cursor
            </button>
          )}
        </fieldset>
      )}
      {animated[group] && (
        <Keyframes item={item} names={animated[group]} pending={pending} local={inside ? local : null} frame={frame}
          ms={ms} onKeyframes={onKeyframes} chosen={property} onProperty={onProperty} />
      )}
    </>
  );
}

function Keyframes({
  item,
  names,
  pending,
  local,
  frame,
  ms,
  onKeyframes,
  chosen,
  onProperty,
}: {
  item: EditItem;
  names: string[];
  pending: boolean;
  local: number | null;
  frame: number;
  ms: (seconds: number) => number;
  onKeyframes: (property: string, points: Keyframe[] | null) => void;
  chosen: string | null;
  onProperty: (property: string) => void;
}) {
  const property =
    chosen && names.includes(chosen) ? chosen : (names.find((name) => item.keyframes[name]) ?? "opacity");
  const points = item.keyframes[property] ?? [];
  const base =
    property === "x" || property === "y"
      ? item.geometry![property]
      : Number(item.resolved_style[property]?.value ?? 0);
  const label = propertyNames[property];
  const replace = (index: number, point: Keyframe | null) => {
    const next = points.flatMap((p, k) => (k !== index ? [p] : point ? [point] : []));
    onKeyframes(property, next.length ? next : null);
  };
  return (
    <fieldset className="inspector-style">
      <legend>Pontos no tempo</legend>
      <label>
        Propriedade
        <select value={property} onChange={(e) => onProperty(e.target.value)}>
          {names.map((name) => (
            <option key={name} value={name}>
              {propertyNames[name]}
              {item.keyframes[name] ? ` (${item.keyframes[name].length})` : ""}
            </option>
          ))}
        </select>
      </label>
      {points.length > 0 ? (
        <ol className="keyframe-list" aria-label={`Pontos no tempo de ${label}`}>
          {points.map((point, index) => (
            <li key={`${index}:${point.at_ms}`}>
              <NumberField
                label={`Instante do ponto ${index + 1} (s)`}
                value={point.at_ms / 1000}
                step={frame / 1000}
                min={0}
                disabled={pending}
                onCommit={(v) => replace(index, { ...point, at_ms: ms(v) })}
              />
              <NumberField
                label={`Valor do ponto ${index + 1}`}
                value={point.value}
                step={steps[property] ?? 0.05}
                disabled={pending}
                onCommit={(v) => replace(index, { ...point, value: v })}
              />
              <label>
                {`Curva do ponto ${index + 1}`}
                <select
                  value={point.easing}
                  disabled={pending}
                  onChange={(e) => replace(index, { ...point, easing: e.target.value as Easing })}
                >
                  {Object.entries(easings).map(([value, name]) => (
                    <option key={value} value={value}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="icon-button"
                disabled={pending}
                aria-label={`Remover ponto ${index + 1}`}
                onClick={() => replace(index, null)}
              >
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="edit-help">{label} fica em {base} durante todo o item.</p>
      )}
      <button
        type="button"
        className="button secondary"
        disabled={pending || local === null || points.some((p) => p.at_ms === Math.round(local))}
        title={local === null ? "Coloque o cursor dentro do item" : undefined}
        onClick={() => {
          const at = Math.round(local!);
          const value = valueAt(points, at, base);
          onKeyframes(property, [...points, { at_ms: at, value, easing: "linear" }]);
        }}
      >
        <Plus size={15} />
        Adicionar ponto no cursor
      </button>
    </fieldset>
  );
}
