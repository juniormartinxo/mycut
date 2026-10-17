// Servidor local da qualificação: entrega a página do motor, a composição e as mídias.
// Responde a pedidos com Range (a busca do <video> depende disso) e só escuta em 127.0.0.1.
import { createReadStream, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join, normalize, resolve } from 'node:path';

const TIPOS = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.webm': 'video/webm', '.wav': 'audio/wav',
  '.woff2': 'font/woff2', '.mp4': 'video/mp4',
};

// `rotas` liga um prefixo de URL a uma pasta: { '/': raizDoHarness, '/midia/': pastaDasMidias }.
export function servir(rotas, porta = 0) {
  const pares = Object.entries(rotas).sort((a, b) => b[0].length - a[0].length).map(([p, d]) => [p, resolve(d)]);
  const servidor = createServer((req, res) => {
    const caminho = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    const [prefixo, pasta] = pares.find(([p]) => caminho.startsWith(p)) ?? [];
    const arquivo = pasta && normalize(join(pasta, caminho.slice(prefixo.length)));
    let info;
    try { info = arquivo.startsWith(pasta) && statSync(arquivo); } catch { info = null; }
    if (!info || !info.isFile()) { res.writeHead(404).end(); return; }
    const cabecalho = { 'Content-Type': TIPOS[extname(arquivo)] ?? 'application/octet-stream', 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' };
    const faixa = /bytes=(\d*)-(\d*)/.exec(req.headers.range ?? '');
    if (faixa) {
      const inicio = faixa[1] ? Number(faixa[1]) : info.size - Number(faixa[2]);
      const fim = faixa[1] && faixa[2] ? Math.min(Number(faixa[2]), info.size - 1) : info.size - 1;
      res.writeHead(206, { ...cabecalho, 'Content-Range': `bytes ${inicio}-${fim}/${info.size}`, 'Content-Length': fim - inicio + 1 });
      createReadStream(arquivo, { start: inicio, end: fim }).pipe(res);
    } else {
      res.writeHead(200, { ...cabecalho, 'Content-Length': info.size });
      createReadStream(arquivo).pipe(res);
    }
  });
  return new Promise(ok => servidor.listen(porta, '127.0.0.1', () => ok({
    url: `http://127.0.0.1:${servidor.address().port}`,
    fechar: () => new Promise(f => { servidor.closeAllConnections(); servidor.close(f); }),
  })));
}
