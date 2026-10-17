// Gera o JSON da cena representativa a partir das mídias preparadas.
// Uso: node composicao/gerar.mjs <pasta-das-midias> <9:16|16:9> <saida.json> [--marca "ENSAIO · TESTE"]
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { montarCena } from './cena.mjs';

export function gerarCena(pasta, formato, { marcaDeTeste = null } = {}) {
  const midia = JSON.parse(readFileSync(join(pasta, 'midia.json'), 'utf8'));
  const palavras = JSON.parse(readFileSync(join(pasta, 'palavras.json'), 'utf8'));
  const duracao = Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                                  join(pasta, midia.narracao)]).toString());
  return montarCena({ formato, palavras, duracao: Math.floor(duracao * 30) / 30, midia, marcaDeTeste });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { positionals, values } = parseArgs({ allowPositionals: true, options: { marca: { type: 'string' } } });
  const cena = gerarCena(positionals[0], positionals[1], { marcaDeTeste: values.marca ?? null });
  writeFileSync(positionals[2], JSON.stringify(cena));
  console.log(`${positionals[2]}: ${cena.duracao} s, ${cena.trechos.length} trechos, ${cena.itens.length} itens`);
}
