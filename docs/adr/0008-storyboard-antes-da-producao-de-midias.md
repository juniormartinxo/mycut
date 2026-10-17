---
status: accepted
---

# Storyboard antes da produção de mídias

A primeira entrega dos agentes será um storyboard numa linha do tempo:
a fala orienta a sequência e as imagens e vídeos
planejados aparecem como esboços com ícones e descrições. O objetivo é revisar
o conteúdo antes de gastar com a produção de materiais que uma mudança na fala
poderia tornar desnecessários.

Essa decisão revisa a sequência discutida na Q2, em que os visuais poderiam
estar produzidos antes da avaliação humana do texto. A
[ADR 0007](0007-autorizacao-humana-para-gerar-narracao.md) continua válida quanto
à autorização humana para gerar a narração paga. O usuário confirmou as decisões
de tempo, ordem de produção e continuidade no editor ao aceitar Q6–Q8 em
2026-10-16.

## Representação

O storyboard relaciona cada trecho de fala com o que se pretende mostrar.
Textos na tela são apresentados por escrito; imagens e vídeos são representados
por ícones acompanhados de descrições. O esboço de mídia não requer gerar uma
imagem final nem uma imagem provisória como as usadas nos B-rolls dos Shorts.

Na Q24, o usuário autorizou uma exceção à ordem de produção visual: as imagens-base
da bíblia visual podem ser geradas durante o storyboard, antes da voz final. Elas
estabelecem personagens, cenários e estilo sem depender dos tempos da narração e
ajudam a revisar a aparência antes de autorizar a ElevenLabs. Isso não antecipa a
produção das mídias finais de cada cena, que continuam depois da voz final.

A referência visual traz duas cenas sucessivas, com uma área de mídia acima
e a fala abaixo. Ela exemplifica a relação entre conteúdos, sem obrigar toda
cena a ter título, uma única mídia ou uma composição fixa. A organização em
cenas e faixas continua seguindo a
[ADR 0006](0006-faixas-de-conteudo-e-agrupamento-por-cena.md).

## Tempo, produção e continuidade

- **Q6:** mostrar separadamente a fala exata, os textos na tela, sua exibição
  planejada e a duração estimada da fala/cena. A expressão "tempo de escrição"
  foi esclarecida pela aceitação dessa recomendação: duração prevista da fala/cena
  e período de exibição dos textos. Antes da geração da voz, a duração da fala
  é uma estimativa; depois, os tempos são ajustados à duração real. A decisão
  não define um controle de animação de escrita.
- **Q7:** revisar o storyboard, aguardar a autorização de geração, produzir a
  narração, ajustar os tempos e só então produzir as mídias finais e montar o
  vídeo. Aprovar o storyboard e autorizar um gasto são decisões distintas.
- **Q8:** o storyboard é o primeiro estado do próprio projeto na timeline;
  os materiais produzidos substituem seus esboços, preservando o trabalho revisado.

A resposta à Q12 acrescentou áudio de ensaio local antes da narração final,
conforme a [ADR 0010](0010-audio-de-ensaio-local-e-narracao-final.md). A Q15 reforçou
que a voz final sempre vem da API. A Q15a confirmou que, antes da autorização,
ficam disponíveis storyboard e áudio local de teste, acrescidos das imagens-base
permitidas na Q24; a produção das mídias finais ocorre depois da voz final e do
ajuste dos tempos.

Na Q20, o usuário definiu que a prévia pode ser gerada a qualquer momento, inclusive
com esboços, áudio de ensaio ou materiais pendentes. A exportação do vídeo finalizado
só acontece ao final, com as pendências resolvidas e a narração final da API.
Na Q25, o usuário acrescentou que afirmações factuais não verificadas não bloqueiam
a prévia. Antes da exportação final, cada uma precisa ser corrigida ou marcada
como "ciente" pelo autor. Essa ciência não transforma a afirmação em verificada.

O storyboard ainda exige pesquisa, roteiro e planejamento dos agentes. A
economia esperada vem de adiar a produção de mídia e o retrabalho sobre material
final; não há uma redução de tokens ou custo medida nesta sessão.

A [ADR 0012](0012-reajuste-da-montagem-apos-mudancas-na-fala.md) registra o reajuste
temporal aceito na Q26. Partes independentes podem continuar enquanto um clipe
aguarda importação, conforme Q20. A execução concorrente com edições humanas foi
definida nas Q30–Q31 e registrada na
[ADR 0013](0013-pedidos-registrados-e-resultados-vinculados-a-versoes.md). A Q47
condiciona a primeira exportação automática à resolução das pendências bloqueantes
de mídia, alinhamento e afirmações factuais, além da voz final exigida. A Q46
define a mixagem e a Q48 define os critérios do piloto; os contratos estão
consolidados no [plano de implementação](../plano-implementacao-video-horizontal.md).
Este registro documenta decisões de produto e não autoriza implementação.
