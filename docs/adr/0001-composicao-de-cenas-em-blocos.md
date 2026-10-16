---
status: accepted
---

# Composição de cenas em blocos com um objeto visual

O editor de cenas dos Shorts adotará blocos empilhados verticalmente, cada um
em uma linha exclusiva, contendo zero ou um objeto visual. Reduzir a largura
de um bloco deixa espaço livre ao lado, sem permitir que outro bloco ocupe a
mesma linha. Essa restrição foi escolhida em vez de múltiplos objetos,
colunas e sobreposições para manter a primeira versão previsível.

A cena começa com três blocos nas proporções de altura 20%, 60% e 20%, e o
usuário pode acrescentar blocos. Cada bloco começa com 100% da largura e
permite ajustar largura, altura e alinhamento horizontal. O objeto também
permite ajustar largura e altura. O dropdown oferece título, parágrafo,
imagem e vídeo; título e parágrafo permitem editar fonte, tamanho, cor e
alinhamento. Usuários e agentes podem criar e editar esses objetos.

Os blocos e objetos permanecem presentes durante toda a cena. Um objeto de
vídeo reproduz dentro de sua área, sem tempos individuais de entrada e saída
dos objetos nesta versão. Isso mantém o escopo na composição espacial, sem
introduzir uma linha do tempo por objeto. O Fluxo animado é a exceção registrada na
[ADR 0003](0003-fluxo-animado-com-estados-no-tempo.md): continua presente na
cena inteira, mas seus estados internos mudam com a narração. A
[ADR 0004](0004-planos-fundo-e-comportamentos-no-tempo.md) amplia esta decisão:
a cena passa a ter planos, cada um com sua composição em blocos e um fundo em
tela cheia, e título, parágrafo e imagem ganham revelação e movimento de câmera.

## Dimensionamento e conteúdo

A marca do canal e as legendas permanecem fora dos blocos, em áreas reservadas.
As proporções dos blocos são calculadas sobre a área útil restante. As alturas
somam 100%: adicionar ou remover um bloco redistribui proporcionalmente o
espaço dos demais. Redimensionar uma borda ajusta somente o vizinho imediato,
mantendo a borda oposta parada. Essa regra substitui a redistribuição global
no redimensionamento, conforme correção solicitada pelo usuário em 15/10/2026. Ao adicionar um quarto bloco, ele
recebe 25% e os anteriores passam de 20/60/20 para 15/45/15.

Largura e altura são editadas em porcentagem, por campos numéricos e alças de
redimensionamento: o bloco é relativo à área útil e o objeto é relativo ao
bloco. O objeto fica contido no próprio bloco, com alinhamento horizontal e
vertical ajustável. Texto que não cabe é sinalizado na prévia e impede a
exportação até ser corrigido; a ação explícita "Ajustar fonte ao espaço"
permite resolver o excesso sem reduzir silenciosamente o tamanho escolhido.

Título e parágrafo são independentes da narração. Alterá-los modifica apenas
a composição visual; mudar a narração exige uma ação explícita, pois pode
exigir novo áudio e novos tempos de cena.

## Mídia

Imagens e vídeos vêm de upload ou da biblioteca do projeto. O enquadramento
oferece "mostrar inteiro" (padrão) ou "preencher com corte". No corte, o usuário
pode aplicar zoom de 100% a 500% sem modificar a geometria do objeto, tanto
para imagem quanto para vídeo, com o mesmo enquadramento na prévia e exportação.
O ponto do recorte é independente da posição do objeto: arrastar a mídia
desloca seu conteúdo dentro da área. A posição horizontal e vertical do
recorte varia de 0 a 100%, começa em 50/50 e respeita os limites da imagem.
Usuários e agentes podem alterar esses valores; o editor oferece retorno ao
centro. Esse arraste foi solicitado pelo usuário após experimentar o zoom. O agente pode
selecionar mídia disponível; a geração de novas mídias é uma capacidade
separada.

O vídeo começa no início do arquivo, sem seu áudio original. Se for mais
longo que a cena, termina com ela; se for mais curto, repete até o fim da
cena. A narração do Short continua sendo o áudio principal.

## Compatibilidade

Projetos existentes preservam seus layouts e resultados atuais. O botão
**Editar cena** abre diretamente um modal grande e prepara a cena em blocos;
**Salvar** aplica a nova composição sem fechar o editor. Novas cenas já
começam com blocos. Abrir um projeto não altera sua composição anterior.

Em 15/10/2026, após experimentar a primeira interface, o usuário substituiu
explicitamente as etapas de prévia e aceitação da conversão por esse acesso
direto, com botões Salvar e Fechar. Fechar mantém edições pendentes no rascunho
da produção; cada clique em Salvar persiste a versão atual. A navegação
no próprio modal oferece botões numerados ao lado de Salvar/Fechar, com a
cena atual destacada, conforme ajuste visual solicitado pelo usuário. Trocar
de cena mantém os rascunhos; Salvar persiste as alterações de todas as cenas
visitadas. Preparar uma cena antiga durante a navegação não salva esses
rascunhos automaticamente.

## Operação do editor

As propriedades ficam nas abas Bloco, Objeto e Agente. Os comandos Duplicar,
Mover para cima, Mover para baixo e Excluir bloco ficam em uma coluna à esquerda
da composição, sob o título do bloco selecionado, conforme referência enviada
pelo usuário. Trocar de aba preserva os rascunhos.

Cenas criadas manualmente começam com os três blocos vazios. O usuário pode
adicionar, reordenar, duplicar ou excluir blocos, mantendo pelo menos um;
remover apenas o objeto mantém seu bloco. Desfazer/refazer durante a edição
inclui geometria, exclusões, troca de tipo e propostas aceitas. Blocos vazios
exibem apenas o fundo no vídeo. Objetos de mídia sem arquivo permitem salvar
o rascunho, mas impedem a exportação até selecionar a mídia ou remover o objeto.

Título e parágrafo herdam fonte e cor do projeto até serem personalizados;
mudanças globais preservam propriedades personalizadas. Por solicitação
expressa do usuário, as fontes do novo editor vêm do Google Fonts, em vez
das quatro famílias locais anteriormente propostas. Título e parágrafo têm
tamanhos iniciais próprios.

Na conversão de cenas antigas, o título ocupa o primeiro bloco, a imagem
existente ou uma imagem do diagrama ocupa o segundo e o terceiro fica vazio.
Um diagrama convertido em imagem não mantém a edição individual dos seus
textos. A composição preparada aparece no editor antes de salvar.

As decisões deste registro foram confirmadas nas três rodadas da entrevista
em 2026-10-15, com a correção explícita de fonte para Google Fonts. O usuário
confirmou o entendimento compartilhado e autorizou a implementação.
