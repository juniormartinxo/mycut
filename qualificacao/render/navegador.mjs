// Chromium sem janela da qualificação: rede bloqueada fora do servidor local e vigia de relógio.
import { chromium } from 'playwright-core';

// Conta, enquanto ativo, toda leitura de relógio, temporizador e animação feita pela página.
const VIGIA = `(() => {
  const r = window.__relogio = { ativo: false, chamadas: {} };
  const vigiar = (alvo, nome, rotulo) => {
    const original = alvo[nome];
    alvo[nome] = function (...a) { if (r.ativo) r.chamadas[rotulo] = (r.chamadas[rotulo] || 0) + 1; return original.apply(this, a); };
  };
  vigiar(Date, 'now', 'Date.now'); vigiar(performance, 'now', 'performance.now');
  vigiar(window, 'setTimeout', 'setTimeout'); vigiar(window, 'setInterval', 'setInterval');
  vigiar(window, 'requestAnimationFrame', 'requestAnimationFrame'); vigiar(Element.prototype, 'animate', 'Element.animate');
  const D = Date;
  window.Date = new Proxy(D, { construct(alvo, a) { if (r.ativo && !a.length) r.chamadas['new Date()'] = (r.chamadas['new Date()'] || 0) + 1; return new alvo(...a); } });
})();`;

// QUALIF_CHROME (JSON) acrescenta opções de lançamento, para experimentos (ex.: flags de GPU).
export async function abrirNavegador() {
  const extra = JSON.parse(process.env.QUALIF_CHROME ?? '{}');
  return chromium.launch({ headless: true, ...extra,
                           args: ['--autoplay-policy=no-user-gesture-required', '--disable-background-timer-throttling', ...(extra.args ?? [])] });
}

// Abre a página do motor num contexto isolado; `bloqueadas` acumula toda tentativa de rede externa.
export async function abrirPagina(navegador, base, { largura, altura, caminho = '/motor-html/index.html' }) {
  const contexto = await navegador.newContext({ viewport: { width: largura, height: altura }, deviceScaleFactor: 1 });
  const bloqueadas = [];
  await contexto.route('**/*', rota => {
    const url = rota.request().url();
    if (url.startsWith(base) || url.startsWith('data:') || url.startsWith('blob:')) return rota.continue();
    bloqueadas.push(url);
    return rota.abort();
  });
  await contexto.addInitScript(VIGIA);
  const pagina = await contexto.newPage();
  const erros = [];
  pagina.on('pageerror', e => erros.push(String(e)));
  pagina.on('console', m => { if (m.type() === 'error') erros.push(m.text()); });
  await pagina.goto(base + caminho);
  await pagina.waitForFunction(() => window.motor);
  const cdp = await contexto.newCDPSession(pagina);
  return { pagina, contexto, cdp, bloqueadas, erros };
}

export async function capturar(cdp, { formato = 'jpeg', qualidade = 92 } = {}) {
  const { data } = await cdp.send('Page.captureScreenshot', formato === 'png'
    ? { format: 'png', optimizeForSpeed: true } : { format: 'jpeg', quality: qualidade, optimizeForSpeed: true });
  return Buffer.from(data, 'base64');
}
