// Prévia do candidato Remotion: o <Player> com a mesma composição, e a interface de medição
// (carregar, irPara, tocar, quadro atual, captura do som que o Player toca).
// O Player fica em escala 1 e a redução é por `zoom` de fora: com a escala interna dele
// (transform), o backdrop-filter amostra o fundo na escala errada.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { Player } from '@remotion/player';
import { Cena } from './src/Cena.jsx';

const ref = React.createRef();
const quadro = () => new Promise(ok => requestAnimationFrame(ok));
let audio = null, carregando = false;   // "waiting"/"resume" do Player

// Espera o Player terminar de mostrar o quadro: imagens carregadas, vídeos sem busca pendente, sem "buffering".
async function pronto() {
  await quadro(); await quadro();
  for (let i = 0; i < 600; i++) {
    const imagens = [...document.images].every(img => img.complete);
    const videos = [...document.querySelectorAll('video')].every(v => !v.seeking && v.readyState >= 2);
    if (imagens && videos && !carregando) break;
    await quadro();
  }
  await quadro();
}

window.motor = {
  async carregar(cena, { escala }) {
    const { largura: W, altura: H, fps } = cena.formato;
    createRoot(document.getElementById('raiz')).render(
      <Player ref={ref} component={Cena} inputProps={{ cena, baseDaMidia: '/midia/' }} durationInFrames={Math.round(cena.duracao * fps)}
        compositionWidth={W} compositionHeight={H} fps={fps} style={{ width: W, height: H, zoom: escala }} acknowledgeRemotionLicense />);
    while (!ref.current) await quadro();
    ref.current.addEventListener('waiting', () => { carregando = true; });
    ref.current.addEventListener('resume', () => { carregando = false; });
    await document.fonts.ready;
    await this.irPara(0);
    return { fontes: [['Inter', 400], ['Inter', 600], ['Inter', 800], ['Inter', 900], ['JetBrains Mono', 500], ['JetBrains Mono', 800]].map(([f, p]) => ({ fonte: `${p} ${f}`, carregada: document.fonts.check(`${p} 40px "${f}"`) })) };
  },
  async irPara(t) {
    ref.current.pause();
    ref.current.seekTo(Math.round(t * 30));
    await pronto();
  },
  quadroAtual: () => ref.current.getCurrentFrame(),
  // Toca e grava o som que sai dos elementos <audio> do Player, com o relógio do contexto e o quadro mostrado.
  async tocar(desde, { capturar = false } = {}) {
    ref.current.seekTo(Math.round(desde * 30));
    await pronto();
    if (capturar && !audio) {
      const ctx = new AudioContext({ sampleRate: 48000 });
      await ctx.audioWorklet.addModule('/motor-html/captura.js');
      const tap = new AudioWorkletNode(ctx, 'captura', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [2] });
      const blocos = [];
      tap.port.onmessage = e => blocos.push(e.data);
      tap.connect(ctx.destination);
      for (const el of document.querySelectorAll('audio')) ctx.createMediaElementSource(el).connect(tap);
      audio = { ctx, blocos, marcas: [] };
      await ctx.resume();
    }
    ref.current.play();
  },
  marcar() { if (audio) audio.marcas.push([audio.ctx.currentTime, ref.current.getCurrentFrame()]); },
  pausar: () => ref.current.pause(),
  capturaDeAudio() { return audio && { taxa: 48000, blocos: audio.blocos.splice(0), marcas: audio.marcas }; },
  volumes: () => [...document.querySelectorAll('audio')].map(a => ({ src: a.currentSrc, volume: a.volume, paused: a.paused })),
};
