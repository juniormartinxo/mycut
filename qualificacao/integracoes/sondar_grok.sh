#!/usr/bin/env bash
# Um pedido de clipe ao Grok Build, gravando tudo o que o CLI expõe (MYC-13).
# Consome cota de vídeo da assinatura: só rodar com autorização registrada do autor.
# Uso: bash sondar_grok.sh <pasta de saída> <imagem-base.png>
set -euo pipefail
uso="uso: bash sondar_grok.sh <pasta de saída> <imagem-base.png>"
saida="$(realpath -m "${1:?$uso}")"
base="$(realpath "${2:?$uso}")"
mkdir -p "$saida"
[[ -e "$saida/stream.ndjson" ]] && { echo "$saida já tem uma rodada; use outra pasta." >&2; exit 1; }

sessao="$(python3 -c 'import uuid; print(uuid.uuid4())')"
echo "$sessao" > "$saida/sessao.txt"
cat > "$saida/prompt.txt" <<EOF
Call the reference_to_video tool exactly once with exactly these arguments and nothing else:
first_frame = "$base"
prompt = "A small paper boat sails slowly from the left third of the frame to the right third across calm water, the camera holds still."
aspect_ratio = "16:9"
duration = 6
resolution_name = "480p"
Do not generate or edit images. Do not retry if the call fails. After the call, report the raw tool result verbatim, including any request id and the saved file path.
EOF

date -Is > "$saida/inicio.txt"
# Só a ferramenta de vídeo, uma chamada paralela, sem subagentes nem web; o id da sessão é nosso.
# --tools não remove os servidores MCP do ~/.grok: --deny MCPTool bloqueia as chamadas a eles.
GROK_MAX_PARALLEL_VIDEO_GEN_CALLS=1 grok \
  --prompt-file "$saida/prompt.txt" \
  --session-id "$sessao" \
  --cwd "$saida" \
  --output-format streaming-json \
  --tools reference_to_video \
  --disallowed-tools Agent \
  --deny MCPTool \
  --no-subagents \
  --disable-web-search \
  --max-turns 3 \
  --permission-mode bypassPermissions \
  > "$saida/stream.ndjson" 2> "$saida/stderr.log" || echo "saída $?" >> "$saida/stderr.log"
date -Is > "$saida/fim.txt"

grok usage "$sessao" > "$saida/usage.txt" 2>&1 || true
ls -la "$saida" > "$saida/arquivos.txt"
echo "sessão $sessao gravada em $saida"
