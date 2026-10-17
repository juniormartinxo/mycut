import { test } from 'node:test';
import assert from 'node:assert/strict';
import { quadroEm } from '../composicao/quadro.mjs';

const base = (extra = {}) => ({
  formato: { largura: 1080, altura: 1920, fps: 30 },
  duracao: 20,
  palavras: [],
  camera: [{ t: 0, x: 540, y: 960, zoom: 1 }],
  itens: [],
  trechos: [
    { id: 'a', tipo: 'mapa', inicio: 0, fim: 10 },
    { id: 'b', tipo: 'imagem', inicio: 10, fim: 20, entrada: 'corte' },
  ],
  ...extra,
});

test('um corte troca o trecho visível no quadro exato do corte', () => {
  assert.deepEqual(quadroEm(base(), 9.99).trechos, [{ id: 'a', opacidade: 1 }]);
  assert.deepEqual(quadroEm(base(), 10).trechos, [{ id: 'b', opacidade: 1 }]);
});

test('uma fusão mostra os dois trechos e o novo cresce por cima do anterior', () => {
  const cena = base();
  cena.trechos[1].entrada = 'fusao';
  assert.deepEqual(quadroEm(cena, 9.99).trechos, [{ id: 'a', opacidade: 1 }]);
  assert.deepEqual(quadroEm(cena, 10.3).trechos, [{ id: 'a', opacidade: 1 }, { id: 'b', opacidade: 0.5 }]);
  assert.deepEqual(quadroEm(cena, 10.6).trechos, [{ id: 'b', opacidade: 1 }]);
});

test('o clipe acelerado avança no dobro do tempo e para no quadro do congelamento', () => {
  const cena = base();
  cena.trechos[1] = { id: 'b', tipo: 'clipe', inicio: 10, fim: 20, entrada: 'corte',
                      clipe: { inicioNoClipe: 1, velocidade: 2, congelaEm: 13 } };
  assert.deepEqual(quadroEm(cena, 11).clipe, { tempo: 3, congelado: false });
  assert.deepEqual(quadroEm(cena, 13).clipe, { tempo: 7, congelado: true });
  assert.deepEqual(quadroEm(cena, 19).clipe, { tempo: 7, congelado: true });
  assert.equal(quadroEm(cena, 9).clipe, null);
});

test('a imagem aproxima e desliza do enquadramento inicial ao final ao longo do trecho', () => {
  const cena = base();
  cena.trechos[1].kenburns = { de: { escala: 1, x: 0, y: 0 }, ate: { escala: 1.4, x: -200, y: 100 } };
  assert.deepEqual(quadroEm(cena, 10).imagem, { escala: 1, x: 0, y: 0 });
  assert.deepEqual(quadroEm(cena, 15).imagem, { escala: 1.2, x: -100, y: 50 });
  assert.deepEqual(quadroEm(cena, 19.999).imagem, { escala: 1.4, x: -200, y: 100 });
  assert.equal(quadroEm(cena, 5).imagem, null);
});

test('a câmera fica parada até a próxima marca e chega ao alvo ao fim do movimento', () => {
  const cena = base({ camera: [{ t: 0, x: 540, y: 960, zoom: 1 }, { t: 4, x: 1500, y: 2400, zoom: 1.5, dur: 1 }] });
  assert.deepEqual(quadroEm(cena, 3.9).camera, { x: 540, y: 960, zoom: 1 });
  assert.deepEqual(quadroEm(cena, 5).camera, { x: 1500, y: 2400, zoom: 1.5 });
  const meio = quadroEm(cena, 4.5).camera;
  assert.ok(meio.x > 1000 && meio.x < 1500, `a câmera está no caminho: ${meio.x}`);
});

test('um movimento novo parte de onde a câmera estava, sem salto', () => {
  const cena = base({ camera: [{ t: 0, x: 0, y: 0, zoom: 1 }, { t: 4, x: 1000, y: 0, zoom: 1, dur: 2 },
                               { t: 5, x: 1000, y: 1000, zoom: 1, dur: 2 }] });
  const antes = quadroEm(cena, 5 - 1 / 30).camera, depois = quadroEm(cena, 5).camera;
  assert.ok(Math.abs(depois.x - antes.x) < 30, `sem salto em x: ${antes.x} → ${depois.x}`);
});

const comItem = () => base({ itens: [{ id: 'c1', entra: 2, esmaece: [[6, null]] }] });

test('o item fica oculto até a palavra em que entra', () => {
  assert.equal(quadroEm(comItem(), 1.99).itens.c1.estado, 'oculto');
  assert.equal(quadroEm(comItem(), 1.99).itens.c1.opacidade, 0);
});

test('a entrada com mola passa do tamanho final e assenta nele', () => {
  const escalas = Array.from({ length: 31 }, (_, f) => quadroEm(comItem(), 2 + f / 30).itens.c1.escala);
  assert.ok(Math.max(...escalas) > 1.01, `a mola passa do tamanho final: ${Math.max(...escalas)}`);
  const assentado = quadroEm(comItem(), 3.5).itens.c1;
  assert.equal(assentado.estado, 'foco');
  assert.ok(Math.abs(assentado.escala - 1) < 0.002, `assenta em 1: ${assentado.escala}`);
  assert.equal(assentado.opacidade, 1);
  assert.equal(assentado.brilho, 1);
});

test('o item esmaecido fica no mapa, mais transparente, desfocado e sem brilho', () => {
  const q = quadroEm(comItem(), 7).itens.c1;
  assert.deepEqual({ estado: q.estado, opacidade: q.opacidade, desfoque: q.desfoque, brilho: q.brilho },
                   { estado: 'esmaecido', opacidade: 0.32, desfoque: 3, brilho: 0 });
});

test('a legenda mostra grupos de até três palavras e a pontuação fecha o grupo', () => {
  const palavras = [['Montar', 0, 0.4], ['é', 0.4, 0.5], ['escolher.', 0.5, 1], ['Um', 1.6, 1.8],
                    ['corte', 1.8, 2.1], ['seco', 2.1, 2.4], ['muda', 2.4, 2.8]];
  const cena = base({ palavras, legenda: { palavrasPorVez: 3, destaques: ['corte'] } });
  assert.deepEqual(quadroEm(cena, 0.2).legenda, { palavras: ['Montar', 'é', 'escolher.'], destaques: [false, false, false] });
  assert.deepEqual(quadroEm(cena, 1.9).legenda, { palavras: ['Um', 'corte', 'seco'], destaques: [false, true, false] });
  assert.deepEqual(quadroEm(cena, 2.5).legenda, { palavras: ['muda'], destaques: [false] });
  assert.equal(quadroEm(cena, 1.55).legenda, null, 'meio segundo depois da fala, a pausa fica sem legenda');
});
