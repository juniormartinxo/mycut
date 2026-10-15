---
version: 1
slug: web-src-sceneeditor-tsx
primary_target: web/src/SceneEditor.tsx
related_targets: [web/src/SceneEditorDialog.tsx, web/src/SceneEditor.css, web/src/SceneConversation.tsx, web/src/GoogleFontPicker.tsx]
---

# Composição de cenas

Modo: Operate. Extensão da aba Cenas, definida em três rodadas com o usuário.

## Direction contract

THESIS: selecionar um bloco na composição e editar seu objeto com prévia fiel,
mantendo as propostas de agentes visíveis antes de aceitar.

OWN-WORLD: herdar Manrope, papel claro, tinta verde, linhas discretas e ações
terracota do MyCut. Google Fonts pertence ao conteúdo do vídeo, não muda a
tipografia da aplicação.

STORY: clicar em Editar cena, abrir diretamente o editor em modal grande,
escolher um bloco e editar. Salvar grava sem fechar; Fechar mantém o rascunho.
O agente pode propor; o usuário compara, aceita ou descarta.

FIRST VIEWPORT: cabeçalho fixo com Editar cena, estado de salvamento, Salvar e
Fechar; corpo do modal com composição e coluna de comandos à esquerda dela,
abaixo do título do bloco selecionado: Duplicar, subir, descer, Excluir bloco.
Painel de propriedades com abas Bloco, Objeto e Agente. Pendências próximas
ao objeto e conversa na aba Agente. Em celular, composição e controles
empilham sem rolagem horizontal; os comandos continuam ao lado da composição.

Acesso direto solicitado pelo usuário em 15/10/2026. Cenas anteriores são
preparadas ao abrir, sem etapas de prévia/aceite da conversão. Salvar aplica
a nova composição; abrir a produção continua preservando o layout anterior.

CONTROLES: alças independentes nas bordas superior e inferior, além do canto
para largura. Imagem e vídeo oferecem slider de zoom de 100% a 500% em
Preencher com corte. Arrastar a própria mídia reposiciona o recorte, com cursor
de mão, resposta visual imediata e ação Centralizar recorte. O mesmo controle
aceita setas do teclado. São controles locais, mantendo o sistema existente.

FORM: extensão direta do sistema existente, com controles nativos rotulados,
campos numéricos e prévia produzida pelo mesmo compositor da exportação.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

REFERÊNCIA: reorganização solicitada pelo usuário com imagem em 15/10/2026.
Preservar a ordem vertical e a proximidade dos comandos com o bloco. Abas
com navegação por setas, Home/End e preservação dos rascunhos de edição/conversa.

AJUSTE DOS CAMPOS: Largura (%), Altura (%), Posição horizontal e Posição
vertical na mesma linha em painéis largos; duas colunas em painéis estreitos.
Importar imagem/vídeo usa botão secundário compacto com formatos e limite ao
lado; o seletor de arquivo nativo não aparece como parte do formulário.

NAVEGAÇÃO: cabeçalho reúne botões numerados 01, 02, 03… ao lado de Salvar/Fechar,
conforme referência do usuário. A cena atual usa fundo escuro. Trocar de cena
mantém rascunhos; Salvar grava o conjunto. Operações em curso desabilitam a
navegação. Mobile usa uma linha própria no cabeçalho, com rolagem horizontal
quando necessário. Não há setas nem seletor de cenas no modal.
