---
status: accepted
---

# Reajuste da montagem após mudanças na fala

Quando a duração de uma fala muda, a montagem precisa acompanhá-la sem exigir
que o autor reconstrua manualmente as cenas seguintes. Na Q26 da entrevista de
2026-10-16, o usuário aceitou ajustar a duração da cena, deslocar as seguintes em
conjunto e realinhar os conteúdos vinculados à fala.

A Q28 definiu os tempos por caractere da ElevenLabs como base do alinhamento
final. Pela Q29, trechos em ensaio usam a duração do Qwen; receber a voz final ou
reutilizar uma voz anterior exige atualizar os tempos da montagem de acordo com
o áudio vigente. Textos, legendas, mídias vinculadas e o SRT final precisam seguir
essa mesma montagem temporal.

Antes de declarar falta de mídia, o agente pode ajustar a velocidade do clipe,
congelar um quadro, usar zoom ou panorâmica, ou acrescentar outra mídia. Essas
alternativas precisam servir ao trecho; não basta preencher sua duração. Só há
pendência quando nenhuma solução adequada for possível dentro das autorizações
vigentes. Quando a fala encurta, a montagem também deve ser reajustada sem deixar
buracos. A Q22 incluiu controles de velocidade e congelamento no editor humano.

A música que atravessa várias cenas não é esticada para acompanhar a alteração.
Ela continua ou é cortada automaticamente com fade. Música, efeitos e áudio
associado à fala não podem ser tratados como se tivessem a mesma dependência
temporal.

Os ajustes humanos continuam protegidos conforme a
[ADR 0009](0009-pedidos-de-correcao-com-aplicacao-direta.md). A autorização para
reajustar a sequência não libera sobrescrever silenciosamente uma escolha manual
incompatível. A nova geração paga de voz continua dependendo da
[ADR 0007](0007-autorizacao-humana-para-gerar-narracao.md).

A decisão favorece o reaproveitamento dos materiais e a continuidade automática
da montagem. Requer conhecer quais conteúdos dependem da fala e quais atravessam
cenas, em vez de apenas manter seus tempos absolutos antigos. A Q33 exige revisar
também o significado: uma mudança de sentido pode invalidar mídia mesmo sem mudar
a duração da fala. Correções sem mudança de sentido não disparam essa revisão,
mas continuam sujeitas às regras de voz e sincronia. Se fichas da bíblia visual
forem afetadas, suas imagens-base também entram na revisão. A adequação de
velocidade e congelamento depende do conteúdo: a prova técnica e o piloto devem
conferir movimento, intenção e continuidade, sem adotar um preenchimento que
apenas alcance a duração. Não foi imposto um limite numérico universal para
esses recursos. Este registro não autoriza implementação.
