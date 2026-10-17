// Mixagem final e medições de som pela Q46: −14 LUFS integrado ±1 LU, no máximo −1 dBTP e 48 kHz,
// medidos no arquivo final decodificado. A correção é um ganho único (modo linear), depois de
// medir; um limitador de pico só entra se o ganho levaria o pico acima do teto.
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const exec = promisify(execFile);
export const ALVO = { lufs: -14, tolerancia: 1, picoMax: -1, taxa: 48000 };
const TETO_ANTES_DO_AAC = -1.5;   // folga de 0,5 dB para o pico que o AAC acrescenta

const entradaCrua = arquivo => ['-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', arquivo];

// Lê o resumo do ebur128 e a curva de loudness momentânea (a cada 100 ms).
export async function medirLoudness(entrada, { crua = false } = {}) {
  const { stderr } = await exec('ffmpeg', ['-hide_banner', '-nostats', '-nostdin', ...(crua ? entradaCrua(entrada) : ['-i', entrada]),
                                           '-map', '0:a:0', '-af', 'ebur128=peak=true:framelog=info', '-f', 'null', '-'],
                                { maxBuffer: 1 << 30 });
  const resumo = stderr.slice(stderr.lastIndexOf('Summary:'));
  const numero = re => Number(re.exec(resumo)?.[1]);
  const momentanea = [];
  for (const m of stderr.matchAll(/t:\s*([\d.]+)\s+TARGET:[^M]*M:\s*(-?[\d.]+|-inf)/g)) momentanea.push([Number(m[1]), m[2] === '-inf' ? -120 : Number(m[2])]);
  return { lufs: numero(/I:\s*(-?[\d.]+) LUFS/), lra: numero(/LRA:\s*([\d.]+) LU/), picoReal: numero(/Peak:\s*(-?[\d.]+|-inf) dBFS/), momentanea };
}

export async function taxaDeAmostragem(arquivo) {
  const { stdout } = await exec('ffprobe', ['-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate,codec_name,channels', '-of', 'json', arquivo]);
  return JSON.parse(stdout).streams[0];
}

// Mixagem (f32le estéreo 48 kHz crua, ou um arquivo de áudio) → WAV masterizado. Devolve as medições de cada passagem.
export async function masterizar(cru, saidaWav, { crua = true } = {}) {
  const entrada = crua ? entradaCrua(cru) : ['-i', cru];
  const antes = await medirLoudness(cru, { crua });
  let ganho = ALVO.lufs - antes.lufs;
  const filtros = [];
  if (antes.picoReal + ganho > TETO_ANTES_DO_AAC) {
    const limite = Math.pow(10, (TETO_ANTES_DO_AAC - 0.5 - ganho) / 20);
    filtros.push(`alimiter=limit=${limite.toFixed(5)}:attack=2:release=60:level=false:asc=true:latency=true`);   // latency: sem atraso no som
    const { stderr } = await exec('ffmpeg', ['-hide_banner', '-nostats', '-nostdin', ...entrada, '-af', `${filtros[0]},ebur128=peak=true`, '-f', 'null', '-'], { maxBuffer: 1 << 28 });
    const resumo = stderr.slice(stderr.lastIndexOf('Summary:'));
    ganho = ALVO.lufs - Number(/I:\s*(-?[\d.]+) LUFS/.exec(resumo)[1]);
  }
  filtros.push(`volume=${ganho.toFixed(3)}dB`);
  await exec('ffmpeg', ['-v', 'error', '-nostdin', '-y', ...entrada, '-af', filtros.join(','), '-ar', '48000', '-ac', '2', '-c:a', 'pcm_f32le', saidaWav]);
  return { antes: { lufs: antes.lufs, picoReal: antes.picoReal }, ganhoDb: Number(ganho.toFixed(3)), limitador: filtros.length > 1, filtros };
}

// Confere a Q46 no arquivo final decodificado.
export async function conferirQ46(arquivoFinal) {
  const medida = await medirLoudness(arquivoFinal);
  const fluxo = await taxaDeAmostragem(arquivoFinal);
  return {
    lufs: medida.lufs, picoReal: medida.picoReal, lra: medida.lra, taxa: Number(fluxo.sample_rate), codec: fluxo.codec_name, canais: fluxo.channels,
    aprovado: Math.abs(medida.lufs - ALVO.lufs) <= ALVO.tolerancia && medida.picoReal <= ALVO.picoMax && Number(fluxo.sample_rate) === ALVO.taxa,
    momentanea: medida.momentanea,
  };
}

// Média em energia da loudness momentânea nos instantes em que há fala (palavras), e fora dela.
export function mediaNaFala(momentanea, palavras) {
  const falando = t => { // a janela momentânea tem 400 ms e termina em t
    let lo = 0, hi = palavras.length - 1;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (palavras[m][1] <= t) lo = m; else hi = m - 1; }
    return palavras[lo][1] <= t - 0.2 && t - 0.2 <= palavras[lo][2] + 0.1;
  };
  const media = vals => 10 * Math.log10(vals.reduce((s, v) => s + Math.pow(10, v / 10), 0) / Math.max(1, vals.length));
  const na = [], fora = [];
  for (const [t, m] of momentanea) if (m > -70) (falando(t) ? na : fora).push(m);
  return { naFala: Number(media(na).toFixed(2)), foraDaFala: Number(media(fora).toFixed(2)) };
}
