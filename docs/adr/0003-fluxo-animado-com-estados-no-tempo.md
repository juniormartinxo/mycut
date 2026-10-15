---
status: accepted
---

# Fluxo animado com estados internos no tempo

O editor de cenas ganha um quinto objeto visual, o **Fluxo animado**: um
motion graphics explicativo com nós, conexões, pulsos e gráficos que se formam
aos poucos, em sincronia com a narração. Ele é o recurso visual principal do
MyCut: os agentes devem usá-lo sempre que a fala descrever um processo, uma
sequência, causa e efeito, troca de dados ou números.

## Exceção à ADR 0001

A [ADR 0001](0001-composicao-de-cenas-em-blocos.md) mantém os objetos presentes
e estáticos durante toda a cena, sem tempos individuais. O Fluxo animado é uma
exceção contida: o objeto continua presente durante toda a cena e dentro do
próprio bloco, mas os seus **estados internos** mudam com o tempo. Os nós entram
em ordem, as conexões são traçadas, os pulsos percorrem as conexões e cada nó
reage (destaque, processamento, envio). O estado final, com o fluxo completo,
permanece até o fim da cena.

A [ADR 0004](0004-planos-fundo-e-comportamentos-no-tempo.md) amplia esta exceção com
planos, revelação de texto e movimento de câmera. Dentro de um plano, o fluxo
segue as âncoras da narração na janela daquele plano.

A exceção vale só para este objeto porque o movimento é o próprio conteúdo:
mostrar quem envia, quem recebe e o que acontece depois. Título, parágrafo,
imagem e vídeo continuam sem animação. Não há linha do tempo por objeto nem
keyframes livres. Também não há importação de Lottie ou After Effects.

## Autoria pelo agente

Por decisão do usuário em 15/10/2026, o Fluxo animado é montado inteiramente
pelo agente de direção: nós, ícones, posições, conexões, etapas, gráficos,
âncoras na narração e o ritmo da animação. O usuário não arrasta nós nem edita
posições. Ele escolhe **Fluxo animado** no bloco, o que dispara o pedido ao
agente, e revisa a proposta para aceitar ou descartar, como na
[ADR 0002](0002-propostas-de-agente-por-objeto.md). Na criação de um Short
(`/#/novo`), o diretor já coloca um Fluxo animado no bloco central das cenas
em que ele se encaixa.

## Modelo e tempo

Um fluxo tem até 8 nós, 10 conexões e 14 etapas, pensando na leitura no
formato vertical 9:16. Cada nó tem rótulo curto, ícone Lucide ou forma
simples, e posição e tamanho percentuais dentro do objeto. Um nó com gráfico
(barras, linha ou indicador) se constrói ao receber um pulso, com os valores
aparecendo junto com a forma. Os gráficos são parte do mesmo fluxo, e não um
tipo separado, para que possam formar uma única animação com os demais nós.

Uma etapa é um pulso de um nó para outro por uma conexão. O tipo **pedido**
(ida) usa um círculo na cor de destaque, e o tipo **resultado** (volta) usa um
losango na cor do texto, em uma trilha tracejada paralela. A diferença fica na
forma, além da cor. Uma etapa sem origem apenas ativa o nó, por exemplo para
construir um gráfico isolado.

A âncora de uma etapa é uma palavra ou trecho copiado da narração da cena. O
instante vem do alinhamento por palavra da narração gerada quando ela ainda
corresponde ao roteiro. Antes disso, usa a mesma estimativa da exportação.
Etapas sem âncora são distribuídas entre as âncoras vizinhas ou ao longo da
cena. Âncoras tardias são antecipadas para que a última reação termine dentro
da cena. Uma âncora que não está na narração gera um aviso e segue a
distribuição automática, sem bloquear a exportação.

## Desenho e paridade

O fluxo é desenhado como SVG em Python, em função do instante da cena, e
rasterizado pelo resvg com o mesmo arquivo da fonte Google Fonts do projeto. A
prévia animada do editor pede ao servidor os quadros de cada instante. Por
isso, prévia e MP4 usam o mesmo código, e a paridade é verificada por pixels em
três instantes da cena. Os ícones vêm de um subconjunto do Lucide (licença
ISC) versionado com licença e proveniência.

Um Fluxo animado ainda não montado, ou com rótulo que não cabe, pode ser salvo
como rascunho, mas bloqueia a exportação, como as pendências de texto e mídia.
