---
status: accepted
---

# Voz local OmniVoice, alinhador MMS e rota TTS da ElevenLabs

Em 2026-10-17, a qualificação do MYC-12 ([relatório](../qualificacao-voz.md)) testou três coisas: o ensaio
Qwen num texto longo, dois alinhadores locais em PT-BR e as rotas da ElevenLabs com tempos, contexto e
histórico. O teste incluiu um lote pago autorizado. Esta decisão ajusta a
[ADR 0010](0010-audio-de-ensaio-local-e-narracao-final.md) no motor local e fixa o que a ADR 0010 deixava
para qualificar.

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

## Em aberto: OmniVoice como voz principal

Ao trocar o Qwen, o autor indicou que o OmniVoice talvez vire a voz principal, com a ElevenLabs como segunda
via. Isso reverteria a regra central da ADR 0010: narração final sempre pela API, ensaio local só para testes.
**Esta ADR não muda essa regra.** Ela segue valendo até uma decisão explícita, que precisa considerar:

- **a licença dos pesos.** O código do OmniVoice é Apache-2.0, mas os pesos oficiais (`k2-fsa/OmniVoice`) são
  CC-BY-NC, com restrição de uso comercial. Vídeos de um canal monetizado podem ser uso comercial;
- **a qualidade em texto longo.** Ainda não foram medidos no OmniVoice o ensaio longo, as emendas, a
  estabilidade e o alinhamento desta qualificação;
- **o que muda no fluxo:** a autorização de narração (ADR 0007) deixaria de ser obrigatória para a voz final, e
  o áudio de ensaio passaria a poder ser entregue.

O próximo passo é qualificar o OmniVoice no MyCut com os scripts de `qualificacao/voz/`.
