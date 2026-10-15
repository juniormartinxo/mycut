---
status: accepted
---

# Planos, fundo em tela cheia e comportamentos no tempo

O Short livre (MYC-2) pede cortes a cada 1,5–3 s, B-rolls em tela cheia, uma
ficha que aparece linha a linha e imagens com zoom. A
[ADR 0001](0001-composicao-de-cenas-em-blocos.md) mantém os objetos estáticos
durante toda a cena. A [ADR 0003](0003-fluxo-animado-com-estados-no-tempo.md)
abre uma exceção só para o Fluxo animado. Esta ADR amplia as duas. As decisões
foram tomadas no grilling de 15/10/2026 (Q4 a Q7) e implementadas no MYC-3.

## Cena → planos → blocos

A cena passa a ter um ou mais **planos**. A cena continua dona da narração e
da legenda. Cada plano tem uma composição própria em blocos, com as mesmas
regras da ADR 0001: linhas exclusivas, um objeto por bloco, alturas somando
100%. A tela dividida continua sendo dois blocos empilhados; não há colunas
nem sobreposição de blocos.

O primeiro plano é a composição da própria cena (`blocks`, `background`,
`brand`), e os planos seguintes ficam em `shots`, cada um com identificação
própria. Assim, toda cena existente já é uma cena de um plano só, sem
migração. O primeiro plano tem a identidade da cena, e reordenar planos
preserva essa identidade.

Um plano começa numa **âncora**: um trecho copiado da narração da cena,
procurado em ordem, como nas etapas do Fluxo animado. Sem âncora, ou quando o
trecho não está na fala, o plano é distribuído por igual entre os vizinhos
conhecidos, com um aviso no editor. Cada plano dura pelo menos 1 s; uma âncora
tardia é antecipada para caber. Se a cena for curta demais para todos os planos,
eles dividem o tempo disponível por igual, e o editor avisa.

Limites: até 12 planos por cena e 60 por Short, além dos 180 s já vigentes.

## Fundo do plano

Um plano pode ter um **fundo** que ocupa o quadro inteiro (1080×1920), atrás
dos blocos: cor, degradê linear (duas cores e ângulo, na convenção do CSS),
imagem ou vídeo. Imagem e vídeo preenchem com corte e aceitam zoom e posição
do recorte. O fundo pode ser escurecido até 80% para manter textos e legendas
legíveis. Sem fundo, vale o fundo do projeto, como antes.

A marca do canal pode ser desligada por plano, para B-rolls em tela cheia. A
legenda continua sobreposta, na área reservada. O fundo vale para qualquer
cena em blocos, inclusive nos Shorts com um dos quatro formatos, por pedido
explícito do usuário no grilling.

## Comportamentos no tempo

O tempo de cada plano começa no seu início. Vídeos recomeçam no plano, e os
Fluxos animados seguem as âncoras da narração dentro da janela do plano.

- **Revelação progressiva** de título e parágrafo: *linha a linha*, em que cada
  linha do texto (quebra manual) entra com um leve deslize ao longo dos
  primeiros 70% do plano, ou *digitação*, a pelo menos 18 caracteres por
  segundo, terminando até 80% do plano, com cursor na cor de destaque.
- **Movimento de câmera** em imagem (objeto ou fundo): aproximar, afastar e
  panorâmicas para os quatro lados, sobre um enquadramento de até 115%, ao
  longo do plano inteiro.
- **Transição de entrada** do plano: corte seco (padrão) ou fusão de 0,4 s com
  o plano anterior. A troca entre cenas é sempre um corte seco.

O estado sem instante, usado na composição estática do editor e na capa, mostra
o texto completo e o enquadramento inicial. Glitch, partículas e granulação
ficam fora desta versão. Não há linha do tempo livre nem keyframes por objeto:
o tempo vem só do plano e da narração.

## Desenho e paridade

Prévia e MP4 usam o mesmo código: a composição desenha o plano ativo em
função do instante da cena. A paridade é verificada por pixels em instantes de
planos diferentes, durante a revelação, durante o movimento e no meio de uma
fusão.

## Agentes

As propostas da [ADR 0002](0002-propostas-de-agente-por-objeto.md) valem por
plano. Um pedido sobre objeto ou bloco altera só o plano que o contém; o
alcance "plano inteiro" substitui o antigo "cena inteira" quando há mais de um
plano. O agente recebe somente a composição do plano e a sua posição na cena.
