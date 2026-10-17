// Envelope da música presa à fala: abaixa para `ganhoFala` durante a voz e sobe para
// `ganhoPausa` antes da primeira palavra, nas pausas longas e depois da última. Ganhos em dB.

export function marcasDaMusica(cena) {
  const { ganhoFala, ganhoPausa, pausaMinima, rampa } = cena.musica;
  const p = cena.palavras;
  if (!p.length) return [{ t: 0, db: ganhoPausa }];
  const marcas = [{ t: 0, db: ganhoPausa }, { t: Math.max(0, p[0][1] - rampa), db: ganhoPausa }, { t: p[0][1], db: ganhoFala }];
  for (let i = 0; i + 1 < p.length; i++) {
    const fim = p[i][2], proxima = p[i + 1][1];
    if (proxima - fim < pausaMinima) continue;
    const r = Math.min(rampa, (proxima - fim) / 2);   // pausa curta: sobe e desce sem patamar
    marcas.push({ t: fim, db: ganhoFala }, { t: fim + r, db: ganhoPausa },
                { t: proxima - r, db: ganhoPausa }, { t: proxima, db: ganhoFala });
  }
  const ultima = p.at(-1)[2];
  marcas.push({ t: ultima, db: ganhoFala }, { t: ultima + rampa, db: ganhoPausa });
  return marcas.map(m => ({ t: Math.round(m.t * 1e4) / 1e4, db: m.db }));
}

const cache = new WeakMap();
export function ganhoDaMusica(cena, t) {
  if (!cache.has(cena)) cache.set(cena, marcasDaMusica(cena));
  const m = cache.get(cena);
  if (t >= m.at(-1).t) return m.at(-1).db;
  let lo = 0, hi = m.length - 1;
  while (lo < hi) { const k = (lo + hi + 1) >> 1; if (m[k].t <= t) lo = k; else hi = k - 1; }
  const a = m[lo], b = m[lo + 1];
  if (b.t === a.t) return b.db;
  return Math.round((a.db + (b.db - a.db) * (t - a.t) / (b.t - a.t)) * 1e4) / 1e4;
}
