#!/usr/bin/env bash
# Ensaio de escala de 25 min (16:9) no motor escolhido, com áudio de ensaio Qwen e mídias de esboço.
# O arquivo sai marcado como TESTE no nome, nos metadados e na imagem.
# Uso: bash qualificacao/render/ensaio/rodar-ensaio.sh <narracao-qwen.wav> <palavras.json> [abas]
set -euo pipefail
cd "$(dirname "$0")/.."
NARRACAO="$1"; PALAVRAS="$2"; ABAS="${3:-4}"   # 4 abas já saturam as 8 CPUs lógicas do hardware alvo
E=.saida/ensaio
sem_rede() { unshare -rn sh -c 'ip link set lo up && exec "$@"' sh "$@"; }
mkdir -p "$E" .saida/paridade

DURACAO=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$NARRACAO")
node midia/preparar.mjs "$E/midia" --narracao "$NARRACAO" --palavras "$PALAVRAS" --duracao "$DURACAO"
node composicao/gerar.mjs "$E/midia" 16:9 "$E/cena-16x9.json" --marca "ENSAIO DE ESCALA · TESTE"
sem_rede node motor-html/gravar.mjs "$E/cena-16x9.json" "$E/midia" "$E/ENSAIO-TESTE-25min-16x9.mp4" \
  --abas "$ABAS" --codificador h264_nvenc --titulo "TESTE: ensaio de escala MYC-11 (Qwen e esboços), não é entrega" > "$E/gravar.out" 2>&1
sem_rede node ensaio/previa.mjs "$E/cena-16x9.json" "$E/midia" "$E/previa.json" > "$E/previa.out" 2>&1
sem_rede node medir/paridade-motor.mjs html "$E/cena-16x9.json" "$E/midia" "$E/ENSAIO-TESTE-25min-16x9.mp4" .saida/paridade/ensaio > .saida/paridade/ensaio.out 2>&1
node medir/clipe.mjs "$E/cena-16x9.json" "$E/midia" "$E/ENSAIO-TESTE-25min-16x9.mp4" .saida/paridade/clipe-ensaio > .saida/paridade/clipe-ensaio.out 2>&1
echo "ensaio concluído"
