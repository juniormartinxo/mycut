# Qualificação do motor de composição (MYC-11)

Código da prova técnica registrada em [docs/qualificacao-renderizacao.md](../../docs/qualificacao-renderizacao.md).
Não é código do produto: serve para repetir as medições. É anterior ao documento de edição e usa nomes
próprios: `cena` é o vídeo inteiro, `capitulo` é a cena do glossário e `trecho` é um intervalo visual (mapa,
imagem ou clipe) que entra por corte ou fusão, não um trecho de fala. Vídeos, quadros e relatórios vão para `.saida/`,
ignorada pelo Git.

## Peças

| Pasta | O que faz |
| --- | --- |
| `composicao/` | `montarCena` (cena representativa como dados, 9:16 e 16:9), `quadroEm(cena, t)` (estado do quadro como função do tempo) e o envelope da música |
| `motor-html/` | Candidato HTML: página que desenha `quadroEm(t)`, prévia com WebAudio e gravador em abas paralelas |
| `motor-remotion/` | Candidato Remotion: a mesma cena em React, `renderMedia` e a prévia no `<Player>` |
| `referencia-python/` | Repete uma produção existente com o motor atual do MyCut, numa cópia isolada dos dados |
| `midia/` | Mídias de esboço (imagens, clipe com contador de quadros, música, fontes) e alinhamento da narração |
| `medir/` | Paridade prévia × exportação, conferência do clipe, NVENC, som pela Q46, voz × música e memória |
| `ensaio/` | Roteiro e execução do ensaio de escala de 25 min |

## Pré-requisitos

- Node 24 e pnpm; `pnpm install` nesta pasta.
- Chromium do Playwright 1.64: `pnpm exec playwright-core install chromium-headless-shell` (uma vez, com rede).
- FFmpeg com `h264_nvenc` (no WSL, o driver NVIDIA do Windows expõe a GPU em `/usr/lib/wsl/lib`).
- `unshare` (util-linux) para gravar sem rede.
- Para a narração de ensaio: o Qwen3-TTS local do MyCut e o Whisper do backend (`backend/mycut/alignment.py`).

## Repetir

```bash
cd qualificacao/render
pnpm test                                   # núcleo puro: quadroEm, envelope, montarCena

# 1. Narração de ensaio (Qwen local, nunca ElevenLabs) e alinhamento por palavra
PYTHONPATH=../../backend python midia/alinhar.py narracao.wav palavras.json [--cuda]

# 2. Mídias de esboço e a matriz do Short (9:16 e 16:9, HTML e Remotion, NVENC e x264, paridade, clipe)
node midia/preparar.mjs .saida/short/midia --narracao narracao.wav --palavras palavras.json --duracao 65.3
bash rodar-short.sh .saida/short

# 3. NVENC com o caminho verificado, voz × música e determinismo (mesmos pixels em qualquer ordem)
node medir/nvenc.mjs .saida/short/html-16x9-h264_nvenc.video.mp4 .saida/nvenc
node medir/partes.mjs .saida/short/cena-9x16.json .saida/short/midia .saida/partes/short
node medir/determinismo.mjs .saida/short/cena-9x16.json .saida/short/midia 40

# 4. Motor atual como referência (cópia isolada dos dados; não toca o banco original)
PYTHONPATH=../../backend python referencia-python/render.py <pasta .data> <id de um job final> .saida/referencia
node medir/paridade-python.mjs .saida/referencia/python-preview.mp4 .saida/referencia/python-final.mp4 <duração> .saida/paridade/python

# 5. Ensaio de 25 min no motor escolhido
bash ensaio/rodar-ensaio.sh narracao-25min.wav palavras-25min.json 4
```

`QUALIF_CHROME` (JSON) acrescenta opções de lançamento ao Chromium, para experimentos como flags de GPU.
