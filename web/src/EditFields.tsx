import { useEffect, useState } from "react";
import type { EditAuthor } from "./types";

/** Every change made on this screen is an operation of the author, recorded with this authorship. */
export const HUMAN: EditAuthor = { kind: "human", name: "Autor" };
const number = (value: number, digits = 2) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: digits });
export const seconds = (ms: number) => `${number(ms / 1000)} s`;
export const clock = (ms: number) =>
  `${Math.floor(ms / 60000)}:${(Math.floor(ms / 1000) % 60).toString().padStart(2, "0")}`;
export const bytes = (size: number) =>
  size < 1024
    ? `${size} B`
    : size < 1024 ** 2
      ? `${number(size / 1024, 1)} KB`
      : `${number(size / 1024 ** 2, 1)} MB`;

/** Commits a typed value when the field loses focus or on Enter, as one operation. */
export function NumberField({
  label,
  value,
  step,
  min,
  onCommit,
  disabled,
}: {
  label: string;
  value: number;
  step: number;
  min?: number;
  onCommit: (value: number) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  const commit = () => {
    const parsed = Number(text.replace(",", "."));
    if (!Number.isFinite(parsed) || parsed === value) return setText(String(value));
    onCommit(parsed);
  };
  return (
    <label>
      {label}
      <input
        type="number"
        inputMode="decimal"
        step={step}
        min={min}
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && commit()}
      />
    </label>
  );
}
