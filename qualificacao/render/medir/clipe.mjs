// Conferência do clipe no arquivo exportado, independente do motor: o contador gravado em cada
// quadro do clipe-fonte é recortado do quadro exportado e comparado com os quadros-fonte vizinhos.
// O melhor casamento tem de ser o quadro que velocidade e congelamento mandam mostrar.
// Uso: node medir/clipe.mjs <cena.json> <pasta-das-midias> <exportado.mp4> <pasta-de-saida>
import { execFile } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import { FUSAO, quadroEm } from '../composicao/quadro.mjs';
import { lerJson, ssim } from './paridade.mjs';

const exec = promisify(execFile);
const FONTE = { largura: 1280, altura: 720 };
const RECORTE = { x: 440, y: 280, largura: 400, altura: 190 };   // o contador, no centro do clipe-fonte

export async function conferirClipe({ cena, pastaMidia, exportado, pasta }) {
  mkdirSync(pasta, { recursive: true });
  const { largura: W, altura: H, fps } = cena.formato;
  const s = Math.max(W / FONTE.largura, H / FONTE.altura);            // object-fit: cover
  const ox = (FONTE.largura * s - W) / 2, oy = (FONTE.altura * s - H) / 2;
  const r = { x: Math.round(RECORTE.x * s - ox), y: Math.round(RECORTE.y * s - oy), w: Math.round(RECORTE.largura * s), h: Math.round(RECORTE.altura * s) };
  const linhas = [];
  for (const tr of cena.trechos.filter(t => t.tipo === 'clipe')) {
    const de = Math.ceil((tr.inicio + FUSAO) * fps), ate = Math.floor(tr.fim * fps) - 1;
    for (let k = 0; k < 8; k++) {
      const quadro = Math.round(de + ((ate - de) * k) / 7), q = quadroEm(cena, quadro / fps);
      linhas.push({ quadro, esperado: Math.min(tr.clipe.total - 1, Math.floor(q.clipe.tempo * tr.clipe.fps + 1e-6)), congelado: q.clipe.congelado });
    }
  }
  const filtro = `select='${linhas.map(l => `eq(n\\,${l.quadro})`).join('+')}',crop=${r.w}:${r.h}:${r.x}:${r.y},scale=400:190:flags=area`;
  await exec('ffmpeg', ['-v', 'error', '-nostdin', '-y', '-i', exportado, '-vf', filtro, '-fps_mode', 'passthrough', join(pasta, 'exp-%03d.png')]);
  for (const [i, l] of linhas.entries()) {
    const exp = join(pasta, `exp-${String(i + 1).padStart(3, '0')}.png`);
    l.notas = {};
    for (let d = -2; d <= 2; d++) {
      const k = l.esperado + d;
      if (k < 0 || k >= 240) continue;
      const fonte = join(pasta, `fonte-${k}.png`);
      await exec('ffmpeg', ['-v', 'error', '-nostdin', '-y', '-i', join(pastaMidia, 'clipe-quadros', `${String(k).padStart(4, '0')}.jpg`),
                            '-vf', `crop=${RECORTE.largura}:${RECORTE.altura}:${RECORTE.x}:${RECORTE.y}`, fonte]);
      l.notas[d] = await ssim(exp, fonte);
    }
    l.deslocamento = Number(Object.entries(l.notas).sort((a, b) => b[1] - a[1])[0][0]);
  }
  return { amostras: linhas.length, quadroCerto: linhas.filter(l => l.deslocamento === 0).length,
           deslocamentos: linhas.map(l => l.deslocamento), linhas };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [arquivoCena, pastaMidia, exportado, pasta] = process.argv.slice(2);
  const r = await conferirClipe({ cena: lerJson(arquivoCena), pastaMidia: resolve(pastaMidia), exportado: resolve(exportado), pasta: resolve(pasta) });
  writeFileSync(join(pasta, 'clipe.json'), JSON.stringify(r, null, 1));
  console.log(JSON.stringify({ ...r, linhas: r.linhas.map(l => [l.quadro, l.esperado, l.congelado, l.deslocamento]) }));
}
