// Determinismo do motor HTML: os mesmos quadros, capturados sem perda (PNG) em ordem crescente, em ordem
// embaralhada e num navegador novo, têm de dar exatamente os mesmos pixels.
// Uso: node medir/determinismo.mjs <cena.json> <pasta-das-midias> [quadros]
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { amostras, lerJson } from './paridade.mjs';
import { abrirNavegador, abrirPagina, capturar } from '../navegador.mjs';
import { servir } from '../servidor.mjs';

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..');

async function rodada(srv, cena, ordem) {
  const nav = await abrirNavegador();
  try {
    const { pagina, cdp } = await abrirPagina(nav, srv.url, { largura: cena.formato.largura, altura: cena.formato.altura });
    await pagina.evaluate(c => motor.carregar(c), cena);
    const hashes = new Map();
    for (const q of ordem) {
      await pagina.evaluate(t => motor.irPara(t), q / cena.formato.fps);
      const png = await capturar(cdp, { formato: 'png' });
      hashes.set(q, { hash: createHash('sha256').update(png).digest('hex'), png });
    }
    return hashes;
  } finally {
    await nav.close();
  }
}

export async function determinismo({ cena, pastaMidia, maximo = 40 }) {
  const quadros = amostras(cena, maximo).map(a => a.quadro);
  const embaralhados = [...quadros].sort((a, b) => ((a * 7919) % 101) - ((b * 7919) % 101));
  const srv = await servir({ '/': RAIZ, '/midia/': pastaMidia });
  try {
    const a = await rodada(srv, cena, quadros), b = await rodada(srv, cena, embaralhados), c = await rodada(srv, cena, [...quadros].reverse());
    const h = (r, q) => r.get(q).hash;
    const iguais = quadros.filter(q => h(a, q) === h(b, q) && h(a, q) === h(c, q));
    // Onde diferem: quantos pixels e de quanto, entre a rodada crescente e a invertida.
    const pasta = mkdtempSync(join(tmpdir(), 'determinismo-'));
    const diferentes = quadros.filter(q => !iguais.includes(q)).map(q => {
      const [x, y] = [a, c].map((r, i) => { const f = join(pasta, `${q}-${i}.png`); writeFileSync(f, r.get(q).png); return f; });
      const cru = f => execFileSync('ffmpeg', ['-v', 'error', '-i', f, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 1 << 26 });
      const [p1, p2] = [cru(x), cru(y)];
      let pixels = 0, maximo = 0;
      for (let i = 0; i < p1.length; i += 3) {
        const d = Math.max(Math.abs(p1[i] - p2[i]), Math.abs(p1[i + 1] - p2[i + 1]), Math.abs(p1[i + 2] - p2[i + 2]));
        if (d) { pixels++; maximo = Math.max(maximo, d); }
      }
      return { quadro: q, pixelsDiferentes: pixels, diferencaMaxima: maximo };
    });
    return { quadros: quadros.length, pixelsPorQuadro: cena.formato.largura * cena.formato.altura, identicosNasTresRodadas: iguais.length, diferentes };
  } finally {
    await srv.fechar();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [arquivoCena, pastaMidia, maximo] = process.argv.slice(2);
  console.log(JSON.stringify(await determinismo({ cena: lerJson(arquivoCena), pastaMidia: resolve(pastaMidia), maximo: Number(maximo ?? 40) })));
}
