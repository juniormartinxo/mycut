#!/usr/bin/env bash
# Matriz do Short (MYC-11): para 9:16 e 16:9, exporta com os dois candidatos (NVENC e x264),
# mede a paridade prévia × exportação e confere o clipe. Tudo roda num namespace de rede só
# com loopback (unshare -rn): qualquer acesso à internet durante a gravação falha.
# Uso: bash qualificacao/render/rodar-short.sh <pasta .saida/short>
set -euo pipefail
cd "$(dirname "$0")"
S="${1:-.saida/short}"
sem_rede() { unshare -rn sh -c 'ip link set lo up && exec "$@"' sh "$@"; }

node_modules/.bin/esbuild motor-remotion/previa.jsx --bundle --jsx=automatic --format=iife \
  --define:process.env.NODE_ENV='"production"' --minify --outfile=.saida/remotion-previa/previa.js --log-level=warning
for f in 9x16 16x9; do
  node composicao/gerar.mjs "$S/midia" "${f/x/:}" "$S/cena-$f.json"
  for cod in h264_nvenc libx264; do
    sem_rede node motor-html/gravar.mjs "$S/cena-$f.json" "$S/midia" "$S/html-$f-$cod.mp4" --abas 4 --codificador "$cod" > "$S/html-$f-$cod.out" 2>&1
    sem_rede node motor-remotion/gravar.mjs "$S/cena-$f.json" "$S/midia" "$S/remotion-$f-$cod.mp4" --concorrencia 4 --codificador "$cod" > "$S/remotion-$f-$cod.out" 2>&1
  done
  for m in html remotion; do
    sem_rede node medir/paridade-motor.mjs "$m" "$S/cena-$f.json" "$S/midia" "$S/$m-$f-h264_nvenc.mp4" ".saida/paridade/$m-$f" > ".saida/paridade/$m-$f.out" 2>&1
    node medir/clipe.mjs "$S/cena-$f.json" "$S/midia" "$S/$m-$f-h264_nvenc.mp4" ".saida/paridade/clipe-$m-$f" > ".saida/paridade/clipe-$m-$f.out" 2>&1
  done
done
echo "matriz do Short concluída"
