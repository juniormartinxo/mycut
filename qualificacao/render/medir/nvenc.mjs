// Encode NVENC real no WSL, com o caminho verificado durante a execução (não só a lista de encoders):
// 1) bibliotecas mapeadas no processo FFmpeg enquanto codifica (/proc/<pid>/maps);
// 2) uso do codificador da GPU amostrado pelo nvidia-smi durante o encode;
// 3) mensagens de inicialização do NVENC no log e a marca do codificador no arquivo.
// Compara tempo e qualidade (SSIM contra a fonte) com libx264 nos mesmos quadros.
// Uso: node medir/nvenc.mjs <fonte.mp4> <pasta-de-saida>
import { execFile, spawn } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import { CODIFICADORES } from '../motor-html/gravar.mjs';

const exec = promisify(execFile);

function amostrarGpu() {
  const nvsmi = spawn('nvidia-smi', ['--query-gpu=timestamp,utilization.encoder,utilization.gpu,encoder.stats.sessionCount,encoder.stats.averageFps',
                                     '--format=csv,noheader,nounits', '-lms', '200']);
  let texto = '';
  nvsmi.stdout.on('data', d => { texto += d; });
  return { parar: () => { nvsmi.kill(); return texto.trim().split('\n').map(l => l.split(',').map(v => v.trim())); } };
}

async function codificar(fonte, saida, nome) {
  const gpu = amostrarGpu();
  const args = ['-hide_banner', '-nostdin', '-y', '-loglevel', 'verbose', '-benchmark', '-i', fonte, '-an', ...CODIFICADORES[nome], '-pix_fmt', 'yuv420p', saida];
  const ff = spawn('ffmpeg', args);
  let log = '';
  ff.stderr.on('data', d => { log += d; });
  // Bibliotecas que o processo carregou de fato, lidas enquanto ele codifica.
  const mapas = new Set();
  const leitor = setInterval(() => {
    try {
      for (const linha of readFileSync(`/proc/${ff.pid}/maps`, 'utf8').split('\n')) {
        const m = /\s(\/\S*(?:nvidia|cuda|nvcuvid|dxcore|d3d12|x264)\S*)$/.exec(linha);
        if (m) mapas.add(m[1]);
      }
    } catch { /* terminou */ }
  }, 100);
  const t0 = performance.now();
  const codigo = await new Promise(ok => ff.on('close', ok));
  const segundos = (performance.now() - t0) / 1000;
  clearInterval(leitor);
  const amostras = gpu.parar().filter(a => a.length >= 5);
  if (codigo !== 0) throw new Error(`ffmpeg ${nome} saiu com ${codigo}`);
  writeFileSync(saida.replace(/\.mp4$/, '.log'), log);
  const { stdout } = await exec('ffprobe', ['-v', 'error', '-show_entries', 'stream_tags=encoder:stream=nb_frames', '-of', 'json', saida]);
  const fluxo = JSON.parse(stdout).streams[0];
  const { stderr } = await exec('ffmpeg', ['-hide_banner', '-nostdin', '-i', saida, '-i', fonte, '-lavfi', '[0:v][1:v]ssim', '-f', 'null', '-']);
  const usoEnc = amostras.map(a => Number(a[1]));
  return {
    codificador: nome, segundos: Number(segundos.toFixed(2)), quadros: Number(fluxo.nb_frames), qps: Number((fluxo.nb_frames / segundos).toFixed(1)),
    bench: /bench: (utime=\S+ stime=\S+ rtime=\S+)/.exec(log)?.[1] ?? null,
    marcaNoArquivo: fluxo.tags?.encoder ?? null, ssimContraFonte: Number(/All:([\d.]+)/.exec(stderr)[1]),
    bibliotecasCarregadas: [...mapas].sort(),
    logNvenc: log.split('\n').filter(l => /nvenc|cuda|NVENC/i.test(l) && !/^\s*(Stream|encoder)/.test(l)).slice(0, 12),
    gpuDuranteEncode: { amostras: amostras.length, usoDoCodificadorMax: Math.max(0, ...usoEnc),
                        usoDoCodificadorMedio: Number((usoEnc.reduce((a, b) => a + b, 0) / Math.max(1, usoEnc.length)).toFixed(1)),
                        sessoesMax: Math.max(0, ...amostras.map(a => Number(a[3]) || 0)) },
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [fonte, pasta] = process.argv.slice(2).map(p => resolve(p));
  mkdirSync(pasta, { recursive: true });
  const r = { fonte, nvenc: await codificar(fonte, join(pasta, 'nvenc.mp4'), 'h264_nvenc'), x264: await codificar(fonte, join(pasta, 'x264.mp4'), 'libx264') };
  writeFileSync(join(pasta, 'nvenc.json'), JSON.stringify(r, null, 1));
  console.log(JSON.stringify(r, null, 1));
}
