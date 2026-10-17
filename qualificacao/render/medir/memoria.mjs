// Pico de memória da árvore de processos (este Node, os Chrome e os FFmpeg que ele abriu).
// Soma o PSS (/proc/<pid>/smaps_rollup), que divide as páginas compartilhadas entre processos.
import { readFileSync, readdirSync } from 'node:fs';

function filhos() {
  const pais = new Map();
  for (const nome of readdirSync('/proc')) {
    if (!/^\d+$/.test(nome)) continue;
    try {
      const stat = readFileSync(`/proc/${nome}/stat`, 'utf8');
      const ppid = Number(stat.slice(stat.lastIndexOf(')') + 2).split(' ')[1]);
      (pais.get(ppid) ?? pais.set(ppid, []).get(ppid)).push(Number(nome));
    } catch { /* processo terminou */ }
  }
  return pais;
}

function amostra(raiz) {
  const pais = filhos(), fila = [raiz], porTipo = {};
  let total = 0;
  while (fila.length) {
    const pid = fila.pop();
    fila.push(...(pais.get(pid) ?? []));
    try {
      const pss = Number(/Pss:\s+(\d+) kB/.exec(readFileSync(`/proc/${pid}/smaps_rollup`, 'utf8'))[1]) * 1024;
      const nome = readFileSync(`/proc/${pid}/comm`, 'utf8').trim();
      const tipo = /chrom|headless/i.test(nome) ? 'chrome' : /ffmpeg/.test(nome) ? 'ffmpeg' : nome === 'node' || nome === 'MainThread' ? 'node' : nome;
      porTipo[tipo] = (porTipo[tipo] ?? 0) + pss;
      total += pss;
    } catch { /* processo terminou */ }
  }
  return { total, porTipo };
}

export function vigiarMemoria(intervaloMs = 500) {
  const pico = { total: 0, porTipo: {} };
  const medir = () => {
    const a = amostra(process.pid);
    if (a.total > pico.total) { pico.total = a.total; pico.noPico = a.porTipo; }
    for (const [k, v] of Object.entries(a.porTipo)) pico.porTipo[k] = Math.max(pico.porTipo[k] ?? 0, v);
  };
  medir();
  const relogio = setInterval(medir, intervaloMs);
  const mb = b => Math.round(b / 2 ** 20);
  return {
    parar() {
      clearInterval(relogio);
      medir();
      return { picoTotalMB: mb(pico.total), noPicoMB: Object.fromEntries(Object.entries(pico.noPico ?? {}).map(([k, v]) => [k, mb(v)])),
               picoPorTipoMB: Object.fromEntries(Object.entries(pico.porTipo).map(([k, v]) => [k, mb(v)])) };
    },
  };
}
