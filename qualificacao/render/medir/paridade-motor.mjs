// Paridade de um candidato: prévia (720p ou menos) × MP4 exportado, parada e tocando, imagem e som.
// HTML: a prévia é a página do motor; Remotion: o <Player> com a mesma composição.
// Uso: node medir/paridade-motor.mjs <html|remotion> <cena.json> <pasta-das-midias> <exportado.mp4> <pasta-de-saida>
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { setTimeout as esperar } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { ganhoDaMusica } from '../composicao/mixagem.mjs';
import { medirLoudness } from './audio.mjs';
import { ESCALA_DA_PREVIA, amostras, audioDaPrevia, audioDoExportado, comparar, compararAudio, lerJson, quadrosDoExportado, salvarF32 } from './paridade.mjs';
import { abrirNavegador, abrirPagina } from '../navegador.mjs';
import { servir } from '../servidor.mjs';

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const percentil = (v, p) => [...v].sort((a, b) => a - b)[Math.min(v.length - 1, Math.floor(p * v.length))];

const PAGINA = { html: '/motor-html/index.html', remotion: '/motor-remotion/previa.html' };

export async function paridade({ motor, cena, pastaMidia, exportado, pasta, ganhoDb }) {
  const { largura: W, altura: H, fps } = cena.formato;
  const escala = ESCALA_DA_PREVIA[`${W}x${H}`];
  const w = Math.round(W * escala), h = Math.round(H * escala);
  mkdirSync(join(pasta, 'previa'), { recursive: true });
  const srv = await servir({ '/': RAIZ, '/midia/': pastaMidia, '/remotion-previa/': join(RAIZ, '.saida/remotion-previa') });
  const nav = await abrirNavegador();
  const resultado = { motor, previa: `${w}x${h}` };
  try {
    const { pagina, bloqueadas, erros } = await abrirPagina(nav, srv.url, { largura: w, altura: h, caminho: PAGINA[motor] });
    resultado.carga = await pagina.evaluate(([c, e]) => motor.carregar(c, { escala: e, comAudio: true }), [cena, escala]);
    const foto = async arquivo => pagina.screenshot({ path: arquivo, clip: { x: 0, y: 0, width: w, height: h } });

    // 1. Prévia parada: cada amostra vai direto ao instante (busca) e é capturada.
    const lista = amostras(cena), capturas = [], buscas = [];
    for (const a of lista) {
      const t0 = performance.now();
      await pagina.evaluate(t => motor.irPara(t), a.quadro / fps);
      buscas.push(performance.now() - t0);
      const arquivo = join(pasta, 'previa', `${a.quadro}.png`);
      await foto(arquivo);
      capturas.push({ ...a, t: a.quadro / fps, arquivo });
    }

    // 2. Prévia tocando com a narração. HTML: o quadro desenhado fica na tela para a captura, o som segue.
    //    Remotion: lê o quadro do Player antes e depois da captura e só usa a captura se não mudou.
    const desde = Math.max(0, cena.trechos[1].inicio - 3), janela = Math.min(20, cena.duracao - desde - 1);
    await pagina.evaluate(t => motor.tocar(t, { capturar: true }), desde);
    const tocando = [], volumes = [];
    const inicio = performance.now();
    for (let k = 0; k < 12 && tocando.length < 10; k++) {
      await esperar(1400);
      const arquivo = join(pasta, 'previa', `tocando-${k}.png`);
      if (motor === 'html') {
        const t = await pagina.evaluate(() => motor.segurarProximo());
        await foto(arquivo);
        await pagina.evaluate(() => motor.soltar());
        tocando.push({ quadro: Math.round(t * fps), t, arquivo, motivo: 'prévia tocando' });
      } else {
        const antes = await pagina.evaluate(() => { motor.marcar(); return motor.quadroAtual(); });
        await foto(arquivo);
        const depois = await pagina.evaluate(() => motor.quadroAtual());
        volumes.push({ quadro: antes, volumes: await pagina.evaluate(() => motor.volumes()) });
        if (depois - antes <= 2) tocando.push({ quadro: antes, janela: depois - antes, t: antes / fps, arquivo, motivo: 'prévia tocando' });
      }
    }
    await esperar(Math.max(0, janela * 1000 - (performance.now() - inicio)));
    const registro = motor === 'html' ? await pagina.evaluate(() => motor.estadoDaPrevia.registro) : null;
    const captura = await pagina.evaluate(() => motor.capturaDeAudio());
    const atrasosDoClipe = motor === 'html' ? await pagina.evaluate(() => motor.estadoDaPrevia.atrasosDoClipe ?? 0) : null;
    await pagina.evaluate(() => motor.pausar());
    if (motor === 'remotion' && captura) {
      // Relógio do áudio → tempo do vídeo pelo quadro que o Player mostrava em cada marca (mediana).
      const desvios = captura.marcas.map(([ctx, q]) => q / fps - ctx).sort((a, b) => a - b);
      Object.assign(captura, { inicioCtx: 0, t0: desvios[Math.floor(desvios.length / 2)] });
      resultado.volumesNoPlayer = volumes.map(v => ({ quadro: v.quadro, esperadoMusica: Number(Math.pow(10, ganhoDaMusica(cena, v.quadro / fps) / 20).toFixed(4)),
                                                       elementos: v.volumes.filter(a => !a.paused).map(a => Number(a.volume.toFixed(4))) }));
    }

    // 3. Quadros do exportado nos mesmos instantes e vizinhos; comparação.
    const numeros = [...capturas, ...tocando].flatMap(c => [-2, -1, 0, 1, 2, 3, 4].map(d => c.quadro + d));
    const exportados = await quadrosDoExportado(exportado, numeros, w, h, join(pasta, 'exportado'));
    resultado.parada = await comparar(capturas, exportados);
    resultado.tocando = await comparar(tocando, exportados);
    resultado.busca = { amostras: buscas.length, msMediana: Math.round(percentil(buscas, 0.5)), msP95: Math.round(percentil(buscas, 0.95)), msMax: Math.round(Math.max(...buscas)) };
    const intervalos = registro ? registro.slice(1).map(([a], i) => a - registro[i][0]) : [];
    if (registro) resultado.reproducao = {
      segundos: Number((registro.at(-1)[1] - registro[0][1]).toFixed(2)), quadrosDesenhados: registro.length,
      intervaloMsMediana: Number(percentil(intervalos, 0.5).toFixed(1)), intervaloMsP95: Number(percentil(intervalos, 0.95).toFixed(1)),
      intervaloMsMax: Number(Math.max(...intervalos).toFixed(1)), acimaDe50ms: intervalos.filter(i => i > 50).length, atrasosDoClipe,
    };

    // 4. Som: o que a prévia tocou × o áudio do arquivo final, no mesmo trecho da linha do tempo.
    if (captura?.blocos.length) {
      const previa = audioDaPrevia(captura.blocos, captura);
      const dur = previa.l.length / previa.taxa;
      const exp = await audioDoExportado(exportado, previa.inicio, dur);
      resultado.som = { trechoInicio: Number(previa.inicio.toFixed(3)), segundos: Number(dur.toFixed(2)), ...compararAudio(previa, exp, ganhoDb) };
      salvarF32(join(pasta, 'previa-audio.f32'), previa);
      salvarF32(join(pasta, 'exportado-audio.f32'), exp);
      const mp = await medirLoudness(join(pasta, 'previa-audio.f32'), { crua: true });
      const me = await medirLoudness(join(pasta, 'exportado-audio.f32'), { crua: true });
      const difs = [];
      for (let i = 4; i < Math.min(mp.momentanea.length, me.momentanea.length); i++) {
        if (me.momentanea[i][1] > -50) difs.push(me.momentanea[i][1] - (mp.momentanea[i][1] + ganhoDb));
      }
      resultado.som.loudnessMomentanea = { pontos: difs.length, difMaxLU: Number(Math.max(...difs.map(Math.abs)).toFixed(2)),
                                           difMediaLU: Number((difs.reduce((a, b) => a + b, 0) / difs.length).toFixed(2)) };
    } else {
      resultado.som = { erro: 'a prévia não entregou áudio capturado' };
    }
    resultado.redeBloqueada = bloqueadas;
    resultado.errosDaPagina = erros;
  } finally {
    await nav.close();
    await srv.fechar();
  }
  return resultado;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [motor, arquivoCena, pastaMidia, exportado, pasta] = process.argv.slice(2);
  const relatorioExportacao = lerJson(exportado.replace(/\.mp4$/, '.relatorio.json'));
  const r = await paridade({ motor, cena: lerJson(arquivoCena), pastaMidia: resolve(pastaMidia), exportado: resolve(exportado), pasta: resolve(pasta),
                             ganhoDb: relatorioExportacao.masterizacao.ganhoDb });
  writeFileSync(join(pasta, 'paridade.json'), JSON.stringify(r, null, 1));
  const resumo = { ...r, parada: { ...r.parada, linhas: undefined }, tocando: { ...r.tocando, linhas: undefined } };
  console.log(JSON.stringify(resumo, null, 1));
}
