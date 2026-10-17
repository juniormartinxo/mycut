// Exportação do motor HTML: várias abas do Chrome sem janela desenham quadros intercalados
// (aba k faz os quadros k, k+N, ...), o coordenador os reordena e entrega a um único FFmpeg.
// O áudio é o mesmo grafo da prévia, renderizado offline, masterizado e juntado no fim.
// Uso: node motor-html/gravar.mjs <cena.json> <pasta-das-midias> <saida.mp4> [--abas 4] [--codificador h264_nvenc|libx264]
import { spawn } from 'node:child_process';
import { loadavg } from 'node:os';
import { createWriteStream, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { conferirQ46, masterizar } from '../medir/audio.mjs';
import { vigiarMemoria } from '../medir/memoria.mjs';
import { abrirNavegador, abrirPagina, capturar } from '../navegador.mjs';
import { servir } from '../servidor.mjs';

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..');

export const CODIFICADORES = {
  h264_nvenc: ['-c:v', 'h264_nvenc', '-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', '20', '-b:v', '0', '-profile:v', 'high'],
  libx264: ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20'],
};
const COR = ['-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709'];

function codificador(saida, nome, captura, log) {
  const args = ['-hide_banner', '-nostdin', '-y', '-loglevel', 'verbose', '-f', 'image2pipe', '-c:v', captura === 'png' ? 'png' : 'mjpeg',
                '-framerate', '30', '-i', '-', ...COR, ...CODIFICADORES[nome], '-movflags', '+faststart', saida];
  const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'ignore', 'pipe'] });
  ff.stderr.pipe(createWriteStream(log));
  const fim = new Promise((ok, erro) => ff.on('close', c => (c === 0 ? ok() : erro(new Error(`ffmpeg saiu com ${c}; veja ${log}`)))));
  return { ff, fim, args };
}

const escrever = (fluxo, dados) => (fluxo.write(dados) ? null : new Promise(ok => fluxo.once('drain', ok)));

export async function gravarHtml({ cena, pastaMidia, saida, abas = 4, nomeDoCodificador = 'h264_nvenc', captura = 'jpeg', qualidade = 92,
                                    quadros = null, comAudio = true, titulo = null, aoProgredir = () => {} }) {
  const memoria = vigiarMemoria();
  const cargaAntes = loadavg().map(v => Number(v.toFixed(1)));
  const etapas = {};
  const marcar = async (nome, fn) => { const t0 = performance.now(); const r = await fn(); etapas[nome] = Number(((performance.now() - t0) / 1000).toFixed(2)); return r; };
  const total = Math.round(cena.duracao * cena.formato.fps);
  const [primeiro, ultimo] = quadros ?? [0, total];
  const srv = await servir({ '/': RAIZ, '/midia/': pastaMidia });
  const nav = await abrirNavegador();
  const relatorio = { motor: 'html', abas, codificador: nomeDoCodificador, captura, qualidade, quadros: ultimo - primeiro,
                      formato: `${cena.formato.largura}x${cena.formato.altura}`, duracaoVideo: (ultimo - primeiro) / cena.formato.fps };
  try {
    const paginas = await marcar('carregar', () => Promise.all(Array.from({ length: abas }, async () => {
      const p = await abrirPagina(nav, srv.url, { largura: cena.formato.largura, altura: cena.formato.altura });
      p.carga = await p.pagina.evaluate(c => motor.carregar(c), cena);
      await p.pagina.evaluate(() => { window.__relogio.ativo = true; });
      return p;
    })));
    relatorio.fontes = paginas[0].carga.fontes;
    relatorio.animacoesNaCarga = paginas[0].carga.animacoes;
    relatorio.transicoesNaCarga = paginas[0].carga.transicoes;

    const arquivoVideo = comAudio ? saida.replace(/\.mp4$/, '.video.mp4') : saida;
    const enc = codificador(arquivoVideo, nomeDoCodificador, captura, saida.replace(/\.mp4$/, '.ffmpeg.log'));
    relatorio.argsFfmpeg = enc.args.join(' ');
    // Quadros prontos fora de ordem esperam aqui; um único laço os escreve em sequência.
    const prontos = new Map(), esperando = [];
    let proximo = primeiro, escrevendo = false, animacoes = 0;
    const tempoPorQuadro = [];
    const escreverEmOrdem = async () => {
      if (escrevendo) return;
      escrevendo = true;
      while (prontos.has(proximo)) {
        const img = prontos.get(proximo);
        prontos.delete(proximo);
        await escrever(enc.ff.stdin, img);
        proximo++;
        if (proximo % 300 === 0) aoProgredir(proximo - primeiro, ultimo - primeiro);
        for (const ok of esperando.splice(0)) ok();
      }
      escrevendo = false;
    };
    await marcar('quadros_e_codificacao', async () => {
      await Promise.all(paginas.map(async (p, k) => {
        for (let f = primeiro + k; f < ultimo; f += abas) {
          // Uma aba não corre mais de 4 voltas à frente da escrita: a memória fica limitada.
          while (f - proximo > abas * 4) await new Promise(ok => esperando.push(ok));
          const t0 = performance.now();
          await p.pagina.evaluate(t => motor.irPara(t), f / cena.formato.fps);
          prontos.set(f, await capturar(p.cdp, { formato: captura, qualidade }));
          tempoPorQuadro.push(performance.now() - t0);
          if (f % 600 === k) animacoes = Math.max(animacoes, await p.pagina.evaluate(() => document.getAnimations().length));
          await escreverEmOrdem();
        }
      }));
      while (proximo < ultimo) {
        await escreverEmOrdem();
        if (proximo < ultimo) await new Promise(ok => esperando.push(ok));
      }
      enc.ff.stdin.end();
      await enc.fim;
    });
    relatorio.animacoesDuranteGravacao = animacoes;
    relatorio.msPorQuadroPorAba = Number((tempoPorQuadro.reduce((a, b) => a + b, 0) / tempoPorQuadro.length).toFixed(1));
    relatorio.relogio = await Promise.all(paginas.map(p => p.pagina.evaluate(() => window.__relogio.chamadas)));
    relatorio.redeBloqueada = paginas.flatMap(p => p.bloqueadas);
    relatorio.errosDaPagina = paginas.flatMap(p => p.erros);

    if (comAudio) {
      const cru = saida.replace(/\.mp4$/, '.mix.f32');
      const wav = saida.replace(/\.mp4$/, '.mix.wav');
      await marcar('audio_mixagem', async () => {
        const fluxo = createWriteStream(cru);
        const passo = 60;
        for (let t0 = primeiro / 30; t0 < ultimo / 30; t0 += passo) {
          const b64 = await paginas[0].pagina.evaluate(([a, d]) => motor.mixar(a, d), [t0, Math.min(passo, ultimo / 30 - t0)]);
          await escrever(fluxo, Buffer.from(b64, 'base64'));
        }
        await new Promise(ok => fluxo.end(ok));
      });
      relatorio.masterizacao = await marcar('audio_masterizacao', () => masterizar(cru, wav));
      await marcar('juntar', () => new Promise((ok, erro) => {
        const meta = titulo ? ['-metadata', `title=${titulo}`, '-metadata', `comment=${titulo}`] : [];
        const ff = spawn('ffmpeg', ['-v', 'error', '-nostdin', '-y', '-i', arquivoVideo, '-i', wav, '-map', '0:v:0', '-map', '1:a:0',
                                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', ...meta, '-shortest', '-movflags', '+faststart', saida],
                         { stdio: 'inherit' });
        ff.on('close', c => (c === 0 ? ok() : erro(new Error(`mux saiu com ${c}`))));
      }));
      relatorio.relogio = await Promise.all(paginas.map(p => p.pagina.evaluate(() => window.__relogio.chamadas)));
      relatorio.q46 = await marcar('medir_q46', () => conferirQ46(saida));
      delete relatorio.q46.momentanea;
    }
  } finally {
    await nav.close();
    await srv.fechar();
    relatorio.memoria = memoria.parar();
  }
  relatorio.carga = { antes: cargaAntes, depois: loadavg().map(v => Number(v.toFixed(1))) };
  relatorio.etapas = etapas;
  relatorio.tempoTotal = Number(Object.values(etapas).reduce((a, b) => a + b, 0).toFixed(2));
  relatorio.velocidade = Number((relatorio.duracaoVideo / etapas.quadros_e_codificacao).toFixed(3));
  return relatorio;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { positionals, values } = parseArgs({ allowPositionals: true, options: {
    abas: { type: 'string', default: '4' }, codificador: { type: 'string', default: 'h264_nvenc' },
    captura: { type: 'string', default: 'jpeg' }, qualidade: { type: 'string', default: '92' },
    'sem-audio': { type: 'boolean', default: false }, titulo: { type: 'string' }, quadros: { type: 'string' } } });
  const [arquivoCena, pastaMidia, saida] = positionals;
  const cena = JSON.parse(readFileSync(arquivoCena, 'utf8'));
  const relatorio = await gravarHtml({
    cena, pastaMidia: resolve(pastaMidia), saida: resolve(saida), abas: Number(values.abas), nomeDoCodificador: values.codificador,
    captura: values.captura, qualidade: Number(values.qualidade), comAudio: !values['sem-audio'], titulo: values.titulo,
    quadros: values.quadros ? values.quadros.split(':').map(Number) : null,
    aoProgredir: (f, n) => process.stderr.write(`\r${f}/${n} quadros`),
  });
  writeFileSync(saida.replace(/\.mp4$/, '.relatorio.json'), JSON.stringify(relatorio, null, 1));
  console.log('\n' + JSON.stringify(relatorio, null, 1));
}
