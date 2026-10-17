# Qualificação da voz (MYC-12)

Código da prova técnica registrada em [docs/qualificacao-voz.md](../../docs/qualificacao-voz.md). Não é código do
produto: serve para repetir as medições. Áudios, respostas da API e relatórios vão para `.saida/`, ignorada pelo Git.
O perfil da voz local (áudio de referência e transcrição), os pesos do Qwen e a chave da ElevenLabs ficam fora do
repositório.

O Qwen foi reprovado como voz de ensaio e o motor local passa a ser o OmniVoice (ADR 0020). `ensaio_qwen.py`
fica para repetir esta prova. Para qualificar outro motor local, troque só o gerador: a divisão em trechos, as
emendas, o alinhamento e as medições não dependem do modelo de voz.

## Peças

| Arquivo | O que faz |
| --- | --- |
| `texto.py` | Núcleo puro: `trechos` (trechos de fala da Q28), `palavras_da_api` (tempos por palavra a partir dos alinhamentos original e normalizado da ElevenLabs), `casar_roteiro` (palavras do roteiro com os tempos de um alinhador local) |
| `medida.py` | Núcleo puro: `comparar` (desvio por palavra em ms, fração dentro de ±100 ms e separada pela confiança) |
| `ensaio_qwen.py` | Áudio de ensaio Qwen de um texto longo, por trecho de fala ou por frase, emendado com pausas fixas |
| `alinhar.py` | Alinhador local por trecho: Whisper large-v3 (o do backend) ou alinhamento forçado MMS (torchaudio) |
| `elevenlabs.py` | Consultas sem custo (modelos, assinatura, histórico), o lote pago (só com `--autorizado` e teto) e a recuperação pelo histórico |
| `medir.py` | Referências (tempos da API de um áudio existente ou de um lote; começo e fim de frase no modo frase) e comparações |
| `emendas.py` | Silêncios, bordas, loudness, ritmo e conteúdo reconhecido por trecho; vão e saltos em cada emenda |
| `textos/` | `longo.txt` (≈9,3 mil caracteres: três parágrafos com números, siglas e símbolos e os 22 primeiros do roteiro de 25 min do MYC-11) e `lote-elevenlabs.txt` (os três parágrafos e dois do roteiro) |

## Pré-requisitos

- Ambiente da narração local do MyCut (Python 3.12, torch cu128, `qwen-tts` 0.1.1), com os pesos do
  Qwen3-TTS 1.7B Base em `<checkout>/.cache/huggingface` e o perfil JSON da voz.
- Whisper large-v3 do backend (`faster-whisper`, em cache) e o modelo MMS do torchaudio
  (`~/.cache/torch/hub/checkpoints/model.pt`, baixado uma vez com rede).
- Para o Whisper na GPU, as bibliotecas cuBLAS e cuDNN que o torch instala:
  `LD_LIBRARY_PATH=<venv>/lib/python3.12/site-packages/nvidia/cublas/lib:<venv>/.../nvidia/cudnn/lib`.
- Para a ElevenLabs, `httpx` (ambiente do backend) e uma chave com as permissões de fala, `user_read` e
  `speech_history_read`.

## Repetir

```bash
cd qualificacao/voz
python3 -m unittest discover -s test -t .        # núcleo puro: trechos, mapeamentos e métrica

# 1. Ensaio Qwen (local) por trecho e por frase
PY=<venv da narração>/bin/python
$PY ensaio_qwen.py textos/longo.txt .saida/qwen-trecho --perfil <perfil.json> --raiz <checkout> --modo trecho --lote 4
$PY ensaio_qwen.py textos/longo.txt .saida/qwen-frase --perfil <perfil.json> --raiz <checkout> --modo frase --lote 6

# 2. Alinhamento local e emendas
export PYTHONPATH=../../backend
for a in whisper mms; do $PY alinhar.py .saida/qwen-trecho/ensaio.wav .saida/qwen-trecho/trechos.json .saida/qwen-trecho/$a.json --alinhador $a; done
$PY emendas.py .saida/qwen-trecho/ensaio.wav .saida/qwen-trecho/trechos.json .saida/qwen-trecho/whisper.json

# 3. Referência exata no áudio Qwen: frases geradas sozinhas, alinhadas por parágrafo
$PY medir.py paragrafos .saida/qwen-frase/trechos.json .saida/qwen-frase/paragrafos.json
for a in whisper mms; do $PY alinhar.py .saida/qwen-frase/ensaio.wav .saida/qwen-frase/paragrafos.json .saida/qwen-frase/$a.json --alinhador $a; done
$PY medir.py frases .saida/qwen-frase/ensaio.wav .saida/qwen-frase/trechos.json .saida/qwen-frase/{whisper,mms}.json

# 4. Áudios ElevenLabs já existentes (tempos da API como referência)
$PY medir.py referencia <.data>/projects/<id>/renders/<id>/voice .saida/elevenlabs-existentes/<id>
for a in whisper mms; do $PY alinhar.py .saida/elevenlabs-existentes/<id>/elevenlabs.mp3 .saida/elevenlabs-existentes/<id>/roteiro.txt .saida/elevenlabs-existentes/<id>/$a.json --alinhador $a; done
$PY medir.py comparar .saida/elevenlabs-existentes/<id>/referencia.json .saida/elevenlabs-existentes/<id>/{whisper,mms}.json

# 5. ElevenLabs: sem custo, depois o lote pago autorizado e a recuperação pelo histórico
APP=<venv do backend>/bin/python; I=<.data>/private/integrations.json
$APP elevenlabs.py conta $I .saida/elevenlabs
$APP elevenlabs.py lote $I .saida/elevenlabs textos/lote-elevenlabs.txt --rota tts --simular --teto 1350
$APP elevenlabs.py lote $I .saida/elevenlabs textos/lote-elevenlabs.txt --rota tts --autorizado --teto 1350   # PAGO
$APP elevenlabs.py recuperar $I .saida/elevenlabs --rota tts
$PY medir.py lote .saida/elevenlabs/lote-tts .saida/alinhamento-lote-tts
```

O lote pago só roda com `--autorizado`, registra cada pedido antes do envio, para antes de passar do teto de
caracteres e não repete pedidos sozinho. Cada execução é uma nova geração paga: só repita com nova autorização
(ADR 0007).
