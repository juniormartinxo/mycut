import { test } from 'node:test';
import assert from 'node:assert/strict';
import { montarCena } from '../composicao/cena.mjs';

// Fala sintética: uma palavra a cada 0,4 s, com pausa de 1 s a cada 12 palavras.
function fala(segundos) {
  const palavras = [];
  for (let t = 0.5, i = 0; t < segundos - 1; i++) {
    palavras.push([i % 12 === 11 ? `palavra${i}.` : `palavra${i}`, t, t + 0.32]);
    t += i % 12 === 11 ? 1.4 : 0.4;
  }
  return palavras;
}
const midia = { imagens: ['imagem-1.png', 'imagem-2.png'], clipe: { arquivo: 'clipe.webm', duracao: 8 } };

for (const [formato, largura, altura] of [['9:16', 1080, 1920], ['16:9', 1920, 1080]]) {
  test(`a cena ${formato} tem todos os recursos da composição representativa`, () => {
    const cena = montarCena({ formato, palavras: fala(65), duracao: 65, midia });
    assert.deepEqual([cena.formato.largura, cena.formato.altura, cena.formato.fps], [largura, altura, 30]);
    assert.ok(cena.mapa.largura > largura && cena.mapa.altura > altura, 'o mapa é maior que o quadro');
    assert.deepEqual(new Set(cena.trechos.map(t => t.tipo)), new Set(['mapa', 'imagem', 'clipe']));
    const entradas = cena.trechos.slice(1).map(t => t.entrada);
    assert.ok(entradas.includes('corte') && entradas.includes('fusao'), 'há corte e fusão');
    const clipe = cena.trechos.find(t => t.tipo === 'clipe');
    assert.notEqual(clipe.clipe.velocidade, 1);
    assert.ok(clipe.inicio < clipe.clipe.congelaEm && clipe.clipe.congelaEm < clipe.fim, 'o clipe congela dentro do trecho');
    assert.ok(cena.trechos.some(t => t.kenburns), 'há zoom e panorâmica numa imagem');
    assert.ok(cena.itens.some(i => i.vidro) && cena.itens.some(i => i.brilho), 'há vidro fosco e brilho');
    assert.ok(cena.camera.length > 3, 'a câmera viaja pelo mapa');
    assert.ok(cena.legenda && cena.musica && cena.narracao, 'há legenda, narração e música');
  });

  test(`na cena ${formato} os trechos cobrem a fala inteira, sem buraco`, () => {
    const cena = montarCena({ formato, palavras: fala(65), duracao: 65, midia });
    assert.equal(cena.trechos[0].inicio, 0);
    assert.equal(cena.trechos.at(-1).fim, 65);
    cena.trechos.slice(1).forEach((t, i) => assert.equal(t.inicio, cena.trechos[i].fim));
  });
}

test('entradas, câmera e trechos começam em palavras da fala', () => {
  const palavras = fala(65);
  const cena = montarCena({ formato: '9:16', palavras, duracao: 65, midia });
  const inicios = new Set(palavras.map(p => p[1]));
  for (const item of cena.itens) assert.ok(inicios.has(item.entra), `item ${item.id} entra em ${item.entra}`);
  for (const marca of cena.camera.slice(1)) assert.ok(inicios.has(marca.t), `câmera em ${marca.t}`);
  for (const trecho of cena.trechos.slice(1)) assert.ok(inicios.has(trecho.inicio), `trecho ${trecho.id} em ${trecho.inicio}`);
});

test('um vídeo de 25 minutos vira capítulos em regiões diferentes do mapa', () => {
  const cena = montarCena({ formato: '16:9', palavras: fala(1500), duracao: 1500, midia, marcaDeTeste: 'ENSAIO · TESTE' });
  assert.ok(cena.trechos.filter(t => t.tipo === 'clipe').length >= 15, 'cada capítulo tem o seu clipe');
  assert.equal(cena.trechos.at(-1).fim, 1500);
  for (const item of cena.itens.filter(i => i.trecho === 'mapa')) {
    assert.ok(item.x >= 0 && item.x <= cena.mapa.largura && item.y >= 0 && item.y <= cena.mapa.altura, `item ${item.id} no mapa`);
  }
  assert.equal(cena.marcaDeTeste, 'ENSAIO · TESTE');
});
