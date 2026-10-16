---
name: MyCut
description: Estúdio local para produzir Shorts por agentes e revisar seus materiais em português brasileiro.
colors:
  accent: "#bd4b28"
  accent-hover: "#a83d1b"
  accent-on: "#fffaf2"
  accent-soft: "#faeade"
  ink: "#292e29"
  muted: "#686d63"
  paper: "#f6f5f1"
  line: "#dcded4"
  sidebar: "#202621"
  surface: "#fffef9"
  field: "#fffefa"
  field-border: "#ced2c7"
  secondary: "#fffef8"
  secondary-on: "#41493c"
  secondary-hover: "#e9eddf"
  nav-on: "#c4c9be"
  nav-active: "#3a4538"
  nav-active-on: "#fffaf0"
  draft: "#eeeee6"
  draft-on: "#5d6256"
  ready: "#e5ecd8"
  ready-on: "#465833"
  working: "#f9e5d3"
  working-on: "#92552c"
  error: "#f7e0db"
  error-on: "#a23320"
typography:
  headline:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "31px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.03em"
  editor-title:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1.6
    letterSpacing: "-0.025em"
  section-title:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "17px"
    fontWeight: 730
    lineHeight: 1.5
    letterSpacing: "-0.02em"
  card-title:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.65
    letterSpacing: "-0.018em"
  supporting-copy:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "13px"
    lineHeight: 1.7
  field-label:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "13px"
    fontWeight: 650
  button:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1.4
  badge:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "10px"
    fontWeight: 700
    lineHeight: 1.5
rounded:
  badge: "5px"
  control: "7px"
  surface: "12px"
  preview: "13px"
spacing:
  gap-small: "8px"
  gap-control: "12px"
  inset-card: "20px"
  gap-section: "24px"
  inset-panel: "28px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-on}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.secondary-on}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  button-text:
    textColor: "{colors.accent}"
    padding: "8px 0"
  field:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "11px 13px"
  navigation:
    textColor: "{colors.nav-on}"
    rounded: "{rounded.control}"
    padding: "13px 12px"
  navigation-active:
    backgroundColor: "{colors.nav-active}"
    textColor: "{colors.nav-active-on}"
  badge-draft:
    backgroundColor: "{colors.draft}"
    textColor: "{colors.draft-on}"
    typography: "{typography.badge}"
    rounded: "{rounded.badge}"
    padding: "4px 7px"
  badge-ready:
    backgroundColor: "{colors.ready}"
    textColor: "{colors.ready-on}"
    typography: "{typography.badge}"
    rounded: "{rounded.badge}"
    padding: "4px 7px"
  badge-working:
    backgroundColor: "{colors.working}"
    textColor: "{colors.working-on}"
    typography: "{typography.badge}"
    rounded: "{rounded.badge}"
    padding: "4px 7px"
  badge-error:
    backgroundColor: "{colors.error}"
    textColor: "{colors.error-on}"
    typography: "{typography.badge}"
    rounded: "{rounded.badge}"
    padding: "4px 7px"
  project-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "0"
---

# Design System: MyCut

## Overview

**Creative North Star: "Folha de contato e mesa de revisão"**

MyCut organiza a produção por agentes a partir da pauta e de seus materiais: pesquisa, roteiro, cenas, capa, voz e versões. A navegação escura recua diante da área clara de acompanhamento, revisão e edição; o vídeo vertical recebe um lugar próprio de revisão. A densidade é de ferramenta de trabalho, com títulos diretos, controles compactos e separação entre etapas.

Esta é a linguagem implementada com direção escolhida em código, agora estendida a Conexões e Pauta e agentes. O objetivo autorizado desde o início é a produção por agentes; a entrega inicial limitada ao editor manual foi uma decisão do implementador, não uma redução de escopo aprovada pelo usuário. A edição manual permanece disponível para ajustes. A interface mantém Manrope, superfícies quentes e ações terracota entre projetos; a capa e a cor do vídeo pertencem à produção, e o laranja do Short sobre Claude não constitui uma regra permanente da marca.

**Key Characteristics:**

- Conteúdo real como identidade de cada produção.
- Navegação escura, superfícies claras e ações terracota.
- Tipografia Manrope local e numeração funcional das cenas.
- Edição e prévia vertical lado a lado no computador.
- Estados textuais para conexões, etapas dos agentes, produção e revisão.
- Histórico com acesso aos materiais existentes de cada execução.

**Evidência e alcance.** Extração de [styles.css](web/src/styles.css), [App.tsx](web/src/App.tsx), [Automation.tsx](web/src/Automation.tsx), [Connections.tsx](web/src/Connections.tsx) e [types.ts](web/src/types.ts), com importação local de Manrope em [main.tsx](web/src/main.tsx), alinhada a [PRODUCT.md](PRODUCT.md) e [direction.md](.impeccable/direction.md). Os nomes descritivos organizam valores existentes; não são novas variáveis da aplicação. O handoff de 14/10/2026 informa a correção e revisão das três falhas funcionais — rascunho, erro de voz e histórico —, 24 testes Python aprovados e verificações TypeScript, Vite e Compose válidas. As fronteiras externas de CLI e ElevenLabs foram simuladas nos testes: isso não qualifica uma execução real nesses serviços.

A extensão de seleção de modelos e testes por agente foi extraída de [AgentConnections.tsx](web/src/AgentConnections.tsx), [Connections.tsx](web/src/Connections.tsx), [agent_models.py](backend/mycut/agent_models.py) e [agent_tests.py](backend/mycut/agent_tests.py). Preserva a identidade e os tokens acima. A revisão fresca mantém **recapture** e confirmou por fonte a correção do aviso de polling que persistia após recuperação. O registro anterior de 24 testes pertence ao handoff anterior; os resultados atuais de build e testes ficam em [verificacao-studio.md](docs/verificacao-studio.md), sem promover testes simulados a qualificação externa real.

A disposição visual permanece **recapture**: faltam screenshots atuais e inspeção da UI, com TCP, Chromium e Docker bloqueados no ambiente de verificação. Não há aprovação visual. Frames do vídeo renderizado não validam a interface. Composição desktop/móvel, overflow em 390px e foco no navegador precisam de nova captura e verificação. O sidecar usa schemaVersion 2 e não cria rampas tonais inexistentes no CSS.

## Colors

A paleta combina terracota, papel quente e neutros com matiz verde. O frontmatter contém os valores normativos; cores locais adicionais aparecem nos trechos de componentes do sidecar quando necessárias para reproduzir a implementação.

### Primary

- **Terracota de ação — `accent`:** ações principais, links de ação, aba selecionada, progresso e cursor de texto. `accent-hover` escurece o botão principal; `accent-on` é seu texto claro.
- **Terracota suave — `accent-soft`:** fundo das instruções para conectar o executor, reutilizando a variável já declarada no CSS.

### Neutral

- **Tinta verde — `ink`:** leitura e títulos. `muted` reduz a ênfase das descrições e dos metadados.
- **Papel de trabalho — `paper`:** fundo do aplicativo. `surface` delimita fichas e painel de edição; `field` diferencia campos editáveis. `line` organiza divisões.
- **Verde de bastidor — `sidebar`:** navegação persistente. Os tokens `nav-*` definem texto e seleção nesse contexto escuro.
- **Papel de ação secundária — `secondary`:** salvar, assistir e baixar, com seus estados de texto e hover.

Estados usam pares próprios: `draft` para edição ou conexão ausente, `working` para execução, `ready` para resultado disponível ou conexão reportada e `error` para falha. A legenda textual distingue cada contexto; “Pronto para revisar” não afirma aprovação final. As etapas dos agentes usam pontos com cores locais de sucesso e falha, terracota durante execução, contorno enquanto pendentes e contorno tracejado quando dispensadas (a Pesquisa de um Short livre sem afirmações factuais). Mensagens reais acompanham os pontos. Avisos têm cores locais próprias, extraídas no sidecar.

**The Cor da Produção Rule.** A cor editável do vídeo fica restrita à capa provisória e à composição da cena; não substitui a cor de ação do aplicativo.

## Typography

Manrope Variable é importada pelo pacote Fontsource, com fallback sans-serif. A mesma família sustenta títulos, formulários, navegação e metadados; pesos variáveis estabelecem hierarquia.

Os papéis `headline`, `editor-title`, `section-title` e `card-title` correspondem ao título da biblioteca, ao título do editor, ao cabeçalho de etapa e à produção na biblioteca. `supporting-copy` descreve o parágrafo sob o título da página: não existe tamanho universal de body explicitamente definido no CSS. `field-label`, `button` e `badge` capturam os controles recorrentes.

Títulos usam quebra balanceada; nomes de produções e arquivos aceitam quebra de palavras longas. Duração, cenas e limite de caracteres usam algarismos tabulares. Narração usa entrelinha própria (1.85), alterada a (1.8) no breakpoint móvel. A ajuda tem largura máxima (60ch); não existe medida global de parágrafo.

**The Uma Família Rule.** Preserve Manrope e use os papéis tipográficos existentes para diferenciar conteúdo, controle e metadado.

## Layout

O shell combina navegação (228px) e área flexível com largura mínima zero. A barra superior tem altura (72px). Biblioteca e fila compartilham espaçamento externo; a biblioteca tem limite de largura (1600px), enquanto a área de cartões termina em (1180px). A grade tem colunas com mínimo (270px), intervalo (24px) e cartões de até (370px).

O editor tem limite de largura (1720px), coluna editável flexível, prévia (310px) e intervalo (28px). As abas permanecem em uma linha com rolagem horizontal. O player tem proporção (9:16), largura disponível e altura máxima inicial (555px). Cenas, fila e versões usam listas com divisores.

Conexões usa largura máxima (1180px), preenchimento (40px 42px 70px) e seções separadas por divisores. Cada papel de agente combina descrição, CLI e modelo em três colunas (`minmax(180px, 1.2fr) minmax(0, 0.8fr) minmax(0, 1.4fr)`); ajuda e teste ocupam as duas últimas colunas. Cada papel termina em divisor fino, sem cartão adicional. Ações de catálogo e teste mantêm texto e botão lado a lado, com intervalo (18px); o texto introdutório tem medida máxima (68ch). Os ajustes de voz usam duas colunas. Pauta e agentes ocupa o mesmo painel de edição. As etapas aparecem em lista vertical, sem uma nova superfície elevada. Os links de materiais no histórico quebram em múltiplas linhas.

| Condição no CSS | Comportamento implementado |
| --- | --- |
| A partir de 1550px | Prévia com 350px, intervalo de 38px e maior espaço interno no painel. |
| Até 1250px | Navegação com 190px; cabeçalho do editor em duas linhas; prévia com 270px. |
| Até 1000px | Navegação com 74px e ícones; prévia com 250px. Os textos dos botões continuam no DOM. Em Conexões, descrição e área de teste ocupam linhas inteiras; CLI/modelo ficam em duas colunas; cabeçalhos e formulário de chave empilham. |
| Até 760px | Navegação horizontal no topo; edição acima da prévia; painel de prévia limitado a 380px; grade com mínimo de 245px. Título da página reduzido a 25px e do editor a 16px. |
| Até 540px | Papéis de agentes e ajustes de voz usam uma coluna; texto e botão de catálogo/teste empilham; ações de automação ocupam a largura disponível; Conexões tem preenchimento de 25px 22px 45px. |

Os espaçamentos nomeiam medidas recorrentes existentes, não uma escala imposta retroativamente. Essas regras responsivas não comprovam ausência de overflow.

## Elevation & Depth

A separação principal vem de superfície e borda fina. O cartão de produção recebe sombra suave no hover; o player mantém sombra para destacar o material em revisão. Não há sistema amplo de níveis de elevação. Os dois valores extraídos ficam em `extensions.shadows` do sidecar.

**The Profundidade Local Rule.** Reserve a sombra persistente para a prévia e a sombra de resposta para o cartão de produção, conforme os usos atuais.

Transições acompanham estados: fundo dos botões e borda dos campos (0.16s), cartão (0.22s), progresso (0.4s). O easing exponencial de `--ease` é usado na sombra do cartão. O indicador de execução gira (1.4s, linear). Não há animação de entrada implementada. Movimento reduzido desliga animações e transições.

## Shapes

Controles têm cantos discretamente arredondados; fichas e painel têm cantos mais amplos. Os raios canônicos estão em `rounded`. Selos de estado são pequenos retângulos com ponto circular. O player mantém recorte vertical próprio. Importação usa borda tracejada; opções de criação de produção usam borda contínua e fundo de seleção. Modelos de agentes usam select nativo com o mesmo raio dos campos.

A marca vem de `/mark.svg`; os ícones de interface vêm de Lucide, em traço. Miniaturas conservam a imagem completa com `object-fit: contain`. A cena provisória combina texto e relações geométricas, e é distinta do vídeo renderizado.

## Components

### Buttons

A ação principal usa terracota; a secundária usa papel com borda; a textual usa cor sem caixa. A altura mínima base é (40px), com ajustes locais para ações compactas. Hover muda o fundo. Foco visível aplica contorno de destaque (3px) e afastamento (4px). Desabilitado usa opacidade (0.48) e cursor indisponível. Não há tratamento específico de pressionamento.

### Chips

Os selos combinam texto, cor e ponto para comunicar o estado real. São indicadores, não filtros ou botões; o sidecar não lhes atribui interação inexistente.

### Cards / Containers

A ficha de produção é um único botão: capa ou composição provisória, estado, título, cenas, presença de voz e data. O painel de edição agrupa as etapas em uma superfície contínua. Fila e versões usam linhas.

Conexões mantém a mesma linguagem de formulários, botões e selos em seções abertas. O estado do executor e a presença da chave ElevenLabs aparecem junto dos respectivos títulos, sem sugerir uma produção concluída.

### Inputs / Fields

Campos têm fundo claro, borda fina e rótulo persistente. Hover escurece a borda; placeholder tem cor própria; desabilitado recebe superfície atenuada. Cursor e seleção usam a paleta. Roteiro tem fundo e entrelinha específicos. Importação combina input de arquivo, botão visível e indicação do arquivo atual. Pauta recebe texto ou link. CLI, modelo e voz usam controles nativos; estabilidade, semelhança e velocidade usam ranges com destaque terracota. A chave ElevenLabs usa campo de senha e é limpa após conexão bem-sucedida.

### Modelos e testes por agente

Os seletores nativos de CLI e Modelo têm nomes acessíveis específicos do papel. Modelo apresenta “Padrão do CLI” e as opções nome/ID recebidas do catálogo. Trocar o CLI limpa o modelo escolhido. Um ID salvo que deixou de constar na lista permanece visível como opção desabilitada “selecione novamente”; `aria-invalid`, borda de falha e ajuda associada por `aria-describedby` explicam a correção. A presença do ID no catálogo valida a seleção, não o acesso da conta.

“Atualizar modelos” solicita atualização ao executor disponível. A ajuda mostra origem e horário, ou erro/ausência de lista. Codex e Grok usam caches locais; Claude fornece IDs resolvidos pela inicialização do protocolo do CLI, sem prompt de inferência. A atualização acontece quando o executor está ocioso. Uma falha pode conservar o catálogo anterior acompanhado do erro; nem catálogo salvo nem inicialização do CLI comprovam permissão, cota ou acesso ao modelo.

“Testar agente” envia a escolha atual de CLI/modelo e o papel, antes de “Salvar agentes”; não altera a configuração salva. O teste faz uma solicitação curta real pela fila do executor, consome a cota do CLI e não gera áudio nem vídeo. A resposta precisa cumprir um desafio e um cálculo com estrutura definida. Existe apenas um teste ativo por vez, com prazo de três minutos a partir da solicitação, incluindo a espera na fila. O executor precisa estar conectado com protocolo compatível e o CLI selecionado disponível. Durante o teste, os seletores daquele papel ficam bloqueados e a ação muda para “Cancelar teste”.

O resultado permanece junto ao papel, em texto aberto com ícone, horário, CLI, ID solicitado, tempo quando retornado, resposta curta e erro quando presente. É anunciado por `role="status"` e `aria-live="polite"`. Falha ou divergência de modelo usa a mesma cor local já aplicada às etapas com falha; o texto explica a diferença. A confirmação de identidade usa exclusivamente as chaves de `modelUsage` com tokens consumidos no envelope de saída de Claude/Grok; conteúdo escrito pelo próprio modelo não conta como evidência.

| Evidência do teste | Estado e apresentação |
| --- | --- |
| ID explícito e único modelo reportado igual ao solicitado | `match`: “Respondeu · modelo confirmado pelo CLI”. |
| ID explícito e modelos reportados diferentes, inclusive mais de um | `mismatch`: “Respondeu · modelo diferente do selecionado”. |
| Solicitação com padrão do CLI e metadados de uso disponíveis | `resolved`: “Respondeu · modelo padrão identificado”, com os IDs reportados. |
| Resposta válida sem metadados aceitos de uso | `unknown`: “Respondeu · modelo não informado pelo CLI”; confirma resposta, sem confirmar identidade. |

Codex permanece em `unknown` nesta implementação, mesmo quando responde corretamente: o parser não aceita seus dados como confirmação de modelo. O teste também distingue fila, espera de resposta, cancelamento solicitado, cancelado, expirado e falha. Cancelar um teste em execução apresenta “Cancelando teste…” até a confirmação; o cancelamento em fila pode finalizar imediatamente. Recarregar consulta novamente o último teste de cada papel no servidor. Isso não persiste escolhas locais ainda não salvas; se a seleção atual difere da testada, um aviso identifica o resultado como pertencente à seleção anterior.

**The Modelo Reportado Rule.** Separe resposta válida, modelo reportado pelo CLI e acesso da conta; catálogo ou declaração do próprio modelo não confirma identidade nem permissão de uso.

### Navigation

A navegação principal contém Produções, Fila de produção e Conexões. Seleção e hover usam superfícies próprias. Pauta e agentes, Roteiro, Cenas, Áudio, Capa, Publicação e Versões têm linha terracota na aba selecionada. O markup declara `tablist`, `tab`, `tabpanel` e suas relações; isso não comprova navegação completa por setas. Foco e operação por teclado exigem teste no navegador.

### Pauta, conexões e etapas

Novo Short começa em “Da pauta ao Short.” e oferece Short completo, Roteiro e cenas primeiro ou Abrir editor vazio. A produção completa exige pauta, executor online, CLIs selecionados encontrados e voz configurada. A opção de planejamento não exige voz. A interface diferencia disponibilidade reportada de uma execução: detectar um CLI não comprova que seu login funciona. Gerar voz informa uso de créditos; conectar e listar vozes não gera narração.

A galeria de formatos tem um quinto cartão, **Livre**, sem prévia renderizada: ícone e texto sobre papel com borda tracejada. Escolhê-lo troca “Pauta ou link” por “Prompt do Short livre”, um campo alto na mesma tipografia Manrope, oculta a personalização de aparência, o conteúdo visual e “Abrir editor vazio”, e mostra “Anexar referências”: um botão secundário sobre input de arquivo, com as imagens listadas em fichas removíveis (raio de controle). Escolher outro formato sai do Livre. No editor de um Short livre, a aba Pauta e agentes mostra o prompt sem a galeria e os avisos dos agentes numa caixa de aviso com lista. Depois da direção, a seção “Estilo gerado” abre com um divisor fino, sem cartão: amostras de 20px (raio de controle) para fundo, texto e destaque com o código da cor, e uma linha de apoio com a fonte, a legenda e o loop. Na aba Roteiro, as pausas aparecem sob a narração da cena em texto de metadado (“Pausa de 0,8 s depois de …”). Uma pausa cujo trecho saiu da narração ganha a cor de erro e o complemento “não aplicada: o trecho não está na narração”. Na aba Publicação, o “Pacote de publicação” vem abaixo do formulário, também após um divisor: opções de título numa lista numerada, com “Usar este título” (botão secundário compacto) ou “Em uso”, e hashtags e comentário fixado com “Copiar”, que vira “Copiado” por 2 s. O comentário fica num bloco de papel com raio 7px, que preserva as quebras de linha.

Com Livre escolhido, **Novo** ganha o grupo “Imagens da Arte”, no mesmo padrão de opções de “O que produzir”: conferir as imagens-base primeiro (padrão), gerar todas ou nenhuma, com uma linha de apoio que dá o teto (até 12 imagens) e a estimativa pelo preço por imagem. O editor de um Short livre ganha a aba **Arte**, depois de Publicação. A bíblia visual abre a aba em texto corrido: o tom em cor de apoio e as fichas numa lista de definição. Depois vem a ação principal, “Gerar as N imagens que faltam” (com “e continuar a produção” quando a produção parou nas bases), com a estimativa e a última estimativa gravada logo abaixo, e as etapas da última execução. As imagens-base e as imagens das cenas vêm em dois grupos separados por divisor fino. Cada pedido é uma linha com a moldura da imagem à esquerda (150px, raio padrão, papel mais escuro com o estado quando ainda não há imagem) e, à direita, título, estado, proporção e referências em metadado, o prompt num `details`, as orientações já enviadas e o formulário “Orientação para a Arte”, com “Anexar exemplo” e “Refazer com esta orientação”. Falha e imagem feita com uma base anterior aparecem na cor de erro. Até 640px, a moldura vai para cima do texto.

Depois da Arte vem a aba **Materiais**, também só no Short livre. Quando falta algum clipe, uma caixa de aviso “Clipes de B-roll que faltam” abre a aba com o título no plural ou no singular, uma linha por B-roll (número, título, cena e plano, ferramenta e duração) e o prompt num `details` e a explicação de que a exportação continua liberada. A mesma caixa, com “Abrir a lista de materiais”, aparece na Pauta e agentes e em Cenas. A lista é numerada e repete a linha dos pedidos da Arte: moldura 9:16 de 120px à esquerda (a imagem provisória, o clipe de imagem ou o pôster do vídeo), título com o badge de estado (“Aguardando clipe” em badge-working, “Clipe importado” em badge-ready), ferramenta e duração em metadado, onde entra, as referências como miniaturas de 32px com link para baixar, o prompt em monoespaçada com “Copiar” e “Importar clipe” como botão principal (“Trocar clipe”, secundário, depois do clipe). No editor, o plano que aguarda o clipe ganha um ponto na cor de destaque na faixa de planos e uma pílula escura “Aguardando clipe” no canto da composição, que fica fora da prévia e do MP4; a aba Plano abre o grupo “B-roll deste plano”, com borda no destaque enquanto aguarda.

O rascunho da nova produção — pauta, título, opção escolhida e anexos — fica no estado de App e sobrevive à ida a Conexões e ao retorno pela navegação interna. É limpo depois da criação bem-sucedida; não há persistência desse rascunho após recarregar ou fechar a aba. No editor de projeto existente, sair com alterações não salvas continua sujeito à confirmação de descarte.

Etapas apresentam Pesquisa, Roteiro, Animações, Conferência, Arte, Narração e Vídeo conforme o tipo de execução; a Arte só aparece quando a execução a registrou. Nome, ponto de estado e mensagem formam uma linha. Etapas sem registro mostram “Aguardando”, ou “Não executada” depois de falha/cancelamento. Trabalho apenas de narração mostra a etapa de voz; render isolado não mostra essa lista. O fluxo implementado conecta agentes CLI, ElevenLabs e render; agendamento diário e envio ao YouTube continuam pendentes, como partes do objetivo original.

**The Estado com Evidência Rule.** Use o estado e a mensagem da execução ou conexão correspondente; não apresente disponibilidade de CLI, chave salva ou etapa concluída como prova de todo o fluxo concluído.

### Histórico e materiais

Cada execução identifica Roteiro e cenas, Narração, Vídeo final ou Prévia, junto de mensagem, data e revisão. Os links são derivados de `materials`: Entrada anterior, Roteiro, Publicação, Capa, Áudio e outros arquivos retornados. “Assistir” aparece somente em execução bem-sucedida com saída de vídeo. Planejamento e voz preservam acesso aos seus materiais sem criar um player inexistente. A seleção de vídeo não apaga as demais versões.

### Prévia e sequência de cenas

O espaço 9:16 mostra o player nativo quando há resultado; antes disso, mostra a composição estática. Texto adjacente distingue versão anterior, ausência de narração e revisão final pendente. A sequência abaixo liga cada cena ao editor. Downloads aparecem quando existe resultado.

**The Revisão Explícita Rule.** Mantenha visíveis a atualidade do resultado, a presença de narração e a necessidade de revisão; a aparência de um player pronto não substitui esses estados.

### Feedback

Falhas usam `role="alert"`; mensagens comuns usam `role="status"`. Progresso possui nome acessível e valor da execução. Carregamento, vazio e erro têm mensagens específicas. A última falha de execução aparece acima das abas do editor, inclusive quando a falha foi na geração de voz, acompanhada de orientação para conferir conexões ou ajustar o conteúdo. A interface distingue API, worker, executor de CLIs e ElevenLabs. Publicação ainda é manual na implementação atual; a interface explicita que agendamento e envio ao YouTube não estão conectados.

Erros de atualização periódica de Conexões e dos testes ficam separados dos erros de ações e desaparecem após a próxima consulta bem-sucedida. Uma resposta de polling iniciada antes de um teste novo não apaga esse teste; o polling também não regride “Cancelando” para fila ou execução. Os campos em edição não são sobrescritos pela atualização periódica.

## Do's and Don'ts

### Do:

- **Do** preservar a capa real e a cor de cada produção no contexto do vídeo.
- **Do** reutilizar Manrope, os papéis tipográficos e os pares de cor extraídos.
- **Do** manter rótulos para fila, falha, resultado anterior e revisão pendente.
- **Do** preservar o rascunho durante a navegação para Conexões e os materiais reais de cada execução no histórico.
- **Do** distinguir executor, CLI disponível, voz configurada e estado das etapas.
- **Do** mostrar origem do catálogo, seleção testada e limites dos metadados de modelo ao apresentar um resultado.
- **Do** aplicar foco visível, estados desabilitados e preferência de movimento reduzido.
- **Do** verificar a interface no navegador antes de afirmar aprovação visual.

### Don't:

- **Don't** promover o laranja do conteúdo Claude a restrição permanente da marca MyCut.
- **Don't** preencher a biblioteca com produções, datas ou métricas fictícias.
- **Don't** apresentar a composição estática como reprodução do vídeo final.
- **Don't** confundir resultado disponível com resultado revisado ou publicação automática.
- **Don't** apresentar o editor manual como substituição autorizada do objetivo de produção por agentes.
- **Don't** apresentar testes com serviços externos simulados como execução real qualificada desses serviços.
- **Don't** tratar catálogo, ID salvo ou resposta escrita pelo modelo como prova de acesso ou identidade; Codex não confirma identidade nesta implementação.
- **Don't** tratar screenshot do vídeo como evidência visual da interface.
