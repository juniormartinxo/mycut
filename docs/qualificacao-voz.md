# Qualificação da voz (MYC-12)

Prova técnica de 17/10/2026 para a voz dos vídeos horizontais, pedida pela fase 0 do
[plano](plano-implementacao-video-horizontal.md) e pela [ADR 0010](adr/0010-audio-de-ensaio-local-e-narracao-final.md).
Ela cobre três pontos: o áudio de ensaio local em texto longo, um alinhador local para PT-BR e a rota da
ElevenLabs com contexto e tempos. Produz evidência e escolhas, não funcionalidade do produto. O código da prova
está em [`qualificacao/voz/`](../qualificacao/voz/README.md). Áudios, respostas da API e relatórios ficam em
`qualificacao/voz/.saida/`, fora do Git.

**Escolhas** ([ADR 0020](adr/0020-voz-principal-omnivoice-alinhador-mms-e-rota-tts.md)):

- **Voz principal:** o Qwen foi reprovado de ouvido pelo autor. O
  [OmniVoice](https://github.com/k2-fsa/OmniVoice), testado e aprovado pelo autor no MyVoice, passa a ser a voz
  principal do MyCut, inclusive na narração final. A ElevenLabs vira a segunda via.
- **Alinhador local:** alinhamento forçado MMS (torchaudio), com um coringa para números e símbolos. O Whisper
  serve só para conferir o conteúdo, não os tempos.
- **ElevenLabs (segunda via):** `eleven_v4` na rota TTS com tempos
  (`/v1/text-to-speech/{voz}/with-timestamps`), com os pedidos encadeados por `previous_request_ids` e
  `next_text`.

## Hardware e versões

| Item | Valor |
| --- | --- |
| GPU | NVIDIA GeForce RTX 5070 Ti, 16 GB, no WSL2 (máquina compartilhada com outros projetos) |
| Qwen | `Qwen/Qwen3-TTS-12Hz-1.7B-Base`, revisão `fd4b2543`, `qwen-tts` 0.1.1, torch 2.11.0+cu128, bfloat16, SDPA |
| Whisper | large-v3 do backend (`faster-whisper`), float16 na GPU |
| MMS | `torchaudio.pipelines.MMS_FA` (torchaudio 2.11.0), com o token coringa `*` |
| ElevenLabs | plano Starter (40 mil caracteres por mês), voz Junior, `eleven_v4`, estabilidade 0,5, similaridade 0,75, velocidade 1,0 |

## Textos

- `textos/longo.txt`: 9.337 caracteres em 25 parágrafos. Os três primeiros concentram números, siglas e
  símbolos de propósito: data, `1080p`, `RTX 5070 Ti`, `4 min 12 s`, `US$ 22`, `275.000`, `R$ 5,01`,
  `R$ 110,22`, `5%`, `Dr.`, `NVENC`, `FFmpeg`, `9h30`, um e-mail e `±100 ms`. Os outros 22 são os primeiros
  parágrafos do roteiro do ensaio de 25 min do MYC-11.
- `textos/lote-elevenlabs.txt`: 1.327 caracteres, com os três parágrafos de números e dois de prosa. É o
  texto do lote pago.

## Resultados por critério de aceite

### 1. Ensaio Qwen de texto longo: gerado, ouvido e avaliado

O ensaio usou o perfil local da Q16: a referência é um recorte de 13,7 s de uma narração da voz Junior na
ElevenLabs `v4`, com a transcrição, no ambiente da narração local do MyCut. O serviço de narração local limita
cada pedido a 500 caracteres e devolve WAV sem tempos. Por isso o texto foi dividido em **trechos de fala** pela
Q28 (`texto.trechos`): um parágrafo por trecho e, se ele passar do limite, divisão entre frases, sem nunca
cortar uma frase. Os trechos foram emendados com pausa fixa de 0,9 s entre parágrafos. Para comparar, o mesmo
texto também foi gerado frase a frase.

| Modo | Unidades | Áudio | Tempo de GPU | Limite de tokens atingido |
| --- | ---: | ---: | ---: | ---: |
| Por trecho (Q28) | 25 trechos | 593,5 s (9,9 min) | 982 s (16,4 min) | 0 |
| Por frase | 107 frases | 629,8 s (10,5 min) | 1.106 s (18,4 min) | 0 |

A geração ficou em cerca de 0,6× o tempo real, gerando 4 e 6 pedidos juntos na GPU.

**Emendas.** Foram medidas em `emendas.py`, por trecho e por emenda:

| Medida | Qwen por trecho | ElevenLabs TTS | ElevenLabs diálogo |
| --- | --- | --- | --- |
| Vão real entre falas (pausa inserida de 0,9 s) | 1,06–1,47 s | 1,09–1,42 s | 1,08–1,38 s |
| Maior salto de loudness entre trechos vizinhos | 2,6 LU | 2,1 LU | 1,9 LU |
| Faixa de loudness por trecho | −31,2 a −27,8 LUFS | −29,5 a −26,8 LUFS | −29,4 a −27,2 LUFS |
| Amplitude nas bordas (estalo) | ≤ 0,0007 | ≤ 0,0029 | até 0,0426 no fim do último trecho |
| Ritmo na prosa (caracteres por segundo de fala) | 17,0 | 15,1 | 14,9 |

As emendas não têm estalo, e o silêncio que o próprio modelo põe nas bordas soma de 0,2 a 0,6 s à pausa
inserida. O Qwen fala cerca de 13% mais rápido que a ElevenLabs com o mesmo texto. Logo, a duração do ensaio não
prevê a duração da voz final, como a ADR 0010 já presumia. Na rota de diálogo, o último trecho termina sem
silêncio e com amplitude alta na borda, sinal de fala cortada.

**Conteúdo.** No ensaio Qwen, o Whisper reconheceu iguais ao texto 1.536 das 1.559 palavras da prosa. As 23
diferenças são números que o roteiro escreve por extenso e o Whisper escreve em algarismos. Nos três parágrafos
de números, 19 palavras saíram diferentes no Qwen, contra 13 na rota TTS e 14 na de diálogo da ElevenLabs. O
Qwen errou também `MyCut`, `RTX 5070 Ti`, `12`, `6`, `22` e `9h30`, que a ElevenLabs acertou.

**Escuta do autor.** O ensaio por trecho de 10 min foi ouvido, com os dois lotes da ElevenLabs para comparação.
Veredito sobre o Qwen: *"tá cortando muito as palavras e parece que tem uma certa deficiência, e com sotaque"*.
**O Qwen está reprovado como voz de ensaio.** Uma amostra com uma referência mais longa (28 s da voz Junior
v4) chegou a ser gerada, mas não foi avaliada. O autor decidiu trocar de modelo em vez de ajustar o Qwen.

**Substituto: OmniVoice.** O autor testou e aprovou o OmniVoice no MyVoice, um estúdio local de clonagem de
voz que fica fora deste repositório. O que lá foi verificado e importa para o MyCut:

- roda local na mesma GPU, com até 10 mil caracteres por geração. Gera um parágrafo por vez com o mesmo
  prompt de voz e acrescenta um silêncio escolhido entre os parágrafos, o mesmo modelo de trechos e emendas
  medido aqui;
- devolve WAV PCM16 mono de 24 kHz, **sem tempos**. O alinhador local continua necessário;
- prepara a leitura em PT-BR (moedas, unidades, horários, siglas e e-mails por extenso, mais um dicionário de
  pronúncias) e guarda o texto original separado do texto falado. É o caso de original × normalizado do
  critério 3;
- o código upstream é Apache-2.0, mas **os pesos oficiais (`k2-fsa/OmniVoice`) são CC-BY-NC**, com restrição
  de uso comercial, uma condição conhecida da escolha (ver a ADR 0020).

A validação do MyVoice registra que estabilidade em texto longo,
naturalidade e prosódia não foram medidas lá. Antes de o OmniVoice entrar no MyCut, falta repetir sobre ele o
ensaio longo, as emendas e o alinhamento desta prova.

### 2. Alinhador local medido por palavra

Foram dois candidatos, rodando por trecho e sem rede:

- **Whisper large-v3** (o do backend): reconhece a fala com tempos por palavra, e `texto.casar_roteiro` casa o
  reconhecido com o roteiro;
- **MMS forçado**: alinha o próprio roteiro ao áudio. Palavras com algarismos ou símbolos (`25`, `R$`, `@`)
  viram o coringa, que absorve qualquer fala (`vinte e cinco`) sem exigir que o texto seja normalizado antes.

**Contra os tempos da API** (desvio do início de cada palavra; a tolerância do piloto é ±100 ms pela Q48):

| Áudio | Palavras | Whisper: mediana / p95 / dentro de ±100 ms | MMS: mediana / p95 / dentro de ±100 ms |
| --- | ---: | --- | --- |
| Render existente `3ddbcd1c` | 149 | 200 / 400 ms / 12% | 20 / 191 ms / 90% |
| Render existente `672c63dd` | 144 | 180 / 400 ms / 17% | 24 / 122 ms / 90% |
| Render existente `845acad2` | 18 | 136 / 400 ms / 33% | 32 / 149 ms / 94% |
| Render existente `e1731c16` | 150 | 180 / 360 ms / 19% | 24 / 86 ms / 96% |
| Lote TTS: prosa | 152 | 191 / 400 ms / 15% | 24 / 100 ms / 95% |
| Lote TTS: números e símbolos | 106 | 200 / 580 ms / 20% | 42 / 710 ms / 71% |
| Lote diálogo: prosa | 152 | 200 / 380 ms / 18% | 18 / 99 ms / 96% |
| Lote diálogo: números e símbolos | 106 | 200 / 620 ms / 19% | 46 / 650 ms / 73% |

**Contra uma referência exata no áudio Qwen.** No modo por frase, cada frase foi gerada sozinha e emendada numa
posição conhecida. O começo da primeira palavra e o fim da última podem então ser medidos no próprio sinal
(silêncio abaixo de −45 dBFS):

| 107 frases, 10,5 min | Whisper | MMS |
| --- | --- | --- |
| Início de frase: mediana / p95 / dentro de ±100 ms | 400 / 570 ms / 4% | 30 / 74 ms / 99% |
| Fim de frase: mediana / p95 / dentro de ±100 ms | 130 / 330 ms / 39% | 14 / 145 ms / 88% |
| Tempo para alinhar os 10 min (GPU) | 132 s | 15 s |

**Confiança.** A do Whisper não avisa o erro: quase todas as palavras saem com confiança alta, mesmo atrasadas
em 200 ms. A do MMS (média do escore dos caracteres) também não separa o erro de forma consistente. As palavras
abaixo de 0,5 são de 0 a 7 por áudio e acertam, conforme o áudio, entre 40% e 100% (2 de 5, 5 de 7, 6 de 6,
5 de 7 e 4 de 6), contra 86–96% das demais. A confiança baixa pode abrir uma pendência pela Q45, mas não basta
como detector. Os erros grandes se concentram perto de números e símbolos, e é a posição no texto que melhor
indica onde conferir.

**Limitações registradas:**

- **Números e símbolos.** Perto do coringa, o MMS acerta 53% das palavras. Nesses pontos, porém, o erro maior é
  da referência. Com a `v4`, o alinhamento da API dá ao algarismo uma duração de texto, não de fala: `5070`
  recebe 0,16 s e `±100`, 0,24 s. A palavra seguinte fica adiantada de 0,4 a 1,3 s. Whisper e MMS concordam
  entre si que `Ti`, `por`, `caracteres.` e `ms"` começam bem depois do que a API diz. Logo, nos tempos de
  números e símbolos, nem a API nem a medição contra ela merecem confiança.
- **O Whisper atrasa os inícios** em cerca de 200 ms, de forma sistemática, e erra mais nos inícios de frase.
  Ele só serve para conferir o conteúdo (omissão, troca ou fala inventada), como em `emendas.py`.
- **O coringa exige grafia sem algarismos** no restante do texto. `romanizar` tira acentos e símbolos, e uma
  palavra sem nenhuma letra latina também vira coringa.
- **A referência exata cobre só bordas de frase.** O meio das frases foi medido apenas contra a API, ou seja,
  em áudio ElevenLabs.
- **Nada foi medido em áudio OmniVoice.** O MMS não depende do modelo de voz, mas a medição precisa ser repetida
  nos áudios dele.

### 3. Texto original × normalizado, sem presumir índices iguais

Testes do núcleo puro (`python3 -m unittest discover -s test -t .`, 16 testes):

- `palavras_da_api` usa o alinhamento do texto original quando ele reproduz o texto enviado. Se o original
  faltar ou não bater com o texto, recorre ao normalizado. Nesse caso, um grupo escrito de outro jeito na fala
  (`25` e `vinte e cinco`) recebe o intervalo do grupo falado, marcado como `aproximado`. Sem nenhum alinhamento,
  a ausência é informada e não fica escondida;
- `casar_roteiro` dá tempos a cada palavra do roteiro a partir do que o alinhador reconheceu. A correspondência
  é por sequência (`difflib`), sem caixa, acento e pontuação, não por índice. Palavras não reconhecidas dividem
  o vão entre as vizinhas, como `interpolado` e com confiança 0. Fala reconhecida a mais é ignorada;
- `comparar` recusa alinhamentos de textos diferentes.

O que a API devolveu na prática: em 10 de 10 pedidos `v4` (TTS e diálogo), `alignment` e `normalized_alignment`
vieram presentes e **iguais ao texto original, caractere a caractere**, mesmo com `US$ 22`, `275.000` e
`contato@mycut.dev`. A `v4` não expõe a normalização que fez. Assim, o mapeamento por índice daria certo aqui
por acaso, enquanto os tempos dos algarismos ficam errados (critério 2). Em respostas nas quais o normalizado
difere, o caminho da correspondência por sequência está coberto pelos testes, sem dados reais desta rodada.

O OmniVoice no MyVoice cria o mesmo problema do lado local: o texto falado (`vinte e dois dólares`) difere do
original (`US$ 22`). O MyCut deve alinhar o texto falado ao áudio com o MMS e levar os tempos ao original por
`corresponder`.

### 4. Rota e modelo da ElevenLabs

**Modelos (consulta sem custo a `/v1/models`).** Com português: `eleven_v4` (10 mil caracteres por pedido,
custo 1×), `eleven_v4_turbo` (0,5×), `eleven_v3`, `eleven_multilingual_v2`, `eleven_flash_v2_5` e
`eleven_turbo_v2_5`. A narração atual do MyCut já usa a `eleven_v4`, e ela foi mantida.

**As duas rotas com tempos**, testadas com o mesmo lote e a mesma voz:

| | TTS `/with-timestamps` | Diálogo `/text-to-dialogue/with-timestamps` |
| --- | --- | --- |
| Configurações da voz | estabilidade, similaridade, velocidade | só estabilidade |
| Contexto vizinho | `previous_request_ids` (até 3) ou `previous_text`, mais `next_text` inteiro | `previous_request_ids` ou `previous_text`, mais `future_text` de até 100 caracteres |
| Tempos | `alignment` e `normalized_alignment` em 5/5 | `alignment`, `normalized_alignment` e `voice_segments` em 5/5 |
| Escuta do autor | **melhor ou igual** | — |
| Emendas | sem corte | último trecho termina cortado |

**Escolha: TTS com tempos.** O contexto vai nos pedidos assim: o primeiro leva só `next_text`; os seguintes
levam até três `request-id` anteriores em `previous_request_ids` e o texto do trecho seguinte. O texto de
contexto **não é cobrado** (critério 5). O efeito do contexto na entonação não foi medido em separado, porque não
houve uma rodada sem contexto para comparar; a avaliação do autor foi sobre o lote encadeado.

**Recuperação pelo histórico.** A chave precisa das permissões `user_read` (assinatura) e
`speech_history_read` (histórico); sem elas, as consultas voltam 401. Com as duas, os 10 pedidos foram achados
no histórico pelo `request-id`. O áudio decodificado saiu idêntico ao recebido, e os alinhamentos também, com
uma diferença de formato: **no histórico, `character_end_times_seconds` traz a duração de cada caractere, não
o instante do fim** (`fins_absolutos` converte). Na listagem `/v1/history`, os itens vêm sem texto, voz e
alinhamentos, que só aparecem na consulta do item. Os campos `character_count_change_from/to` de cada item não
formam uma sequência e não servem para medir o consumo de um pedido.

**Alinhamento ausente.** Não aconteceu nos 10 pedidos, e não há como provocá-lo sem gastar créditos. Cada passo
do caminho foi exercitado em separado: a recuperação pelo histórico nos 10 pedidos e o alinhamento local nos
mesmos áudios. Falta exercitá-los como reserva de uma ausência real. O caminho previsto pela Q39 fica assim:

1. usar o `alignment` se ele reproduz o texto enviado; senão, o `normalized_alignment` por correspondência
   (`palavras_da_api`);
2. sem nenhum dos dois, consultar o item no histórico pelo `request-id` e converter os fins;
3. sem alinhamento no histórico, alinhar localmente o mesmo áudio com o MMS, registrando a origem `local`;
4. nunca gerar de novo por falta de tempos.

Nos números e símbolos, mesmo um alinhamento presente deve ser conferido pelo MMS (critério 2).

### 5. Geração paga autorizada e consumo real × estimado

A autorização está registrada em `.saida/autorizacao-lote.json`. O autor a deu no chat da sessão às 17h34 de
17/10/2026, depois de ver o alcance e o custo:

| Item | Valor |
| --- | --- |
| Alcance | voz Junior, `eleven_v4`, 5 trechos (1.327 caracteres), nas rotas TTS e diálogo |
| Estimativa apresentada | 2.654 caracteres, ~1.062 créditos (0,40 por caractere, o cobrado nas 4 gerações v4 anteriores); pior caso 2.654; ~US$ 0,21 pela tabela pública |
| Teto | 1.350 caracteres por rota, sem nova tentativa automática |
| Enviado | 1.327 + 1.327 caracteres, 10 pedidos, todos HTTP 200 |
| Cobrado pelos cabeçalhos (`character-cost`) | 74 + 72 + 56 + 164 + 164 = 530 por rota, **1.060 no total** |
| Assinatura antes → depois | 8.800 → 9.860 caracteres: **1.060**, igual aos cabeçalhos |

O consumo real ficou 2 créditos abaixo do estimado (arredondamento por pedido). Os 1.143 caracteres de
`next_text` e os request ids de contexto não foram cobrados. Cada pedido foi gravado antes do envio, e o lote
para antes de passar do teto (`elevenlabs.py`).

### 6. Registro em `docs/`

Este relatório e a [ADR 0020](adr/0020-voz-principal-omnivoice-alinhador-mms-e-rota-tts.md).

## O que fica para depois

- **Medir o OmniVoice no MyCut**, agora voz principal: ensaio longo dividido em trechos, emendas, alinhamento
  MMS sobre o texto falado com volta ao original, e escuta do autor. Os scripts desta pasta servem com a troca
  do gerador.
- **Conferir sempre os tempos da API perto de números e símbolos** e preferir o MMS nesses pontos ao montar
  legendas e cortes.

## Como reproduzir

Ver o [README da prova](../qualificacao/voz/README.md). O lote pago só roda com `--autorizado` e teto de
caracteres. Cada execução é uma nova geração paga e precisa de nova autorização (ADR 0007).
