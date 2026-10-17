// Paridade do motor atual: a prévia do app (MP4 540×960 a 24 qps) × o arquivo final (1080×1920 a 30 qps).
// Só compara instantes que existem nas duas grades (múltiplos de 1/6 s) e confere os vizinhos do final.
// Uso: node medir/paridade-python.mjs <python-preview.mp4> <python-final.mp4> <duração> <pasta-de-saida>
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { comparar, quadrosDoExportado } from './paridade.mjs';

export async function paridadePython({ previa, final, duracao, pasta }) {
  mkdirSync(pasta, { recursive: true });
  const instantes = [];
  for (let k = 3; k / 6 < duracao - 1; k += 7) instantes.push(k / 6);
  const daPrevia = await quadrosDoExportado(previa, instantes.map(t => Math.round(t * 24)), 540, 960, join(pasta, 'previa'));
  const finais = instantes.flatMap(t => [-2, -1, 0, 1, 2].map(d => Math.round(t * 30) + d));
  const doFinal = await quadrosDoExportado(final, finais, 540, 960, join(pasta, 'final'));
  const capturas = instantes.map(t => ({ quadro: Math.round(t * 30), t, arquivo: daPrevia.get(Math.round(t * 24)), motivo: 'grade comum 24/30 qps' }));
  return { motor: 'python-ffmpeg (atual)', previa: '540x960 a 24 qps', parada: await comparar(capturas, doFinal) };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [previa, final, duracao, pasta] = process.argv.slice(2);
  const r = await paridadePython({ previa: resolve(previa), final: resolve(final), duracao: Number(duracao), pasta: resolve(pasta) });
  writeFileSync(join(pasta, 'paridade.json'), JSON.stringify(r, null, 1));
  console.log(JSON.stringify({ ...r, parada: { ...r.parada, linhas: undefined } }, null, 1));
}
