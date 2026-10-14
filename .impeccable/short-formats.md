# Formatos de Shorts

Mode: Operate. Extensão da criação e do editor existentes; identidade do aplicativo preservada.

## Direction contract

THESIS: escolher o visual antes da produção por meio de quatro exemplos comparáveis, feitos pelo próprio renderizador. O formato governa composição e movimento, além das cores.

OWN-WORLD: Manrope, papel quente, campos compactos e ações terracota no aplicativo. Editorial, Radar tech, Passo a passo e Impacto são linguagens do vídeo, sem substituir os tokens do MyCut.

STORY: informar a pauta, escolher um formato, ajustar fonte e paleta, permitir ou não imagens, iniciar os agentes. No editor, revisar e substituir a mídia de cada cena sem regravar a voz.

FIRST VIEWPORT: a pauta precede uma galeria de quatro miniaturas verticais; no celular, duas por linha. A opção selecionada mostra a personalização real. Fonte e três cores ficam agrupadas abaixo; modo visual e origem das imagens fecham a seção. A ação de produzir continua no formulário existente.

FORM: extensão direta solicitada pelo usuário, sem nova identidade ou sorteio de conceitos. As imagens de exemplo são diagramas sintéticos explicitamente identificados; não são notícias ou produções reais.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Conferência documental da extensão — 14/10/2026

Comparados `PRODUCT.md`, `DESIGN.md` e `.impeccable/design.json` com `web/src/styles.css`, `FormatPicker.tsx`, `FormatPicker.css`, os usos em `Automation.tsx` e `App.tsx`, o catálogo `backend/mycut/short_formats.json` e o renderizador `visuals.py`.

- A interface mantém Manrope, papel quente, navegação escura, campos compactos, divisores finos e ações terracota. As fontes e paletas de Editorial, Radar tech, Passo a passo e Impacto pertencem ao vídeo, em acordo com a regra de cor da produção do sistema existente.
- A galeria usa quatro colunas no computador e duas abaixo de 700px; fonte, fundo, texto e destaque aparecem agrupados. Seleção tem borda e marca, foco tem contorno visível e os controles conservam rótulos. O seletor é compartilhado pela criação e pela pauta do projeto; Cenas oferece imagem, enquadramento e retorno à animação. A prévia é identificada como composição estática.
- As nove capturas abaixo foram abertas individualmente e conferidas contra os arquivos e o contrato. Mostram páginas completas desde o topo, com os conteúdos esperados e sem regiões em carregamento. O vermelho das cenas é uma fixture sintética de upload do teste, não uma imagem editorial de produção.

| Estado conferido | Desktop | Celular | Largura do usuário |
| --- | --- | --- | --- |
| Galeria, Radar tech selecionado | `review/desktop.png` · 1440×2074 | `review/mobile.png` · 390×2691 | `review/user-1640.png` · 1640×2074 |
| Fonte e paleta alteradas, imagens habilitadas | `review/custom-desktop.png` · 1440×2094 | `review/custom-mobile.png` · 390×2800 | `review/custom-user-1640.png` · 1640×2094 |
| Imagem de teste atribuída à cena | `review/image-desktop.png` · 1440×1432 | `review/image-mobile.png` · 390×2357 | `review/image-user-1640.png` · 1640×1456 |

Não foram introduzidos rasters estáticos de interface: miniaturas e prévias são respostas do renderizador. A proveniência `mycut_provenance` foi confirmada em `pipeline.cover_image` e, no delta final, em `visuals.save_png`, chamado por `preview_png` e pela exportação das capas geradas pelo novo renderizador em `production.make_video`. Capas importadas continuam copiadas sem alteração. Essa conferência não atribui o metadado a toda imagem externa ou saída legada. As capturas e o teste `web/tests/visual-formats.spec.ts` usam dados sintéticos e não qualificam a busca real de imagens ou uma produção completa com serviços externos.

**Preservação e drift anterior.** Esta é uma extensão ordinária; `DESIGN.md` e `.impeccable/design.json` foram preservados, sem diff. O documento central ainda registra a disposição `recapture` da rodada sem screenshots e descreve o menu Conexões; as capturas atuais da extensão existem e mostram Configurações. Essas referências históricas não foram reescritas, nem convertidas em aprovação geral do aplicativo.

**Alcance da revisão.** O handoff informa inspeção visual sem achados materiais nas capturas. O reviewer independente classificou o P2 sobre a origem permitida das imagens como **resolvido**, com disposição **ship no escopo desse achado**. O delta conferido usa `scene_images.eligible` tanto para limitar `available_images` enviado ao diretor quanto para validar os IDs retornados em `pipeline.create_direction`; os arquivos armazenados e as escolhas manuais não são apagados. Esse verdict pass não constitui uma nova aprovação geral de toda a superfície.

**Confirmação e runtime.** O usuário confirmou o uso de ambas as origens, representado por `image_source: "both"` e pela opção “Fontes da pauta e minha biblioteca”; o filtro permite ambas nessa seleção. Após o handoff relatar a ausência da fonte condensada no contêiner, foram conferidos `fonts-dejavu-extra` no `Dockerfile` e nas instruções de execução local do `README.md`. O renderizador mantém `DejaVuSansCondensed-Bold.ttf`, a mesma fonte usada nas capturas WSL, sem troca de identidade. A conferência final da raiz confirmou implantação com API/worker saudáveis, quatro prévias de formato e prévia personalizada com cada uma das quatro fontes por HTTP dentro do contêiner. Os 12 testes de formatos também passaram após o ajuste de metadados. Detalhes reproduzíveis em `docs/verificacao-studio.md`.

## Extensão: nome do canal no vídeo — 14/10/2026

Conferido o delta de `channel_name` em `backend/mycut/models.py`, `visuals.py`, `web/src/types.ts` e `FormatPicker.tsx`/`.css`. O campo “Nome do canal no vídeo” fica em Personalizar aparência, tem limite de 40 caracteres e ajuda associada ao controle. O valor pertence ao estilo da produção; vazio oculta o texto e projetos sem o campo mantêm `MYCUT`. Trocar ou restaurar o formato preserva o nome. `Composition` aplica o valor nos quatro formatos e é compartilhada por prévia, capa gerada e vídeo.

O novo campo reutiliza os estilos existentes de input, Manrope e rótulo persistente. Sua ajuda usa `--muted`, 12px e espaçamento de 8px; a largura máxima de 360px permanece contida no formulário móvel. Foram abertas e conferidas `review/channel-desktop.png` (1440×2210), `review/channel-mobile.png` (390×2936) e `review/channel-user-1232.png` (1232×2210), com `@JuniorIA` como exemplo. As três mostram o campo e a prévia selecionada atualizada, preservando a identidade do aplicativo e a separação entre controles e conteúdo do vídeo.

`DESIGN.md` e `.impeccable/design.json` permanecem sem diff e com os mesmos hashes da conferência anterior. O drift histórico já registrado não foi alterado. O handoff da raiz reporta 73 testes Python, três Playwright e build aprovados, além de detector sem achados; foram lidos os testes direcionados de persistência, troca/restauração e ocultação do nome. A revisão independente desta extensão retornou **ship**, sem achados materiais no delta `channel_name`, após conferir código e capturas; não reexecutou os testes nem qualificou uma produção completa por serviços externos.
