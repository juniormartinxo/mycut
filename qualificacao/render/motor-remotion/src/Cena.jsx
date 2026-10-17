// Candidato Remotion: a mesma cena (dados de montarCena e estado de quadroEm), desenhada em React.
// Mídia no idioma do Remotion: OffthreadVideo com playbackRate e Freeze para o clipe, Img para a
// imagem, Audio com volume por quadro para a música. Serve à renderização e ao <Player> da prévia.
import React from 'react';
import { Audio, Freeze, Img, OffthreadVideo, Sequence, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { FUSAO, quadroEm } from '../../composicao/quadro.mjs';
import { ganhoDaMusica } from '../../composicao/mixagem.mjs';
import '../../motor-html/motor.css';

const LATIN = 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD';
const FONTES = [['Inter', 400], ['Inter', 600], ['Inter', 800], ['Inter', 900], ['JetBrains Mono', 500], ['JetBrains Mono', 800]];

let fontes = null;
function carregarFontes(url) {
  if (fontes) return;
  const espera = delayRender('fontes locais');
  fontes = Promise.all(FONTES.map(async ([familia, peso]) => {
    const arquivo = `fontes/${familia.toLowerCase().replace(' ', '-')}-latin-${peso}-normal.woff2`;
    document.fonts.add(await new FontFace(familia, `url(${url(arquivo)})`, { weight: String(peso), unicodeRange: LATIN }).load());
  })).then(() => continueRender(espera));
}

const camada = (visivel, opacidade, z) => ({ visibility: visivel ? 'visible' : 'hidden', opacity: visivel ? opacidade : 0, zIndex: z });

function Item({ item, s }) {
  return (
    <div className={`item ${item.tipo} tom${item.tom}${item.vidro ? ' vidro' : ''}`}
      style={{ left: item.x, top: item.y, width: item.largura, visibility: s.opacidade > 0 ? 'visible' : 'hidden', opacity: s.opacidade,
               transform: `translate(-50%, -50%) translateY(${s.desloc}px) scale(${s.escala})`,
               filter: s.desfoque > 0.01 ? `blur(${s.desfoque}px)` : 'none', '--brilho': item.brilho ? s.brilho : 0 }}>
      {item.tipo !== 'titulo' && <div className="selo">{item.vidro ? 'vidro fosco' : 'ponto'}</div>}
      <div className="titulo">{item.titulo}</div>
      <div className="texto">{item.texto}</div>
    </div>
  );
}

export function Cena({ cena, baseDaMidia }) {
  const frame = useCurrentFrame();
  const { fps, width: W, height: H } = useVideoConfig();
  const url = nome => (baseDaMidia ? baseDaMidia + nome : staticFile(nome));
  carregarFontes(url);
  const q = quadroEm(cena, frame / fps);
  const porId = Object.fromEntries(cena.trechos.map(t => [t.id, t]));
  const visiveis = new Map(q.trechos.map((v, i) => [v.id, { ...v, z: i }]));
  let mapa = 0, mapaZ = 0;
  for (const [id, v] of visiveis) if (porId[id].tipo === 'mapa') { mapa = Math.max(mapa, v.opacidade); mapaZ = v.z; }
  const c = q.camera;
  const itensDe = trecho => cena.itens.filter(i => i.trecho === trecho).map(i => <Item key={i.id} item={i} s={q.itens[i.id]} />);

  return (
    <div id="palco" style={{ width: W, height: H, '--cor1': cena.fundo.cor1, '--cor2': cena.fundo.cor2, '--grade': cena.fundo.grade }}>
      <div className="camada mapa" style={camada(mapa > 0, mapa, 2 * mapaZ)}>
        <div className="fundo" />
        <div className="grade" style={{ backgroundPosition: `0 ${q.ambiente.grade}px` }} />
        <div className="luz" style={{ background: '#38bdf8', left: q.ambiente.luz1.x * W, top: q.ambiente.luz1.y * H }} />
        <div className="luz" style={{ background: '#10b981', left: q.ambiente.luz2.x * W, top: q.ambiente.luz2.y * H }} />
        <div className="mundo" style={{ width: cena.mapa.largura, height: cena.mapa.altura,
                                          transform: `translate(${W / 2 - c.x * c.zoom}px, ${H / 2 - c.y * c.zoom}px) scale(${c.zoom})` }}>
          {itensDe('mapa')}
        </div>
      </div>
      {cena.trechos.filter(t => t.tipo === 'imagem').map(t => {
        const v = visiveis.get(t.id);
        return (
          <div key={t.id} className="camada imagem" style={camada(!!v, v?.opacidade, v ? 2 * v.z : 0)}>
            <Img src={url(t.imagem)} style={v ? { transform: `translate(${q.imagem.x}px, ${q.imagem.y}px) scale(${q.imagem.escala})` } : {}} />
          </div>
        );
      })}
      {cena.trechos.filter(t => t.tipo === 'clipe').map(t => {
        const v = visiveis.get(t.id), de = Math.round(t.inicio * fps), ate = Math.round((t.fim + FUSAO) * fps);
        const congela = Math.round((t.clipe.congelaEm - t.inicio) * fps);
        return (
          <Sequence key={t.id} from={de} durationInFrames={ate - de} layout="none">
            <div className="camada video" style={camada(!!v, v?.opacidade, v ? 2 * v.z : 0)}>
              <Freeze frame={congela} active={f => f >= congela}>
                <OffthreadVideo src={url(t.clipe.arquivo)} playbackRate={t.clipe.velocidade} muted
                  style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
              </Freeze>
            </div>
            <div className="camada" style={camada(!!v, v?.opacidade, v ? 2 * v.z + 1 : 0)}>{itensDe(t.id)}</div>
          </Sequence>
        );
      })}
      <div className="legenda" style={{ left: cena.legenda.x, top: cena.legenda.y, width: cena.legenda.largura, height: cena.legenda.altura,
                                         visibility: q.legenda ? 'visible' : 'hidden' }}>
        {q.legenda && q.legenda.palavras.map((w, i) => (
          <React.Fragment key={i}>{i > 0 && ' '}{q.legenda.destaques[i] ? <span className="destaque">{w}</span> : w}</React.Fragment>
        ))}
      </div>
      {cena.marcaDeTeste && <div className="marca-teste">{cena.marcaDeTeste}</div>}
      <div className="progresso" style={{ width: `${q.progresso * 100}%` }} />
      <Audio src={url(cena.narracao.arquivo)} />
      <Audio src={url(cena.musica.arquivo)} volume={f => Math.pow(10, ganhoDaMusica(cena, f / fps) / 20)} />
    </div>
  );
}
