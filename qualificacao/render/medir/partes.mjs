// Voz × música na mixagem: renderiza só a narração e só a música pelo mesmo grafo da exportação e
// compara a loudness momentânea de cada uma nos instantes com fala (Q46: música 15–20 LU abaixo da voz).
// Uso: node medir/partes.mjs <cena.json> <pasta-das-midias> <pasta-de-saida>
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mediaNaFala, medirLoudness } from './audio.mjs';
import { lerJson } from './paridade.mjs';
import { abrirNavegador, abrirPagina } from '../navegador.mjs';
import { servir } from '../servidor.mjs';

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..');

export async function medirPartes({ cena, pastaMidia, pasta }) {
  mkdirSync(pasta, { recursive: true });
  const srv = await servir({ '/': RAIZ, '/midia/': pastaMidia });
  const nav = await abrirNavegador();
  const r = {};
  try {
    const { pagina } = await abrirPagina(nav, srv.url, { largura: 320, altura: 240 });
    await pagina.evaluate(c => motor.carregar(c, { escala: 0.1 }), cena);   // o grafo usa a cena e as mídias dela
    const duracao = Math.min(cena.duracao, 300);   // até 5 min bastam para a média
    for (const [nome, opcoes] of [['voz', { semMusica: true }], ['musica', { semNarracao: true }]]) {
      const b64 = await pagina.evaluate(([d, o]) => motor.mixar(0, d, o), [duracao, opcoes]);
      const arquivo = join(pasta, `${nome}.f32`);
      writeFileSync(arquivo, Buffer.from(b64, 'base64'));
      r[nome] = mediaNaFala((await medirLoudness(arquivo, { crua: true })).momentanea, cena.palavras);
    }
  } finally {
    await nav.close();
    await srv.fechar();
  }
  r.musicaAbaixoDaVozNaFalaLU = Number((r.voz.naFala - r.musica.naFala).toFixed(1));
  return r;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [arquivoCena, pastaMidia, pasta] = process.argv.slice(2);
  const r = await medirPartes({ cena: lerJson(arquivoCena), pastaMidia: resolve(pastaMidia), pasta: resolve(pasta) });
  writeFileSync(join(pasta, 'partes.json'), JSON.stringify(r, null, 1));
  console.log(JSON.stringify(r));
}
