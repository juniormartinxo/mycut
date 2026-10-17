// Composição representativa da qualificação (MYC-11), descrita como dados.
// Cada capítulo de fala ocupa uma região do mapa e repete o mesmo roteiro visual:
// mapa com câmera e cartões → corte para imagem com zoom e panorâmica → fusão para um
// clipe acelerado que congela, com cartão de vidro por cima → corte de volta ao mapa,
// que recua para mostrar o capítulo. Todos os tempos saem de inícios de palavras.

export const FORMATOS = {
  '9:16': { largura: 1080, altura: 1920, fps: 30 },
  '16:9': { largura: 1920, altura: 1080, fps: 30 },
};

// Posições dentro da região do capítulo (frações) e larguras dos cartões, por formato.
const ARRANJO = {
  '9:16': { colunas: 2, titulo: [0.5, 0.14, 900], cartoes: [[0.27, 0.42, 600], [0.73, 0.42, 600], [0.5, 0.66, 760]],
            final: [0.5, 0.87, 900], vidro: [540, 420, 900], legenda: { x: 90, y: 1440, largura: 900, altura: 190 } },
  '16:9': { colunas: 4, titulo: [0.5, 0.14, 1200], cartoes: [[0.19, 0.5, 680], [0.5, 0.5, 680], [0.81, 0.5, 680]],
            final: [0.5, 0.84, 1200], vidro: [1380, 250, 820], legenda: { x: 260, y: 880, largura: 1400, altura: 150 } },
};

const REGIAO = 1.3;
const DESTAQUES = ['teste', 'vídeo', 'quadro', 'tempo', 'motor', 'prévia', 'câmera', 'música', 'volume', 'mapa'];
const limpa = w => w.replace(/[^\p{L}\p{N}-]/gu, '');

export function montarCena({ formato, palavras, duracao, midia, marcaDeTeste = null, palavrasPorCapitulo = 150 }) {
  const quadro = FORMATOS[formato];
  const arranjo = ARRANJO[formato];
  const regiao = { largura: Math.round(quadro.largura * REGIAO), altura: Math.round(quadro.altura * REGIAO) };
  const capitulos = Math.max(1, Math.round(palavras.length / palavrasPorCapitulo));
  const linhas = Math.ceil(capitulos / arranjo.colunas);
  const colunas = Math.min(capitulos, arranjo.colunas);
  const mapa = { largura: colunas * regiao.largura, altura: linhas * regiao.altura };
  const visao = Math.min(quadro.largura / regiao.largura, quadro.altura / regiao.altura) * 0.96;

  const trechos = [], itens = [], camera = [];
  for (let k = 0; k < capitulos; k++) {
    const a = Math.floor(k * palavras.length / capitulos), b = Math.floor((k + 1) * palavras.length / capitulos);
    const em = fracao => palavras[Math.min(b - 1, a + Math.round(fracao * (b - a)))][1];
    const ox = (k % arranjo.colunas) * regiao.largura, oy = Math.floor(k / arranjo.colunas) * regiao.altura;
    const noMapa = ([fx, fy]) => ({ x: Math.round(ox + fx * regiao.largura), y: Math.round(oy + fy * regiao.altura) });
    const texto = (fracao, n) => palavras.slice(a + Math.round(fracao * (b - a)), a + Math.round(fracao * (b - a)) + n).map(p => limpa(p[0])).join(' ');
    const inicio = k === 0 ? 0 : em(0), fim = k === capitulos - 1 ? duracao : palavras[b][1];
    const cortes = [em(0.45), em(0.6), em(0.78)];

    trechos.push(
      { id: `c${k}-mapa`, tipo: 'mapa', inicio, fim: cortes[0], entrada: 'corte' },
      { id: `c${k}-imagem`, tipo: 'imagem', inicio: cortes[0], fim: cortes[1], entrada: 'corte',
        imagem: midia.imagens[k % midia.imagens.length],
        kenburns: { de: { escala: 1, x: 0, y: 0 }, ate: { escala: 1.25, x: Math.round(-0.06 * quadro.largura), y: Math.round(0.03 * quadro.altura) } } },
      { id: `c${k}-clipe`, tipo: 'clipe', inicio: cortes[1], fim: cortes[2], entrada: 'fusao',
        clipe: { arquivo: midia.clipe.arquivo, quadros: midia.clipe.quadros, fps: midia.clipe.fps, total: midia.clipe.total,
                 inicioNoClipe: 0, velocidade: 2,
                 congelaEm: congelamento(palavras, a, b, cortes[1], cortes[2], midia.clipe.duracao / 2 - 0.2) } },
      { id: `c${k}-volta`, tipo: 'mapa', inicio: cortes[2], fim, entrada: 'corte' },
    );

    const fases = [0, 0.1, 0.2, 0.32];
    const posicoes = [arranjo.titulo, ...arranjo.cartoes];
    posicoes.forEach((pos, i) => itens.push({
      id: `c${k}-i${i}`, trecho: 'mapa', tipo: i === 0 ? 'titulo' : 'cartao', ...noMapa(pos), largura: pos[2],
      entra: em(fases[i]), esmaece: [[i < 3 ? em(fases[i + 1]) : cortes[2], null]],
      brilho: true, vidro: i === 3, tom: (k + i) % 4 + 1,
      titulo: i === 0 ? `Capítulo ${k + 1}` : texto(fases[i], 3), texto: texto(fases[i] + 0.02, 6),
    }));
    itens.push({ id: `c${k}-final`, trecho: 'mapa', tipo: 'cartao', ...noMapa(arranjo.final), largura: arranjo.final[2],
                 entra: em(0.8), esmaece: k < capitulos - 1 ? [[palavras[b][1], null]] : [], brilho: true, vidro: false,
                 tom: (k + 2) % 4 + 1, titulo: texto(0.8, 3), texto: texto(0.82, 6) });
    itens.push({ id: `c${k}-vidro`, trecho: `c${k}-clipe`, tipo: 'cartao', x: arranjo.vidro[0], y: arranjo.vidro[1],
                 largura: arranjo.vidro[2], entra: em(0.62), esmaece: [], brilho: true, vidro: true, tom: 2,
                 titulo: texto(0.62, 3), texto: 'clipe 2× até congelar' });

    const centro = noMapa([0.5, 0.5]);
    if (k === 0) camera.push({ t: 0, ...focoEm(noMapa(arranjo.titulo), 1.15) });
    else camera.push({ t: inicio, ...focoEm(noMapa(arranjo.titulo), 1.15), dur: 1.6 });
    arranjo.cartoes.forEach((pos, i) => camera.push({ t: em(fases[i + 1]), ...focoEm(noMapa(pos), 1.2), dur: 0.9 }));
    camera.push({ t: cortes[2], ...focoEm(noMapa(arranjo.final), 1.1), dur: 0.01 });
    camera.push({ t: em(0.9), ...focoEm(centro, visao), dur: 1.4 });
  }

  return {
    formato: quadro, duracao, mapa, palavras, trechos, itens, camera, marcaDeTeste,
    fundo: { cor1: '#0F172A', cor2: '#05080E', grade: 'rgba(59,130,246,.12)' },
    legenda: { palavrasPorVez: 3, destaques: DESTAQUES, ...arranjo.legenda },
    narracao: { arquivo: midia.narracao ?? null },
    musica: { arquivo: midia.musica ?? null, ganhoFala: -18, ganhoPausa: -9, pausaMinima: 0.6, rampa: 0.3 },
  };
}

const focoEm = ({ x, y }, zoom) => ({ x, y, zoom: Math.round(zoom * 1e4) / 1e4 });

// O congelamento cai na última palavra antes de o clipe (acelerado) acabar e depois de um
// terço do trecho, para que se veja o movimento antes da parada.
function congelamento(palavras, a, b, inicio, fim, folga) {
  const limite = Math.min(fim - 0.1, inicio + folga);
  let escolhido = inicio + Math.min(folga, (fim - inicio) / 2);
  for (let i = a; i < b; i++) {
    const t = palavras[i][1];
    if (t > inicio + (fim - inicio) / 3 && t <= limite) escolhido = t;
  }
  return escolhido;
}
