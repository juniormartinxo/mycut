import { useEffect, useId, useRef, useState } from "react";
import { request } from "./api";

type Catalog = { families: { family: string; category: string; weight: number }[]; checked_at: string };
let catalogRequest: Promise<Catalog> | null = null;
const loadedFonts = new Map<string, Promise<void>>();

export function loadGoogleFont(family: string): Promise<void> {
  let loading = loadedFonts.get(family);
  if (!loading) {
    loading = request("/google-fonts/install", { method: "POST", body: JSON.stringify({ family }) }).then(async () => {
      const face = new FontFace(family, `url(/api/google-fonts/file?family=${encodeURIComponent(family)})`);
      await face.load();
      document.fonts.add(face);
    }).catch(error => { loadedFonts.delete(family); throw error; });
    loadedFonts.set(family, loading);
  }
  return loading;
}

export function GoogleFontPicker({ value, onChange, disabled = false, inherit = false, label = "Fonte · Google Fonts" }: {
  value: string | null; onChange: (family: string | null) => void; disabled?: boolean; inherit?: boolean; label?: string;
}) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const generation = useRef(0);
  const latestChange = useRef(onChange);
  latestChange.current = onChange;
  const id = useId();
  useEffect(() => {
    let alive = true;
    catalogRequest ??= request<Catalog>("/google-fonts").catch(e => { catalogRequest = null; throw e; });
    catalogRequest.then(c => { if (alive) { setCatalog(c); setError(""); } }).catch(e => { if (alive) setError(e.message); });
    return () => { alive = false; generation.current++; };
  }, [retry]);
  const choose = async (family: string) => {
    const current = ++generation.current;
    setError("");
    if (!family) { onChange(null); return; }
    setLoading(true);
    try {
      await loadGoogleFont(family);
      if (generation.current === current) latestChange.current(family);
    } catch (e) { if (generation.current === current) setError((e as Error).message); }
    finally { if (generation.current === current) setLoading(false); }
  };
  const families = catalog?.families.filter(f => f.family === value || f.family.toLocaleLowerCase().includes(query.toLocaleLowerCase())) || [];
  return <div className="google-font-picker">
    <label htmlFor={id}>{label}</label>
    <input aria-label={`Buscar ${label.toLowerCase()}`} type="search" placeholder="Buscar família…" value={query} onChange={e => setQuery(e.target.value)} disabled={disabled || !catalog} />
    <select id={id} value={value || (inherit ? "" : "Roboto")} disabled={disabled || loading || !catalog} onChange={e => void choose(e.target.value)}>
      {inherit && <option value="">Herdar fonte do projeto</option>}
      {families.map(f => <option key={f.family} value={f.family}>{f.family}</option>)}
    </select>
    {loading && <small role="status">Preparando fonte para a prévia e o vídeo…</small>}
    {catalog && !families.length && <small>Nenhuma família encontrada.</small>}
    {error && <div className="notice danger" role="alert">{error} <button type="button" onClick={() => { setError(""); setRetry(n => n + 1); }}>Tentar novamente</button></div>}
  </div>;
}
