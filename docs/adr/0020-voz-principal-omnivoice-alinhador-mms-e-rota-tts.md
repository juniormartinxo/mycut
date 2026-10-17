---
status: accepted
---

# Voz principal OmniVoice, alinhador MMS e rota TTS da ElevenLabs

Em 2026-10-17, a qualificação do MYC-12 ([relatório](../qualificacao-voz.md)) testou três coisas: o ensaio
Qwen num texto longo, dois alinhadores locais em PT-BR e as rotas da ElevenLabs com tempos, contexto e
histórico. O teste incluiu um lote pago autorizado. Esta decisão troca o motor
local da [ADR 0010](0010-audio-de-ensaio-local-e-narracao-final.md), fixa o que ela deixava para qualificar e,
por decisão posterior do autor, inverte o papel das duas vozes (última seção).

**O motor de voz local passa a ser o OmniVoice, no lugar do Qwen.** O autor ouviu 10 min de ensaio Qwen
dividido em trechos e o reprovou como voz de ensaio: "tá cortando muito as palavras e parece que tem uma certa
deficiência, e com sotaque". O Qwen também errou moedas, unidades, siglas e símbolos e falou cerca de 13% mais
rápido que a voz final. O autor já tinha testado e aprovado o
[OmniVoice](https://github.com/k2-fsa/OmniVoice) no MyVoice, seu estúdio local de clonagem de voz. O OmniVoice
roda na mesma GPU, gera por parágrafo com o mesmo prompt de voz e prepara a leitura em PT-BR, guardando o texto
original separado do falado. Onde a ADR 0010 e o plano dizem "Qwen", vale o motor local de ensaio. A troca
é uma escolha do autor feita de ouvido, ainda sem as medições desta qualificação sobre o OmniVoice. A
referência continua sendo a da Q16, uma amostra da voz Junior da ElevenLabs em PT-BR, até que se decida outra.

**O alinhador local é o alinhamento forçado MMS (torchaudio).** Ele alinha o próprio roteiro ao áudio, com um
coringa para palavras com algarismos ou símbolos. Na prosa, 90–96% dos inícios de palavra ficaram a até 100 ms
dos tempos da API. Numa referência exata no áudio local, 99% dos inícios de frase ficaram dentro dessa margem. O
Whisper large-v3 atrasa os inícios em cerca de 200 ms, de forma sistemática, e sua confiança não avisa o erro.
Ele fica só para conferir o conteúdo (omissões, trocas). A confiança do MMS também não basta como detector de
erro. A correspondência entre o texto escrito e o falado é feita por sequência, nunca por índice. Palavras sem
correspondência recebem tempos interpolados com confiança zero e viram pendência pela Q45.

**Na ElevenLabs, a rota é `eleven_v4` com TTS e tempos** (`/v1/text-to-speech/{voz}/with-timestamps`). Cada
pedido leva até três `request-id` anteriores em `previous_request_ids` e o trecho seguinte em `next_text`. O
texto de contexto não foi cobrado. A rota de diálogo foi descartada: aceita só estabilidade e 100 caracteres de
contexto, cortou o fim do último trecho, e o autor preferiu a TTS de ouvido. O consumo real (1.060 créditos)
bateu com o estimado. O alinhamento ausente segue a Q39, nesta ordem: resposta, histórico pelo `request-id`
(lá o fim de cada caractere vem como duração e precisa ser convertido) e alinhamento local do mesmo áudio. A
chave precisa das permissões `user_read` e `speech_history_read` para medir consumo e recuperar do histórico.

Os tempos da API não são confiáveis perto de números e símbolos. A `v4` devolve o alinhamento "normalizado"
igual ao texto original, dá ao algarismo uma duração de texto (`5070` em 0,16 s) e adianta a palavra seguinte
em até 1,3 s. Nesses pontos, legendas e cortes devem usar o MMS.

## OmniVoice como voz principal e ElevenLabs como segunda via

Em 2026-10-17, depois da qualificação, o autor aprovou o OmniVoice como **voz principal do MyCut**: mais barato
e, na avaliação dele, tão bom quanto a ElevenLabs. **Isso substitui a regra central da ADR 0010**, que exigia a
narração final sempre pela API e deixava o motor local só para testes. Passa a valer:

- **a narração final é gerada localmente pelo OmniVoice** com a voz Junior. O mesmo motor produz o áudio que
  se ouve na revisão do storyboard e o que vai para a entrega, sem troca obrigatória de voz no fim;
- **a ElevenLabs é a segunda via**, usada quando o autor escolher. Uma geração nela continua sujeita à
  autorização de narração da [ADR 0007](0007-autorizacao-humana-para-gerar-narracao.md), com alcance e custo
  apresentados antes, e segue a rota e os cuidados descritos acima;
- **o alinhamento da fala principal é local**, porque o OmniVoice devolve WAV sem tempos. O MMS alinha o texto
  falado (a leitura preparada) e os tempos voltam ao texto original por correspondência. A origem `local` e a
  confiança ficam registradas, e as pendências seguem a Q45;
- a falha do motor local deixa a narração pendente. Usar a ElevenLabs no lugar é uma escolha do autor, nunca
  automática.

Ficam condições conhecidas desta escolha:
- **a licença dos pesos oficiais** (`k2-fsa/OmniVoice`) é CC-BY-NC, com restrição de uso comercial; o código
  é Apache-2.0;
- **as medições desta prova ainda não foram repetidas no OmniVoice** dentro do MyCut: emendas em texto longo,
  alinhamento MMS sobre o áudio dele e mapeamento da leitura preparada. A aprovação veio da escuta do autor no
  MyVoice.
