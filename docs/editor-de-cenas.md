# Editor de cenas em blocos

Na aba **Cenas**, selecione a cena e clique em **Editar cena**. O editor abre
diretamente em um modal grande, com **Salvar** e **Fechar** sempre visíveis.
Use os botões **01, 02, 03…**, ao lado de **Salvar** e **Fechar** no cabeçalho,
para trocar de cena sem fechar o editor. A cena atual fica destacada em escuro.
No celular, os números ocupam uma linha do cabeçalho e permitem rolagem
horizontal quando necessário. As edições das cenas visitadas permanecem no
rascunho. Cada clique em **Salvar** grava todas essas alterações sem fechar
o modal. A navegação fica indisponível enquanto uma operação está em andamento. Fechar (ou Esc)
mantém alterações pendentes no rascunho; elas ainda precisam ser salvas.

Cada cena nova começa com três blocos vazios de alturas
20%, 60% e 20%. Cada bloco ocupa uma linha exclusiva e aceita um título,
parágrafo, imagem ou vídeo. O limite desta versão é de 100 blocos por cena.

Selecione o bloco na composição ou na lista e escolha **Objeto do bloco**.
O painel separa as propriedades nas abas **Bloco**, **Objeto** e **Agente**.
Bloco reúne dimensões e posição; Objeto reúne conteúdo, estilo e recorte;
Agente reúne conversa, marcação e propostas. Trocar de aba mantém os rascunhos.
À esquerda da composição, abaixo do título do bloco selecionado, ficam
**Duplicar**, **Mover para cima**, **Mover para baixo** e **Excluir bloco**,
nessa ordem, em uma coluna. Títulos e parágrafos têm texto, família Google Fonts,
tamanho, cor e alinhamento próprios. O texto visual não modifica a narração.

As dimensões dos blocos são percentuais da área útil da cena; as dos objetos,
percentuais do bloco. Campos numéricos e alças permitem redimensionar ambos.
É possível apagar o valor e digitar outro, inclusive decimal, nas dimensões
e no tamanho da fonte. Valores válidos atualizam a composição durante a
digitação; ao sair de um campo vazio ou fora dos limites, ele volta ao último
valor válido. As setas do campo continuam disponíveis.
As alças também respondem às setas do teclado. Cada borda altera somente o
bloco e seu vizinho imediato, mantendo a borda oposta parada. O campo de altura
move a borda inferior; no último bloco, move a superior. O crescimento para
quando o vizinho chega a 0,1%. **Adicionar bloco** em uma cena
20/60/20 resulta em 15/45/15/25. É possível duplicar, mover ou excluir blocos,
mantendo pelo menos um, e remover somente o objeto.

**Desfazer** e **Refazer** mantêm o histórico da cena durante sua edição,
inclusive propostas aceitas. Salve as alterações para persistir a composição.
Marca do canal e legendas ocupam áreas reservadas fora dos blocos.

Na aba **Objeto**, títulos e parágrafos oferecem **Alinhamento vertical do
texto**: **Topo**, **Centro** ou **Rodapé**. O texto é alinhado dentro da sua
área; com altura de 100%, essa área ocupa toda a altura do bloco. **Posição
vertical** continua controlando a posição da própria área quando ela é menor
que o bloco. Cenas existentes mantêm o texto no topo até uma escolha explícita.
O alinhamento escolhido vale na prévia, no salvamento e no vídeo exportado.

## Fontes

Em **Formato**, escolha **Fonte dos blocos · Google Fonts**. Objetos herdam
essa família e a cor do projeto até receberem uma escolha própria. A fonte
dos layouts anteriores continua separada para preservar projetos existentes.

O catálogo local contém 1.949 famílias com estilo normal, obtidas do Google
Fonts em 15/10/2026. Esta versão seleciona famílias; não oferece seleção de
pesos, itálico ou eixos variáveis. Roboto está incluída no repositório com sua
licença OFL. A primeira escolha de outra família requer internet; o arquivo
TTF é baixado para `MYCUT_DATA_DIR/google-fonts/` e reutilizado offline. A
prévia e o exportador usam esse mesmo arquivo, sem substituição silenciosa
por uma fonte instalada na máquina. A interface do MyCut continua em Manrope.

A proveniência da Roboto está em `backend/mycut/fonts/Roboto/source.json`;
as fontes baixadas mantêm URL, peso e SHA-256 em seu próprio `source.json`.
O catálogo é um snapshot, sem dependência de consulta online ao abrir o editor.
Referências: [API CSS2](https://developers.google.com/fonts/docs/css2) e
[repositório oficial das famílias](https://github.com/google/fonts).

## Imagens, vídeos e pendências

Escolha um arquivo da biblioteca da produção ou use **Importar imagem** /
**Importar vídeo**. O botão abre o seletor de arquivos; os formatos e o limite
aparecem ao lado. Os campos **Largura (%)**, **Altura (%)**, **Posição horizontal**
e **Posição vertical** ficam juntos, em uma linha nos painéis largos e em duas
colunas nos estreitos. Imagens usam
a biblioteca existente. Vídeos aceitam MP4, MOV e WebM, até 100 MB, 180 segundos
e resolução de até 4K. **Mostrar inteiro** preserva todo o conteúdo;
**Preencher com corte** ocupa a área recortando o excedente e permite
**Zoom no recorte**, de 100% a 500%, sem alterar o tamanho do objeto. O zoom
vale para imagem e vídeo, na composição estática e na exportação.
Para escolher o ponto do recorte, selecione o bloco e arraste a própria mídia
na composição. O conteúdo acompanha o mouse, respeitando os limites do arquivo,
sem alterar zoom nem dimensões. As setas também reposicionam o recorte.
**Centralizar recorte** restaura o centro; Desfazer/Refazer inclui cada arraste.
Salvar persiste a posição usada na exportação. Ao voltar
a Mostrar inteiro, o zoom fica guardado para a próxima vez que usar o corte.

O vídeo começa no início do arquivo e é importado sem áudio. Ele repete quando
é mais curto que a cena e termina junto com ela quando é mais longo. A
composição estática mostra seu pôster; o controle de vídeo permite inspecionar
o arquivo, e a reprodução composta aparece na exportação.

Texto que não cabe e objetos de mídia sem arquivo podem ser salvos como
rascunho, mas bloqueiam a exportação. Corrija o conteúdo ou as dimensões; para
texto, **Ajustar fonte ao espaço** aplica explicitamente o tamanho sugerido.
Não há redução automática do tamanho escolhido.

## Conversas e propostas

A aba **Agente** abre uma conversa com alcance explícito:
objeto selecionado, bloco vazio ou cena inteira. O agente configurado no papel
de diretor recebe a cena e a narração como contexto. Precisa do runner e da
conexão do provedor já configurados no estúdio.

Marcar uma conversa não executa uma alteração. Mensagens e marcas persistem;
é possível resolver e reabrir conversas. Trocar o conteúdo preserva o histórico;
excluir seu alvo o arquiva. O histórico arquivado continua acessível.

Uma proposta aparece em **Revisar proposta**, com a cena atual e a sugerida.
**Aceitar proposta** aplica o conjunto; **Descartar** mantém a cena atual.
Propostas fora do alcance permitido são rejeitadas. Edições no alvo, geometria,
estilo ou narração tornam a proposta anterior desatualizada. A validação ocorre
novamente no servidor ao aceitar, inclusive se a edição ainda estava em rascunho.
O agente pode selecionar mídia da biblioteca; este editor não gera novos arquivos.

## Cenas anteriores

Cenas existentes continuam no renderizador anterior, inclusive em produções
que também contêm cenas com blocos. **Editar cena** prepara diretamente:
título no primeiro bloco, imagem existente ou diagrama rasterizado no segundo,
terceiro bloco vazio. O original só é substituído ao salvar no editor.
Isso também vale ao navegar para uma cena anterior: a preparação usa as
cores e o estilo atuais sem salvar automaticamente os rascunhos. Se falhar,
o modal oferece **Tentar abrir novamente** e permite voltar a outra cena.
Textos internos de diagramas convertidos deixam de ser editáveis individualmente.

As decisões de domínio estão no [glossário](../GLOSSARY.md), na
[ADR de composição](adr/0001-composicao-de-cenas-em-blocos.md) e na
[ADR de propostas](adr/0002-propostas-de-agente-por-objeto.md).

## Verificação

Resultado local em 15/10/2026:

| Verificação | Resultado |
| --- | --- |
| Suíte completa do backend | 100 testes passaram; 14 cenários de blocos revalidados após ajuste final de compatibilidade |
| Editor de blocos, desktop/celular | 22 cenários passaram, incluindo navegação no modal, rascunhos entre cenas, abas, mídia e recorte; um cenário foi repetido após interrupção da API de teste |
| Regressão de estúdio, formatos, cenas anteriores e navegação | 18 cenários passaram |
| Navegação com histórico controlado | 9 testes passaram |
| TypeScript e build Vite | Passaram |
| Download real de fonte Google Fonts | Lora instalada e servida como TTF local |

Os cenários de navegador incluem um download de fonte atrasado: editar texto e
tamanho durante a espera preserva ambas as alterações quando a fonte termina
de carregar. O fluxo do estúdio confirma renderização e download do pacote,
com o vídeo resultante acessível também na aba Cenas.

Os testes do backend ficam em `backend/tests/test_scene_blocks.py` e incluem
geometria e identidade, persistência, overflow, falta de mídia, cache offline,
conflitos, escopo, conversão e FFmpeg real. A exportação final usa áudio sintético
com alinhamento conhecido; não depende de síntese de voz ou transcrição externa.

```sh
PYTHONPATH=backend:backend/tests .venv-narration/bin/python -m unittest discover -s backend/tests
npm --prefix web run build
npm --prefix web run test:navigation
```

Use o ambiente Python que contém `backend/requirements-test.txt`; nesta
verificação ele foi `.venv-narration`, mas `.venv-app` também é suportado.
`web/tests/scene-blocks.spec.ts` verifica desktop e celular com API real:
edição, salvamento/reabertura, conversão, marcas, upload de imagem/vídeo,
enquadramento, zoom persistente, bordas independentes, limite do vizinho,
arraste e desfazer/refazer. Os testes de pixels conferem o zoom na imagem,
no pôster do vídeo, no frame decodificado e no MP4 exportado.

O cenário de proposta requer API e worker isolados, além de
`MYCUT_BLOCK_TEST_DATA` apontando para o mesmo diretório temporário sob `/tmp`.
A fixture `web/tests/fixtures/scene_agent_runner.py` simula exclusivamente a
resposta do provedor; persistência, fila, worker, validação e aceitação são reais.
Sem essa variável, esse cenário é explicitamente ignorado. O teste não qualifica
a qualidade nem a disponibilidade de um provedor real de IA.

A revisão visual independente aprovou desktop e celular, incluindo modal,
cabeçalho persistente, zoom e comparação de propostas. As alças superior e
inferior ficam na lateral da composição para não cobrir texto.
O detector visual não apontou achados. A verificação documental manteve o
sistema existente; registrou como preexistentes o sidecar de design desatualizado
e a ausência de `buildPath`, sem alterá-los nesta implementação.

Os testes usaram dados temporários. Duas finalizações do Playwright colidiram
na pasta de artefatos; os cenários passaram ao usar pastas exclusivas. Um teste
de proposta aguardou um worker isolado que havia encerrado; após restaurá-lo,
o reteste de propostas passou em desktop e celular.

API e worker locais foram atualizados após confirmar a fila de produção vazia.
Ambos executam a imagem `d3ce2b5d3071`; a API está saudável na porta
8322, conforme `.data/http.json` e a publicação atual do container. A
verificação HTTP somente de leitura confirmou o bundle
`/assets/index-NiVUldmn.js` com navegação numerada entre cenas, digitação numérica e
alinhamento vertical do texto.
Nenhuma cena da produção foi editada pelos testes. Não houve commit
ou publicação remota.

Na extensão de arraste do recorte, 15 testes de blocos passaram no backend e
6 cenários passaram no navegador (desktop/celular). Incluem persistência de
posição, preservação de zoom/dimensões, desfazer/refazer, centralização, setas,
limites e cancelamento de arraste. A conferência de pixels inclui os extremos
horizontal/vertical em imagem, pôster, frame de vídeo e MP4 exportado. Revisões
visual e documental independentes aprovaram essa extensão.

Na reorganização em abas, 18 cenários passaram em desktop/celular, incluindo
ordem e posição dos comandos, seleção após duplicar/mover/excluir, teclado
nas abas, preservação de rascunhos e regressão de fontes, mídia, recorte e
propostas. A revisão visual aprovou as quatro capturas de composição e painel
de propriedades; a documentação mantém essas escolhas locais à superfície.

O refinamento do upload e dos campos do objeto foi validado em quatro cenários
de navegador: seleção real pelo botão, upload de imagem/vídeo, edição e
persistência em desktop/celular. A revisão visual aprovou o botão compacto,
os rótulos curtos e os quatro campos alinhados, com duas colunas no mobile.

A navegação dentro do modal foi validada em desktop/celular: botões numerados,
destaque da cena atual, bloqueio durante operações, preservação dos rascunhos,
salvamento conjunto e nova tentativa após falha de conversão. Os 16 testes de
blocos do backend passaram, incluindo conversão com o estilo do rascunho sem
salvar outras edições. Revisões visual e documental independentes aprovaram
a navegação.

A edição por teclado e o alinhamento vertical foram verificados em 18 testes
de backend e oito cenários de navegador em desktop/celular. A cobertura inclui
apagar e redigitar, casas decimais, valores temporariamente abaixo do mínimo,
restauração de campos inválidos, setas, desfazer, persistência e comparação
dos pixels da prévia com um MP4 gerado pelo FFmpeg.

O cabeçalho com botões numerados passou nos quatro cenários de navegação e
recuperação em desktop/celular. A conferência visual com seis cenas confirmou
posição, destaque da cena atual e contraste sob hover; o teste de navegação
também verifica esse contraste.
