import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ganhoDaMusica, marcasDaMusica } from '../composicao/mixagem.mjs';

const cena = {
  palavras: [['a', 1, 1.5], ['b', 1.6, 2], ['c', 4, 4.5]],
  musica: { ganhoFala: -18, ganhoPausa: -8, pausaMinima: 0.8, rampa: 0.3 },
};

test('a música abaixa para o ganho de fala quando a voz entra e fica baixa nas pausas curtas', () => {
  assert.equal(ganhoDaMusica(cena, 0.2), -8);
  assert.equal(ganhoDaMusica(cena, 1), -18);
  assert.equal(ganhoDaMusica(cena, 1.55), -18);
  assert.equal(ganhoDaMusica(cena, 2), -18);
});

test('numa pausa longa a música sobe e volta a abaixar antes da próxima palavra', () => {
  assert.equal(ganhoDaMusica(cena, 2.15), -13);
  assert.equal(ganhoDaMusica(cena, 3), -8);
  assert.equal(ganhoDaMusica(cena, 4), -18);
  assert.equal(ganhoDaMusica(cena, 5), -8);
});

test('as marcas do envelope estão em ordem e cobrem o começo e o fim', () => {
  const marcas = marcasDaMusica(cena);
  assert.deepEqual(marcas[0], { t: 0, db: -8 });
  assert.deepEqual(marcas.at(-1), { t: 4.8, db: -8 });
  assert.ok(marcas.every((m, i) => i === 0 || m.t >= marcas[i - 1].t));
});

test('numa pausa mais curta que duas rampas a música sobe e desce sem patamar, com as marcas em ordem', () => {
  const curta = { palavras: [['a', 1, 1.5], ['b', 2.1, 2.5]], musica: { ganhoFala: -18, ganhoPausa: -8, pausaMinima: 0.5, rampa: 0.4 } };
  const marcas = marcasDaMusica(curta);
  assert.ok(marcas.every((m, i) => i === 0 || m.t >= marcas[i - 1].t), JSON.stringify(marcas));
  assert.equal(ganhoDaMusica(curta, 1.8), -8);
  assert.equal(ganhoDaMusica(curta, 2.1), -18);
});
