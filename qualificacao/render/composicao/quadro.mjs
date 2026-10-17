// Estado completo de um quadro como função só do tempo t (segundos).
// Sem DOM, relógio, temporizadores ou estado entre chamadas: o mesmo t dá sempre o mesmo quadro.

export const FUSAO = 0.6;

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const r4 = v => Math.round(v * 1e4) / 1e4;
const lerp = (a, b, p) => a + (b - a) * p;
const desacelera = p => 1 - (1 - p) ** 5;
const vaivem = p => (p < 0.5 ? 4 * p ** 3 : 1 - (-2 * p + 2) ** 3 / 2);

// Um trecho que entra por fusão cresce por cima do anterior, que segue inteiro até ser coberto.
function trechosEm(cena, t) {
  const visiveis = [];
  cena.trechos.forEach((trecho, i) => {
    const proximo = cena.trechos[i + 1];
    const cobre = proximo?.entrada === 'fusao' ? FUSAO : 0;
    if (t < trecho.inicio || t >= trecho.fim + cobre) return;
    const opacidade = trecho.entrada === 'fusao' ? clamp((t - trecho.inicio) / FUSAO) : 1;
    visiveis.push({ id: trecho.id, opacidade: r4(opacidade) });
  });
  return visiveis;
}

// Posição dentro do clipe: anda na velocidade escolhida até o instante do congelamento.
function clipeEm(trecho, t) {
  const { inicioNoClipe = 0, velocidade = 1, congelaEm = Infinity } = trecho.clipe;
  const ate = Math.min(t, congelaEm);
  return { tempo: r4(inicioNoClipe + velocidade * (ate - trecho.inicio)), congelado: t >= congelaEm };
}

// Zoom e panorâmica sobre uma imagem parada, do enquadramento `de` ao `ate` durante o trecho.
function kenburnsEm(trecho, t) {
  const { de, ate } = trecho.kenburns;
  const p = vaivem(clamp((t - trecho.inicio) / (trecho.fim - trecho.inicio)));
  return { escala: r4(lerp(de.escala, ate.escala, p)), x: r4(lerp(de.x, ate.x, p)), y: r4(lerp(de.y, ate.y, p)) };
}

// Cada movimento parte de onde a câmera estava quando ele começou, mesmo que o anterior não tenha terminado.
function cameraEm(marcas, t) {
  let atual = { x: marcas[0].x, y: marcas[0].y, zoom: marcas[0].zoom };
  for (let i = 1; i < marcas.length && t >= marcas[i].t; i++) {
    const fim = Math.min(t, marcas[i + 1]?.t ?? Infinity);
    const p = desacelera(clamp((fim - marcas[i].t) / (marcas[i].dur ?? 1)));
    atual = { x: lerp(atual.x, marcas[i].x, p), y: lerp(atual.y, marcas[i].y, p), zoom: lerp(atual.zoom, marcas[i].zoom, p) };
  }
  return { x: r4(atual.x), y: r4(atual.y), zoom: r4(atual.zoom) };
}

// Mola amortecida (rigidez 170, amortecimento 14, massa 1): passa ~13% do alvo e assenta em ~1 s.
const W0 = Math.sqrt(170), ZETA = 14 / (2 * W0), WD = W0 * Math.sqrt(1 - ZETA ** 2);
export function mola(tau) {
  if (tau <= 0) return 0;
  return 1 - Math.exp(-ZETA * W0 * tau) * (Math.cos(WD * tau) + (ZETA * W0 / WD) * Math.sin(WD * tau));
}

function esmaecimento(janelas, t) {
  let d = 0;
  for (const [a, b] of janelas || []) d = Math.max(d, clamp((t - a) / FUSAO) * (1 - clamp((t - (b ?? Infinity)) / FUSAO)));
  return d;
}

function itemEm(item, t) {
  const tau = t - item.entra;
  if (tau < 0) return { estado: 'oculto', opacidade: 0, escala: 0.85, desloc: 40, desfoque: 0, brilho: 0 };
  const d = esmaecimento(item.esmaece, t);
  const estado = d > 0.5 ? 'esmaecido' : tau < 0.7 ? 'entrando' : 'foco';
  return {
    estado,
    opacidade: r4(clamp(tau / 0.25) * (1 - 0.68 * d)),
    escala: r4((0.85 + 0.15 * mola(tau)) * (1 - 0.04 * d)),
    desloc: r4(40 * (1 - desacelera(clamp(tau / 0.7)))),
    desfoque: r4(3 * d),
    brilho: r4(1 - d),
  };
}

const normal = w => w.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^\p{L}\p{N}]/gu, '');

// Grupos de até `n` palavras; pontuação final fecha o grupo, que some meio segundo depois da fala.
function gruposDeLegenda(palavras, n) {
  const grupos = [];
  let atual = [];
  palavras.forEach(([w], i) => {
    atual.push(i);
    if (atual.length === n || /[.?!,;:]$/.test(w) || i === palavras.length - 1) { grupos.push(atual); atual = []; }
  });
  return grupos.map((g, k) => ({
    inicio: palavras[g[0]][1],
    fim: Math.min(palavras[g.at(-1)][2] + 0.5, k + 1 < grupos.length ? palavras[grupos[k + 1][0]][1] : Infinity),
    palavras: g.map(i => palavras[i][0]),
  }));
}

// Memória só de desempenho: os grupos dependem apenas das palavras, nunca do caminho até t.
const cacheDeGrupos = new WeakMap();
function legendaEm(cena, t) {
  if (!cena.legenda || !cena.palavras.length) return null;
  if (!cacheDeGrupos.has(cena.palavras)) cacheDeGrupos.set(cena.palavras, gruposDeLegenda(cena.palavras, cena.legenda.palavrasPorVez));
  const grupos = cacheDeGrupos.get(cena.palavras);
  let lo = 0, hi = grupos.length - 1;
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (grupos[m].inicio <= t) lo = m; else hi = m - 1; }
  const g = grupos[lo];
  if (!(g.inicio <= t && t < g.fim)) return null;
  const destaques = new Set((cena.legenda.destaques || []).map(normal));
  return { palavras: g.palavras, destaques: g.palavras.map(w => destaques.has(normal(w))) };
}

export function quadroEm(cena, t) {
  const trechos = trechosEm(cena, t);
  const porId = Object.fromEntries(cena.trechos.map(tr => [tr.id, tr]));
  const clipe = trechos.map(v => porId[v.id]).filter(tr => tr.tipo === 'clipe').pop();
  const imagem = trechos.map(v => porId[v.id]).filter(tr => tr.kenburns).pop();
  const itens = Object.fromEntries(cena.itens.map(item => [item.id, itemEm(item, t)]));
  // Movimento contínuo do fundo (grade e luzes): também só função de t.
  const ambiente = { grade: r4((t * 24) % 80), luz1: { x: r4(0.2 + 0.08 * Math.sin(t * 0.21)), y: r4(0.25 + 0.06 * Math.cos(t * 0.17)) },
                     luz2: { x: r4(0.75 + 0.07 * Math.cos(t * 0.19)), y: r4(0.7 + 0.08 * Math.sin(t * 0.23)) } };
  return { t: r4(t), trechos, camera: cameraEm(cena.camera, t), itens, legenda: legendaEm(cena, t), ambiente,
           progresso: r4(clamp(t / cena.duracao)), clipe: clipe ? clipeEm(clipe, t) : null, imagem: imagem ? kenburnsEm(imagem, t) : null };
}

// FNV-1a de 32 bits sobre o estado do quadro: mesma assinatura = mesmo quadro descrito.
export function assinatura(valor) {
  const s = JSON.stringify(valor);
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return h.toString(16).padStart(8, '0');
}
