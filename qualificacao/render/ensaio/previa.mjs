// Resposta da prévia no vídeo longo: carga, buscas por todo o vídeo e reprodução no início, meio e fim.
// Uso: node ensaio/previa.mjs <cena.json> <pasta-das-midias> <saida.json>
import { writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { setTimeout as esperar } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { vigiarMemoria } from '../medir/memoria.mjs';
import { ESCALA_DA_PREVIA, lerJson } from '../medir/paridade.mjs';
import { abrirNavegador, abrirPagina } from '../navegador.mjs';
import { servir } from '../servidor.mjs';

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const percentil = (v, p) => [...v].sort((a, b) => a - b)[Math.min(v.length - 1, Math.floor(p * v.length))];
const resumo = v => ({ n: v.length, mediana: Number(percentil(v, 0.5).toFixed(1)), p95: Number(percentil(v, 0.95).toFixed(1)), max: Number(Math.max(...v).toFixed(1)) });

export async function respostaDaPrevia({ cena, pastaMidia }) {
  const { largura: W, altura: H } = cena.formato;
  const escala = ESCALA_DA_PREVIA[`${W}x${H}`];
  const memoria = vigiarMemoria(250);
  const srv = await servir({ '/': RAIZ, '/midia/': pastaMidia });
  const nav = await abrirNavegador();
  const r = { previa: `${Math.round(W * escala)}x${Math.round(H * escala)}`, duracao: cena.duracao };
  try {
    const { pagina, bloqueadas, erros } = await abrirPagina(nav, srv.url, { largura: Math.round(W * escala), altura: Math.round(H * escala) });
    let t0 = performance.now();
    await pagina.evaluate(([c, e]) => motor.carregar(c, { escala: e, comAudio: true }), [cena, escala]);
    r.cargaComAudioMs = Math.round(performance.now() - t0);

    // Buscas: posições espalhadas pelo vídeo inteiro, em ordem embaralhada (gerador fixo, repetível).
    let semente = 7;
    const aleatorio = () => ((semente = (semente * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
    const buscas = [];
    for (let k = 0; k < 60; k++) {
      const t = aleatorio() * (cena.duracao - 1);
      t0 = performance.now();
      await pagina.evaluate(x => motor.irPara(x), t);
      await pagina.evaluate(() => new Promise(ok => requestAnimationFrame(() => requestAnimationFrame(ok))));
      buscas.push(performance.now() - t0);
    }
    r.buscaAtePintarMs = resumo(buscas);

    // Reprodução: 12 s em três pontos; intervalos entre quadros desenhados e atrasos do clipe.
    r.reproducao = [];
    for (const desde of [5, cena.duracao / 2, cena.duracao - 20]) {
      t0 = performance.now();
      await pagina.evaluate(t => motor.tocar(t), desde);
      await esperar(12000);
      const registro = await pagina.evaluate(() => motor.estadoDaPrevia.registro);
      const pedidoEm = await pagina.evaluate(() => motor.estadoDaPrevia.pedidoEm);
      const atrasos = await pagina.evaluate(() => motor.estadoDaPrevia.atrasosDoClipe ?? 0);
      await pagina.evaluate(() => { motor.pausar(); motor.estadoDaPrevia.atrasosDoClipe = 0; });
      const intervalos = registro.slice(1).map(([a], i) => a - registro[i][0]);
      r.reproducao.push({ desde: Number(desde.toFixed(1)), primeiroQuadroMs: Math.round(registro[0][0] - pedidoEm),
                          segundosDeVideo: Number((registro.at(-1)[1] - registro[0][1]).toFixed(2)), quadrosDesenhados: registro.length,
                          intervaloMs: resumo(intervalos), acimaDe50ms: intervalos.filter(i => i > 50).length, atrasosDoClipe: atrasos });
    }
    r.redeBloqueada = bloqueadas;
    r.errosDaPagina = erros;
  } finally {
    await nav.close();
    await srv.fechar();
    r.memoria = memoria.parar();
  }
  return r;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [arquivoCena, pastaMidia, saida] = process.argv.slice(2);
  const r = await respostaDaPrevia({ cena: lerJson(arquivoCena), pastaMidia: resolve(pastaMidia) });
  writeFileSync(saida, JSON.stringify(r, null, 1));
  console.log(JSON.stringify(r, null, 1));
}
