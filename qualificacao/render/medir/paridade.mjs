// Paridade entre prévia e exportação, quadro a quadro, sem confiar em código compartilhado:
// a prévia (página em 720p ou menos) é capturada nos mesmos instantes que o MP4 exportado é
// decodificado, e as imagens são comparadas por SSIM. Para cada amostra também se compara com
// os quadros vizinhos (±2): o melhor casamento tem de ser o próprio quadro, o que prova os tempos.
import { execFile } from 'node:child_process';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { FUSAO } from '../composicao/quadro.mjs';

const exec = promisify(execFile);
export const ESCALA_DA_PREVIA = { '1080x1920': 0.375, '1920x1080': 2 / 3 };   // 405×720 e 1280×720

// Instantes que exercitam cada recurso: cortes (quadro antes e depois), fusão, mola, esmaecimento,
// câmera em movimento, clipe acelerado e congelado, imagem com zoom, legenda; mais uma grade regular.
export function amostras(cena, maximo = 120) {
  const fps = cena.formato.fps, f = t => Math.round(t * fps), quadros = new Map();
  const add = (t, motivo) => { const q = Math.min(f(cena.duracao) - 3, Math.max(2, f(t))); if (!quadros.has(q)) quadros.set(q, motivo); };
  for (const tr of cena.trechos.slice(1)) {
    add(tr.inicio - 1 / fps, `último quadro antes de ${tr.id}`);
    add(tr.inicio + 1 / fps, `${tr.entrada} para ${tr.id}`);
    if (tr.entrada === 'fusao') add(tr.inicio + FUSAO / 2, `meio da fusão para ${tr.id}`);
    add((tr.inicio + tr.fim) / 2, `meio de ${tr.id}${tr.kenburns ? ' (zoom e panorâmica)' : ''}`);
    if (tr.clipe) { add((tr.inicio + tr.clipe.congelaEm) / 2, 'clipe acelerado'); add(tr.clipe.congelaEm + 0.5, 'clipe congelado'); }
  }
  for (const item of cena.itens.slice(0, 12)) { add(item.entra + 0.15, `mola de ${item.id}`); if (item.esmaece[0]) add(item.esmaece[0][0] + 0.3, `esmaecimento de ${item.id}`); }
  for (const m of cena.camera.slice(1, 8)) add(m.t + (m.dur ?? 1) * 0.3, 'câmera em movimento');
  for (let k = 1; k <= 10; k++) add((cena.duracao * k) / 11, 'grade regular');
  const todas = [...quadros].sort((a, b) => a[0] - b[0]).map(([quadro, motivo]) => ({ quadro, motivo }));
  // Vídeo longo: um subconjunto espalhado por todo o vídeo, sempre o mesmo.
  return todas.length <= maximo ? todas : Array.from({ length: maximo }, (_, i) => todas[Math.floor((i * todas.length) / maximo)]);
}

// Decodifica de uma vez os quadros pedidos do MP4, já reduzidos ao tamanho da prévia.
export async function quadrosDoExportado(mp4, numeros, largura, altura, pasta) {
  mkdirSync(pasta, { recursive: true });
  const unicos = [...new Set(numeros)].sort((a, b) => a - b);
  const filtro = `select='${unicos.map(n => `eq(n\\,${n})`).join('+')}',scale=${largura}:${altura}:flags=area`;
  await exec('ffmpeg', ['-v', 'error', '-nostdin', '-y', '-i', mp4, '-vf', filtro, '-fps_mode', 'passthrough', join(pasta, '%05d.png')], { maxBuffer: 1 << 26 });
  const arquivos = readdirSync(pasta).filter(a => a.endsWith('.png')).sort();
  return new Map(unicos.map((n, i) => [n, join(pasta, arquivos[i])]));
}

export async function ssim(a, b) {
  const { stderr } = await exec('ffmpeg', ['-hide_banner', '-nostdin', '-i', a, '-i', b, '-lavfi', 'ssim', '-f', 'null', '-']);
  return Number(/All:([\d.]+)/.exec(stderr)[1]);
}

export const RUIDO = 0.005;

// Compara cada captura da prévia com o quadro exportado e com os vizinhos.
export async function comparar(capturas, exportados) {
  const linhas = [];
  for (const { quadro, arquivo, motivo, t, janela = 0 } of capturas) {
    // `janela`: a prévia tocando pode ter trocado de quadro durante a captura (quadro..quadro+janela).
    const notas = {};
    for (let d = -2; d <= 2 + janela; d++) if (exportados.has(quadro + d)) notas[d] = await ssim(arquivo, exportados.get(quadro + d));
    const melhor = Number(Object.entries(notas).sort((a, b) => b[1] - a[1])[0][0]);
    const proprio = Math.max(...Object.entries(notas).filter(([d]) => d >= 0 && d <= janela).map(([, v]) => v));
    // Um erro de tempo aparece como um vizinho claramente melhor que o próprio quadro. Diferenças
    // abaixo de RUIDO são da reamostragem (câmera lenta, cena parada) e contam como empate.
    const distinguivel = Object.entries(notas).some(([d, v]) => d !== '0' && Math.abs(notas[0] - v) >= 0.01);
    linhas.push({ quadro, t, motivo, janela, ssim: proprio, vizinhos: notas, melhorDeslocamento: melhor, distinguivel,
                  coerente: proprio >= notas[melhor] - RUIDO });
  }
  const valores = linhas.map(l => l.ssim);
  return {
    amostras: linhas.length, ssimMin: Math.min(...valores), ssimMedio: Number((valores.reduce((a, b) => a + b, 0) / valores.length).toFixed(4)),
    distinguiveis: linhas.filter(l => l.distinguivel).length, incoerentes: linhas.filter(l => !l.coerente).length, linhas,
  };
}

// Áudio que a prévia tocou (blocos do worklet) recolocado na linha do tempo do vídeo.
export function audioDaPrevia(blocos, { inicioCtx, t0, taxa }) {
  blocos.sort((a, b) => a.amostra - b.amostra);
  const primeira = blocos[0].amostra, total = blocos.at(-1).amostra + blocos.at(-1).l.length - primeira;
  const l = new Float32Array(total), r = new Float32Array(total);
  for (const b of blocos) { l.set(b.l, b.amostra - primeira); r.set(b.r, b.amostra - primeira); }
  return { l, r, inicio: t0 + (primeira / taxa - inicioCtx), taxa };
}

// Lê um trecho do áudio do MP4 como float32 estéreo intercalado.
export async function audioDoExportado(mp4, inicio, duracao) {
  const { stdout } = await exec('ffmpeg', ['-v', 'error', '-nostdin', '-ss', String(inicio), '-t', String(duracao), '-i', mp4, '-vn',
                                           '-f', 'f32le', '-ac', '2', '-ar', '48000', '-'], { encoding: 'buffer', maxBuffer: 1 << 30 });
  const pcm = new Float32Array(stdout.buffer, stdout.byteOffset, stdout.length / 4);
  const n = pcm.length / 2, l = new Float32Array(n), r = new Float32Array(n);
  for (let i = 0; i < n; i++) { l[i] = pcm[2 * i]; r[i] = pcm[2 * i + 1]; }
  return { l, r };
}

// Deslocamento (em amostras) que melhor alinha a prévia ao exportado, e o resíduo depois do ganho de masterização.
export function compararAudio(previa, exportado, ganhoDb, buscaMs = 60) {
  const g = Math.pow(10, ganhoDb / 20), max = Math.round((buscaMs / 1000) * 48000);
  const n = Math.min(previa.l.length, exportado.l.length) - 2 * max;
  let melhor = 0, melhorCorr = -Infinity;
  for (let d = -max; d <= max; d += 4) {
    let s = 0;
    for (let i = max; i < n; i += 8) s += previa.l[i] * exportado.l[i + d];
    if (s > melhorCorr) { melhorCorr = s; melhor = d; }
  }
  for (let d = melhor - 4; d <= melhor + 4; d++) {
    let s = 0;
    for (let i = max; i < n; i += 2) s += previa.l[i] * exportado.l[i + d];
    if (s > melhorCorr) { melhorCorr = s; melhor = d; }
  }
  let energia = 0, residuo = 0;
  for (let i = max; i < n; i++) {
    const e = exportado.l[i + melhor], p = previa.l[i] * g;
    energia += e * e; residuo += (e - p) ** 2;
  }
  return { deslocamentoAmostras: melhor, deslocamentoMs: Number(((melhor / 48000) * 1000).toFixed(2)),
           residuoDb: Number((10 * Math.log10(residuo / energia)).toFixed(1)) };
}

export function salvarF32(arquivo, { l, r }) {
  const pcm = new Float32Array(l.length * 2);
  for (let i = 0; i < l.length; i++) { pcm[2 * i] = l[i]; pcm[2 * i + 1] = r[i]; }
  writeFileSync(arquivo, Buffer.from(pcm.buffer));
}

export const lerJson = arquivo => JSON.parse(readFileSync(arquivo, 'utf8'));
