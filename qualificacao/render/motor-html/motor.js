// Motor HTML determinístico: desenha no DOM o estado de quadroEm(cena, t).
// A mesma página serve à prévia (tocando com o relógio do áudio, ou parada num instante)
// e à gravação (um Chrome sem janela pede cada quadro com irPara(t) e captura a tela).
// Na gravação, nada aqui lê relógio, agenda temporizador ou usa animação CSS.
import { assinatura, quadroEm } from '../composicao/quadro.mjs';
import { ganhoDaMusica, marcasDaMusica } from '../composicao/mixagem.mjs';

const MIDIA = '/midia/';
const LATIN = 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD';
const FONTES = [['Inter', 400], ['Inter', 600], ['Inter', 800], ['Inter', 900], ['JetBrains Mono', 500], ['JetBrains Mono', 800]];
const arquivoDaFonte = (familia, peso) => `${familia.toLowerCase().replace(' ', '-')}-latin-${peso}-normal.woff2`;
const db = v => Math.pow(10, v / 20);

let cena, porId, palco, camadas, itensEl, caixas, legendaEl, progressoEl, ultimaLegenda = '';
let audio = null;           // { ctx, buffers, inicioCtx, t0, captura }
const prevista = { tocando: false, t: 0, segurar: false, registro: [], geracao: 0 };

function el(tag, classe, pai) {
  const n = document.createElement(tag);
  if (classe) n.className = classe;
  if (pai) pai.appendChild(n);
  return n;
}

function montarItem(item, pai) {
  const n = el('div', `item ${item.tipo} tom${item.tom}${item.vidro ? ' vidro' : ''}`, pai);
  n.style.left = `${item.x}px`;
  n.style.top = `${item.y}px`;
  n.style.width = `${item.largura}px`;
  if (item.tipo !== 'titulo') el('div', 'selo', n).textContent = item.vidro ? 'vidro fosco' : 'ponto';
  el('div', 'titulo', n).textContent = item.titulo;
  el('div', 'texto', n).textContent = item.texto;
  return n;
}

async function carregar(dados, { escala = 1, comAudio = false } = {}) {
  cena = dados;
  porId = Object.fromEntries(cena.trechos.map(t => [t.id, t]));
  const { largura: W, altura: H } = cena.formato;
  palco = document.getElementById('palco');
  palco.replaceChildren();
  Object.assign(palco.style, { width: `${W}px`, height: `${H}px` });
  palco.style.setProperty('--cor1', cena.fundo.cor1);
  palco.style.setProperty('--cor2', cena.fundo.cor2);
  palco.style.setProperty('--grade', cena.fundo.grade);

  // Fontes carregadas explicitamente dos arquivos locais, antes do primeiro quadro.
  for (const [familia, peso] of FONTES) {
    const face = new FontFace(familia, `url(${MIDIA}fontes/${arquivoDaFonte(familia, peso)})`, { weight: String(peso), unicodeRange: LATIN });
    document.fonts.add(await face.load());
  }

  camadas = {};
  const mapa = el('div', 'camada mapa', palco);
  el('div', 'fundo', mapa);
  const grade = el('div', 'grade', mapa);
  const luz1 = el('div', 'luz', mapa), luz2 = el('div', 'luz', mapa);
  luz1.style.background = '#38bdf8';
  luz2.style.background = '#10b981';
  const mundo = el('div', 'mundo', mapa);
  Object.assign(mundo.style, { width: `${cena.mapa.largura}px`, height: `${cena.mapa.altura}px` });
  camadas.mapa = { raiz: mapa, grade, luz1, luz2, mundo };

  const imagens = [];
  for (const trecho of cena.trechos) {
    if (trecho.tipo === 'imagem') {
      const raiz = el('div', 'camada imagem', palco);
      const img = el('img', '', raiz);
      img.src = MIDIA + trecho.imagem;
      imagens.push(img);
      camadas[trecho.id] = { raiz, img };
    } else if (trecho.tipo === 'clipe') {
      const raiz = el('div', 'camada video', palco);
      camadas[trecho.id] = { raiz, img: el('img', 'quadro-do-clipe', raiz), sobre: el('div', 'camada', palco) };
    }
  }
  itensEl = {};
  for (const item of cena.itens) {
    const pai = item.trecho === 'mapa' ? mundo : camadas[item.trecho].sobre;
    itensEl[item.id] = montarItem(item, pai);
  }
  legendaEl = el('div', 'legenda', palco);
  const L = cena.legenda;
  Object.assign(legendaEl.style, { left: `${L.x}px`, top: `${L.y}px`, width: `${L.largura}px`, height: `${L.altura}px` });
  if (cena.marcaDeTeste) el('div', 'marca-teste', palco).textContent = cena.marcaDeTeste;
  progressoEl = el('div', 'progresso', palco);

  await Promise.all(imagens.map(img => img.decode()));
  await document.fonts.ready;
  // Meia largura e meia altura de cada item do mapa, com folga para mola, deslocamento e desfoque.
  caixas = Object.fromEntries(cena.itens.map(i => [i.id, [i.largura * 0.55 + 60, itensEl[i.id].offsetHeight * 0.55 + 60]]));
  escalar(escala);
  if (comAudio) await carregarAudio();
  const relatorio = {
    fontes: FONTES.map(([f, p]) => ({ fonte: `${p} ${f}`, carregada: document.fonts.check(`${p} 40px "${f}"`) })),
    animacoes: document.getAnimations().length,
    transicoes: [...document.querySelectorAll('*')].filter(n => getComputedStyle(n).transitionDuration.split(',').some(d => parseFloat(d) > 0)).length,
  };
  await irPara(0);
  return relatorio;
}

function escalar(escala) {
  const { largura: W, altura: H } = cena.formato;
  // zoom, e não transform: scale(), porque o backdrop-filter sob um transform amostra o fundo na escala errada.
  palco.style.zoom = escala === 1 ? '' : String(escala);
  Object.assign(document.getElementById('moldura').style, { width: `${W * escala}px`, height: `${H * escala}px` });
}

// Aplica o estado do quadro ao DOM. Não espera nada: a espera do clipe fica em irPara.
function aplicar(q) {
  const { largura: W, altura: H } = cena.formato;
  const visiveis = new Map(q.trechos.map((v, i) => [v.id, { ...v, z: i }]));
  let mapaOpacidade = 0, mapaZ = 0;
  for (const [id, v] of visiveis) if (porId[id].tipo === 'mapa') { mapaOpacidade = Math.max(mapaOpacidade, v.opacidade); mapaZ = v.z; }
  const m = camadas.mapa;
  m.raiz.style.visibility = mapaOpacidade > 0 ? 'visible' : 'hidden';
  m.raiz.style.opacity = mapaOpacidade;
  m.raiz.style.zIndex = 2 * mapaZ;
  if (mapaOpacidade > 0) {
    const c = q.camera;
    m.mundo.style.transform = `translate(${W / 2 - c.x * c.zoom}px, ${H / 2 - c.y * c.zoom}px) scale(${c.zoom})`;
    m.grade.style.backgroundPosition = `0 ${q.ambiente.grade}px`;
    m.luz1.style.left = `${q.ambiente.luz1.x * W}px`; m.luz1.style.top = `${q.ambiente.luz1.y * H}px`;
    m.luz2.style.left = `${q.ambiente.luz2.x * W}px`; m.luz2.style.top = `${q.ambiente.luz2.y * H}px`;
  }
  for (const trecho of cena.trechos) {
    if (trecho.tipo === 'mapa') continue;
    const camada = camadas[trecho.id], v = visiveis.get(trecho.id);
    for (const raiz of [camada.raiz, camada.sobre].filter(Boolean)) {
      raiz.style.visibility = v ? 'visible' : 'hidden';
      raiz.style.opacity = v ? v.opacidade : 0;
      raiz.style.zIndex = v ? 2 * v.z + (raiz === camada.sobre ? 1 : 0) : 0;
    }
    if (v && trecho.tipo === 'imagem') {
      camada.img.style.transform = `translate(${q.imagem.x}px, ${q.imagem.y}px) scale(${q.imagem.escala})`;
    }
  }
  // Itens do mapa fora do enquadramento da câmera saem do desenho: no vídeo longo, os esmaecidos
  // de capítulos antigos (com desfoque) custariam rasterização a cada quadro sem aparecer.
  const c = q.camera, mx = W / 2 / c.zoom, my = H / 2 / c.zoom;
  const noQuadro = item => Math.abs(item.x - c.x) <= mx + caixas[item.id][0] && Math.abs(item.y - c.y) <= my + caixas[item.id][1];
  for (const item of cena.itens) {
    const s = q.itens[item.id], n = itensEl[item.id];
    const ativo = s.opacidade > 0 && (item.trecho === 'mapa' ? mapaOpacidade > 0 && noQuadro(item) : visiveis.has(item.trecho));
    n.style.visibility = ativo ? 'visible' : 'hidden';
    if (!ativo) continue;
    n.style.opacity = s.opacidade;
    n.style.transform = `translate(-50%, -50%) translateY(${s.desloc}px) scale(${s.escala})`;
    n.style.filter = s.desfoque > 0.01 ? `blur(${s.desfoque}px)` : 'none';
    n.style.setProperty('--brilho', item.brilho ? s.brilho : 0);
  }
  const html = q.legenda ? q.legenda.palavras.map((w, i) => q.legenda.destaques[i] ? `<span class="destaque">${w}</span>` : w).join(' ') : '';
  if (html !== ultimaLegenda) { legendaEl.innerHTML = html; ultimaLegenda = html; }
  legendaEl.style.visibility = q.legenda ? 'visible' : 'hidden';
  progressoEl.style.width = `${q.progresso * 100}%`;
}

// O clipe vem como quadros JPEG; cada instante mostra o quadro exato, já decodificado.
const cacheDeQuadros = new Map();   // url → Promise da imagem decodificada (só desempenho)
const quadrosProntos = new Set();
function urlDoQuadro(trecho, tempo) {
  const c = trecho.clipe;
  const k = Math.min(c.total - 1, Math.floor(tempo * c.fps + 1e-6));
  return `${MIDIA}${c.quadros}${String(k).padStart(4, '0')}.jpg`;
}
function decodificado(url) {
  if (!cacheDeQuadros.has(url)) {
    const img = new Image();
    img.src = url;
    cacheDeQuadros.set(url, img.decode().then(() => { quadrosProntos.add(url); return img; }));
    if (cacheDeQuadros.size > 150) { const velho = cacheDeQuadros.keys().next().value; cacheDeQuadros.delete(velho); quadrosProntos.delete(velho); }
  }
  return cacheDeQuadros.get(url);
}
const clipeVisivel = q => q.trechos.map(v => porId[v.id]).filter(tr => tr.tipo === 'clipe').pop();

// Vai ao instante t e só resolve quando o quadro inteiro está pronto, inclusive o do clipe.
async function irPara(t) {
  const q = quadroEm(cena, t);
  const trecho = q.clipe && clipeVisivel(q);
  if (trecho) {
    const url = urlDoQuadro(trecho, q.clipe.tempo), img = camadas[trecho.id].img;
    await decodificado(url);
    if (img.getAttribute('src') !== url) { img.src = url; await img.decode(); }
  }
  aplicar(q);
  prevista.t = t;
  return { t, assinatura: assinatura(q) };
}

// ---------- Áudio: o mesmo grafo toca na prévia e é renderizado offline na exportação ----------

async function carregarAudio() {
  const decodificador = new OfflineAudioContext(2, 48000, 48000);
  const buscar = async nome => decodificador.decodeAudioData(await (await fetch(MIDIA + nome)).arrayBuffer());
  audio = { buffers: { narracao: await buscar(cena.narracao.arquivo), musica: await buscar(cena.musica.arquivo) } };
}

// Monta narração e música com o envelope da música; `quando` é o instante do contexto em que t0 toca.
function montarGrafo(ctx, t0, quando, saida, { semNarracao = false, semMusica = false } = {}) {
  const narr = ctx.createBufferSource();
  narr.buffer = audio.buffers.narracao;
  if (!semNarracao) narr.connect(saida);
  narr.start(quando, Math.min(t0, narr.buffer.duration));
  const mus = ctx.createBufferSource();
  mus.buffer = audio.buffers.musica;
  const ganho = ctx.createGain();
  // Rampa exponencial do ganho = rampa linear em dB, como ganhoDaMusica interpola.
  ganho.gain.setValueAtTime(db(ganhoDaMusica(cena, t0)), quando);
  for (const marca of marcasDaMusica(cena)) {
    if (marca.t > t0) ganho.gain.exponentialRampToValueAtTime(db(marca.db), quando + (marca.t - t0));
  }
  mus.connect(ganho);
  if (!semMusica) ganho.connect(saida);
  mus.start(quando, Math.min(t0, mus.buffer.duration));
  return [narr, mus];
}

// Exportação: renderiza [t0, t0 + duracao) offline e devolve PCM float32 intercalado (estéreo) em base64.
// `opcoes` deixa de fora a narração ou a música, para medir cada parte da mixagem.
async function mixar(t0, duracao, opcoes) {
  if (!audio) await carregarAudio();
  const quadros = Math.round(duracao * 48000);
  const ctx = new OfflineAudioContext(2, quadros, 48000);
  montarGrafo(ctx, t0, 0, ctx.destination, opcoes);
  const buf = await ctx.startRendering();
  const l = buf.getChannelData(0), r = buf.getChannelData(1), pcm = new Float32Array(quadros * 2);
  for (let i = 0; i < quadros; i++) { pcm[2 * i] = l[i]; pcm[2 * i + 1] = r[i]; }
  const bytes = new Uint8Array(pcm.buffer);
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

// ---------- Prévia tocando: o relógio é o do áudio, e cada quadro desenhado é quadroEm(t) ----------

let fontesDeAudio = [];
async function tocar(desde = prevista.t, { capturar = false } = {}) {
  if (!audio) await carregarAudio();
  pausar();
  const ctx = audio.ctx ?? (audio.ctx = new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' }));
  await ctx.resume();
  let saida = ctx.destination;
  audio.captura = null;
  if (capturar) {
    await ctx.audioWorklet.addModule('captura.js');
    const tap = new AudioWorkletNode(ctx, 'captura', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [2] });
    const blocos = [];
    tap.port.onmessage = e => blocos.push(e.data);
    tap.connect(ctx.destination);
    saida = tap;
    audio.captura = { blocos };
  }
  const quando = ctx.currentTime + 0.1;
  fontesDeAudio = montarGrafo(ctx, desde, quando, saida);
  Object.assign(audio, { inicioCtx: quando, t0: desde });
  prevista.tocando = true;
  prevista.registro = [];
  prevista.pedidoEm = performance.now();   // só na prévia: mede a espera até o primeiro quadro
  // Cada tocar() inicia um laço novo; um laço de antes de pausar, ainda agendado, para sozinho.
  const geracao = ++prevista.geracao;
  requestAnimationFrame(agora => passo(agora, geracao));
}

function tempoTocando() {
  const { contextTime } = audio.ctx.getOutputTimestamp();
  return Math.max(audio.t0, audio.t0 + ((contextTime ?? audio.ctx.currentTime) - audio.inicioCtx));
}

function passo(agora, geracao) {
  if (!prevista.tocando || geracao !== prevista.geracao) return;
  if (!prevista.segurar) {
    const t = Math.min(cena.duracao, tempoTocando());
    const q = quadroEm(cena, t);
    aplicar(q);
    mostrarQuadroDoClipe(q);
    prevista.t = t;
    prevista.registro.push([agora, t]);
    if (prevista.pedidoDeSegurar) { prevista.segurar = true; prevista.pedidoDeSegurar(t); prevista.pedidoDeSegurar = null; }
    if (t >= cena.duracao) { pausar(); return; }
  }
  requestAnimationFrame(proximo => passo(proximo, geracao));
}

// Tocando, mostra o quadro do clipe se já estiver decodificado e prepara os próximos;
// se não estiver, mantém o anterior e conta o atraso (medido na prévia).
function mostrarQuadroDoClipe(q) {
  const trecho = q.clipe && clipeVisivel(q);
  if (!trecho) return;
  const url = urlDoQuadro(trecho, q.clipe.tempo), img = camadas[trecho.id].img;
  for (let k = 1; k <= 20; k++) decodificado(urlDoQuadro(trecho, q.clipe.congelado ? q.clipe.tempo : q.clipe.tempo + k * trecho.clipe.velocidade / 30));
  if (img.getAttribute('src') === url) return;
  if (quadrosProntos.has(url)) img.src = url;
  else { decodificado(url); prevista.atrasosDoClipe = (prevista.atrasosDoClipe ?? 0) + 1; }
}

function pausar() {
  prevista.tocando = false;
  prevista.segurar = false;
  for (const f of fontesDeAudio) { try { f.stop(); } catch { /* já parou */ } }
  fontesDeAudio = [];
}

// Para medir a prévia tocando: o próximo quadro desenhado fica na tela até soltar(); o áudio segue.
const segurarProximo = () => new Promise(ok => { prevista.pedidoDeSegurar = ok; });
const soltar = () => { prevista.segurar = false; };

function capturaDeAudio() {
  const c = audio?.captura;
  if (!c) return null;
  return { inicioCtx: audio.inicioCtx, t0: audio.t0, taxa: audio.ctx.sampleRate, blocos: c.blocos.splice(0) };
}

// ---------- Página ----------

const params = new URLSearchParams(location.search);
window.motor = { carregar, irPara, tocar, pausar, mixar, segurarProximo, soltar, capturaDeAudio, prevista,
                 get t() { return prevista.t; } };

if (params.get('cena')) {
  const dados = await (await fetch(params.get('cena'))).json();
  const escala = Number(params.get('escala') ?? 1);
  await carregar(dados, { escala });
  const controles = document.getElementById('controles');
  controles.hidden = false;
  const posicao = document.getElementById('posicao'), relogio = document.getElementById('relogio');
  posicao.max = dados.duracao;
  posicao.oninput = () => { pausar(); irPara(Number(posicao.value)); };
  document.getElementById('tocar').onclick = () => (prevista.tocando ? pausar() : tocar());
  const mostrar = () => { relogio.textContent = `${prevista.t.toFixed(2)} s`; if (prevista.tocando) posicao.value = prevista.t; requestAnimationFrame(mostrar); };
  requestAnimationFrame(mostrar);
}
