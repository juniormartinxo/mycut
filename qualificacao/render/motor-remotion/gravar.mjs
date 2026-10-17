// Exportação do candidato Remotion: bundle → renderMedia (vídeo, com NVENC ou x264) e o áudio
// mixado pelo próprio Remotion num WAV à parte, masterizado pela Q46 e juntado no fim.
// Uso: node motor-remotion/gravar.mjs <cena.json> <pasta-das-midias> <saida.mp4> [--concorrencia 4] [--codificador h264_nvenc|libx264]
import { spawn } from 'node:child_process';
import { loadavg } from 'node:os';
import { readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { bundle } from '@remotion/bundler';
import { renderMedia, selectComposition } from '@remotion/renderer';
import { conferirQ46, masterizar } from '../medir/audio.mjs';
import { vigiarMemoria } from '../medir/memoria.mjs';

const AQUI = dirname(fileURLToPath(import.meta.url));
export const CHROME = join(homedir(), '.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell');

export async function empacotar(pastaMidia) {
  return bundle({ entryPoint: join(AQUI, 'src/index.jsx'), publicDir: pastaMidia, outDir: join(pastaMidia, '..', 'remotion-bundle') });
}

export async function gravarRemotion({ cena, pastaMidia, saida, concorrencia = 4, nomeDoCodificador = 'h264_nvenc', titulo = null,
                                        frameRange = null, aoProgredir = () => {} }) {
  const memoria = vigiarMemoria();
  const cargaAntes = loadavg().map(v => Number(v.toFixed(1)));
  const etapas = {}, logs = [];
  const marcar = async (nome, fn) => { const t0 = performance.now(); const r = await fn(); etapas[nome] = Number(((performance.now() - t0) / 1000).toFixed(2)); return r; };
  const relatorio = { motor: 'remotion', versao: '4.0.536', concorrencia, codificador: nomeDoCodificador, formato: `${cena.formato.largura}x${cena.formato.altura}` };
  try {
    const serveUrl = await marcar('empacotar', () => empacotar(pastaMidia));
    const inputProps = { cena, baseDaMidia: null };
    const composition = await marcar('selecionar', () => selectComposition({ serveUrl, id: 'Cena', inputProps, browserExecutable: CHROME }));
    const nvenc = nomeDoCodificador === 'h264_nvenc';
    const wavDoRemotion = saida.replace(/\.mp4$/, '.remotion.wav');
    const video = saida.replace(/\.mp4$/, '.video.mp4');
    await marcar('quadros_e_codificacao', () => renderMedia({
      composition, serveUrl, inputProps, codec: 'h264', outputLocation: video, browserExecutable: CHROME, concurrency: concorrencia,
      imageFormat: 'jpeg', jpegQuality: 92, hardwareAcceleration: nvenc ? 'required' : 'disable',
      ...(nvenc ? { videoBitrate: '16M' } : { crf: 20, x264Preset: 'veryfast' }),
      colorSpace: 'bt709', separateAudioTo: wavDoRemotion, frameRange, overwrite: true, logLevel: 'verbose',
      onLog: ({ previewString }) => { if (/ffmpeg|nvenc|libx264|encoder|Hardware/i.test(previewString)) logs.push(previewString); },
      onProgress: p => aoProgredir(p.renderedFrames, composition.durationInFrames),
    }));
    relatorio.quadros = frameRange ? frameRange[1] - frameRange[0] + 1 : composition.durationInFrames;
    relatorio.duracaoVideo = relatorio.quadros / 30;
    const wav = saida.replace(/\.mp4$/, '.mix.wav');
    relatorio.masterizacao = await marcar('audio_masterizacao', () => masterizar(wavDoRemotion, wav, { crua: false }));
    await marcar('juntar', () => new Promise((ok, erro) => {
      const meta = titulo ? ['-metadata', `title=${titulo}`, '-metadata', `comment=${titulo}`] : [];
      const ff = spawn('ffmpeg', ['-v', 'error', '-nostdin', '-y', '-i', video, '-i', wav, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
                                  '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', ...meta, '-shortest', '-movflags', '+faststart', saida], { stdio: 'inherit' });
      ff.on('close', c => (c === 0 ? ok() : erro(new Error(`mux saiu com ${c}`))));
    }));
    relatorio.q46 = await marcar('medir_q46', () => conferirQ46(saida));
    delete relatorio.q46.momentanea;
  } finally {
    relatorio.memoria = memoria.parar();
  }
  writeFileSync(saida.replace(/\.mp4$/, '.remotion.log'), logs.join('\n'));
  relatorio.carga = { antes: cargaAntes, depois: loadavg().map(v => Number(v.toFixed(1))) };
  relatorio.etapas = etapas;
  relatorio.tempoTotal = Number(Object.values(etapas).reduce((a, b) => a + b, 0).toFixed(2));
  // Segundos de vídeo por segundo de exportação: no total (como na referência Python) e só nos quadros.
  relatorio.velocidade = Number((relatorio.duracaoVideo / relatorio.tempoTotal).toFixed(3));
  relatorio.velocidadeDosQuadros = Number((relatorio.duracaoVideo / etapas.quadros_e_codificacao).toFixed(3));
  return relatorio;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { positionals, values } = parseArgs({ allowPositionals: true, options: {
    concorrencia: { type: 'string', default: '4' }, codificador: { type: 'string', default: 'h264_nvenc' }, titulo: { type: 'string' },
    quadros: { type: 'string' } } });
  const [arquivoCena, pastaMidia, saida] = positionals;
  const relatorio = await gravarRemotion({
    cena: JSON.parse(readFileSync(arquivoCena, 'utf8')), pastaMidia: resolve(pastaMidia), saida: resolve(saida),
    concorrencia: Number(values.concorrencia), nomeDoCodificador: values.codificador, titulo: values.titulo,
    frameRange: values.quadros ? values.quadros.split(':').map(Number) : null,
    aoProgredir: (f, n) => { if (f % 150 === 0) process.stderr.write(`\r${f}/${n} quadros`); },
  });
  writeFileSync(saida.replace(/\.mp4$/, '.relatorio.json'), JSON.stringify(relatorio, null, 1));
  console.log('\n' + JSON.stringify(relatorio, null, 1));
}
