# Verificação do MyCut Studio 0.1

Entrega local de 13/10/2026. Interface React/Vite, API FastAPI, fila em SQLite e worker Python. Esta nota separa implementação, testes executados e verificações indisponíveis na sessão.

## Evidência executada

| Camada | Resultado |
| --- | --- |
| TypeScript e Vite | Compilação de produção concluída; JavaScript de 257,58 kB, 80,29 kB com gzip |
| API, armazenamento e worker | 12 testes de integração passaram em 3,485 segundos |
| Render real no teste | Prévia sem voz feita por FFmpeg, download parcial HTTP 206 e pacote ZIP conferidos |
| Render real com voz | Job `21105299fb454338b776f551082e627f`: 1080 × 1920, 30 fps, 45,87 segundos, narração selecionada e legendas alinhadas |
| Arquivos originais | Vídeo, WAV e roteiro do primeiro Short continuam correspondendo aos hashes do manifesto original |
| Configuração operacional | `docker compose config --quiet`, sintaxe dos scripts Bash e compilação Python passaram |
| Playwright | Configuração carregada e dois casos listados: desktop 1440 × 1000 e celular 390 × 844 |

Os testes de integração exercitam a aplicação ASGI real via `httpx.ASGITransport`, sem porta HTTP. O cliente de teste mantém um timer de asyncio porque o sandbox bloqueia o mecanismo de despertar do portal de threads usado pelo TestClient. Endpoints, middleware, SQLite, uploads e FFmpeg não foram substituídos por mocks.

Cobertura: revisões concorrentes; persistência; bloqueio de edição e de fila duplicada; correspondência entre áudio e roteiro; arquivo inválido; conversão de capa; recuperação de fila; origem de mutações; acesso apenas aos arquivos exportáveis; validação de textos; preservação de dois lados da comparação; render, Range, ZIP e histórico.

## Revisão da interface

A revisão independente encontrou quatro problemas: saída do editor sem proteção ao texto não salvo; ambiguidade de quebras de linha na comparação; contraste de textos pequenos; índice de cena inválido após alteração em outra aba. Os quatro foram corrigidos e pontuados como **resolvidos** na revisão do delta. O contraste ajustado foi calculado em 5,23:1 ou mais nos elementos apontados.

O detector mecânico de design apontou a transição de largura da barra de progresso. A revisão considerou aceitável para essa barra pequena e esporádica. A documentação do sistema visual está em `DESIGN.md` e `.impeccable/design.json`.

Foram inspecionados frames das sete cenas do MP4. Essa evidência cobre composição e legibilidade do vídeo; não comprova o layout ou a interação do aplicativo no navegador.

## Limites da sessão

- O sandbox impediu escutar uma porta local, acessar o socket do Docker e iniciar o Chromium. A revisão automática rejeitou a tentativa de liberar a inicialização da API fora do sandbox.
- Por isso, **Docker build/up, teste HTTP por socket e interação visual desktop/mobile não foram validados**. Os testes Playwright foram preparados e listados, mas não executados.
- O acesso ao registro de pacotes estava bloqueado. A compilação utilizou dependências já instaladas no computador, nas versões declaradas. Os links locais usados para essa verificação ficam somente em `node_modules`, ignorado pelo Git. A instalação limpa pela rede e a construção da imagem permanecem sem prova nesta sessão.
- O render narrado reutilizou o alinhamento existente do mesmo WAV, conferido por hash. O download do modelo e a transcrição de um áudio novo no container ainda precisam ser exercitados no ambiente normal.

Para completar essa camada de verificação, siga os comandos de instalação e Playwright no README, com Docker/browser disponíveis e a porta 8321 livre. Os testes usam uma pasta temporária e não alteram os projetos reais.

## Atualização: automação por agentes — 14/10/2026

A interface manual foi uma redução de escopo feita pelo implementador, não uma substituição autorizada do objetivo original. Esta rodada adiciona pauta/link como entrada principal, papéis configuráveis em Codex/Claude/Grok CLI, ponte de execução no WSL, pesquisa, roteiro, direção/capa, conferência, voz ElevenLabs com timestamps e render. O template fixo Claude Code saiu da criação; o projeto histórico permanece.

| Camada desta rodada | Evidência |
| --- | --- |
| Integração Python | **24 testes passaram em 7,272 s** após correções funcionais |
| Pipeline editorial | Quatro respostas estruturadas controladas, estado real de cada etapa, checkpoints reais |
| Voz e vídeo | Resposta ElevenLabs controlada com MP3/tempos; decodificação, normalização, alinhamento e FFmpeg reais, vídeo com áudio de teste |
| Barreiras editoriais | Fonte inacessível interrompe antes do roteiro; duas reprovações interrompem antes da chamada de voz |
| Credenciais | API não retorna chave, erros de validação não ecoam entrada, arquivo 0600, snapshot sem chave |
| Retomada e histórico | Cancelamento impede checkpoint tardio; entrada inicial imutável; plano/voz disponíveis sem exigir vídeo; runner não repete solicitação já iniciada após reinício |
| Executor local | `scripts/agents.sh` inicia e publica heartbeat real; localiza codex, claude e grok; encerra removendo heartbeat. Chamada a subprocesso de fixture validou ida/volta de JSON |
| Frontend | TypeScript/Vite compilados, JS 270,17 kB (83,70 kB gzip) |
| Operação | Compose válido e scripts Bash com sintaxe válida |
| Navegador | **6 casos listados**, cobrindo desktop/mobile, entrada por agentes, conexão, preservação da pauta e editor/export; não executados neste sandbox |

Somente as fronteiras de geração externa foram substituídas nos testes do pipeline: respostas dos agentes e HTTP da ElevenLabs. O áudio usado nesse teste é um sinal sintético, não uma amostra da voz do usuário. Não foi gasto crédito ElevenLabs nem comprovada qualidade/pronúncia da voz. O teste de subprocesso também usa um executável controlado, não inferência real de um provedor.

A revisão independente do código identificou perda da pauta ao navegar para Conexões, erro da geração de voz escondido em outra aba e falta de acesso às versões anteriores de planos/vozes. Foram implementados rascunho de criação no componente raiz, aviso global do job falho, entrada imutável e downloads por tentativa. O revisor conferiu o delta no código e marcou os três achados como resolvidos; isso não substitui interação em navegador. A verificação visual formal permanece com disposition **recapture** porque não há capturas atuais desktop/mobile; não se trata de aprovação visual. Screenshots do usuário mostram a interface anterior e fundamentam a correção do fluxo, sem comprovar o layout novo.

## Atualização: seleção e testes de modelos — 14/10/2026

Conexões ganhou seletores nativos por papel, catálogo do executor e teste assíncrono da seleção ainda não salva. O teste atravessa API, fila de arquivos e subprocesso do CLI, com desafio único e cálculo, cancelamento, limite de três minutos e resultado persistido. Apenas metadados `modelUsage` do envelope Claude/Grok confirmam identidade; texto gerado e catálogo não servem como confirmação. O adaptador Codex informa identidade desconhecida mesmo quando há resposta válida.

| Camada | Resultado desta rodada |
| --- | --- |
| Python | **36 testes passaram em 14,482 s**; ASGI real, fila e subprocessos reais com executáveis de teste |
| Diagnósticos | Seleção ainda não salva, IDs inválidos/cruzados, desafio errado, identidade divergente/ausente, padrão resolvido, duplicação, expiração, cancelamento e interrupção real do subprocesso |
| Privacidade | Exportação permitida de ID/nome do catálogo; campos de credenciais excluídos; erros classificados sem repassar saída privada |
| Descoberta real | Codex: seis IDs visíveis no cache; Grok: quatro; Claude: quatro IDs resolvidos via inicialização de controle sem prompt de inferência |
| Inferência real | Tentativas curtas falharam: Codex/Grok por permissão local; Claude por OAuth expirado sem renovação. Nenhuma resposta real qualificada |
| Frontend | TypeScript/Vite passaram; configuração Compose validada |
| Navegador | Oito casos desktop/mobile listados. Novo contrato de seleção/teste usa fixtures explícitas da API; não foi executado neste sandbox |

A revisão independente encontrou um erro de atualização que continuava visível após a conexão se recuperar. O estado de polling agora é separado do erro de ação e foi confirmado como corrigido no código. A disposição visual permanece **recapture**: faltam capturas atuais desktop/mobile, bloqueadas neste ambiente. O detector encontrou apenas a transição de largura preexistente da barra de progresso, fora deste delta.

Para atualizar: `docker compose up --build -d`, encerre o executor anterior com Ctrl+C e rode novamente `bash scripts/agents.sh`. Abra Conexões, selecione os modelos novamente se os nomes antigos estiverem inválidos, teste cada papel e salve. O catálogo comprova descoberta, não habilitação da conta nem sucesso de inferência.

## Atualização: navegação persistente — 14/10/2026

O App inicializava sempre em Produções; Conexões e Fila existiam apenas no estado React e as transições apagavam o endereço. O teste de montagem nova do componente real reproduziu duas falhas: endereços de Conexões e Fila selecionavam Produções. Após a correção, **oito testes de navegação passaram** com `npm --prefix web run test:navigation`, usando a renderização React no servidor e um adaptador controlado de histórico. Não foi acrescentada dependência de testes.

Rotas no fragmento da URL restauram tela, produção e aba do editor, preservam links antigos e conectam Voltar/Avançar. Trocar abas mantém o mesmo rascunho; recusar a saída pelo histórico restaura a entrada anterior sem desmontar o editor. Testes cobrem também edição manual do fragmento, endereços desconhecidos e remoção dos listeners.

TypeScript/Vite passaram. A suíte Playwright agora lista dez casos desktop/mobile, incluindo refresh real e proteção de rascunho via histórico, mas não foi executada: a tentativa de iniciar Chromium permaneceu bloqueada pelo ambiente. Testes React e do adaptador não equivalem a validação visual ou interação no navegador.

Nesta atualização foi possível executar `docker compose up --build -d`: instalação com lockfile, compilação, recriação de API/worker e healthcheck concluídos. A verificação HTTP dentro do container confirmou que `/` aponta para `/assets/index-DCOa4h7g.js`, contendo o controlador de navegação e os seletores/testes de agentes. A imagem produzida foi `sha256:3229e27210911d32e46ca318860649b92a9a1485fe95d9a1ade2b382e53b4c0d`. Isso atualiza o limite anterior de Docker; a indisponibilidade do navegador permanece.

## Atualização: amostras e testes de voz — 14/10/2026

Conexões carrega o catálogo de vozes automaticamente e oferece reprodução do `preview_url` HTTPS sem síntese. Quando falta amostra ou sua reprodução falha, a interface informa isso e não chama a geração paga. O teste de texto aceita até 300 caracteres, usa a seleção ainda não salva e envia uma única solicitação à ElevenLabs. Texto, voz, modelo e ajustes iguais reutilizam o MP3 local. O histórico mostra os últimos cinco testes e permanece após refresh; o cache é separado pela chave conectada e não contém a chave nos registros.

| Camada | Evidência desta rodada |
| --- | --- |
| Backend | **45 testes passaram em 16,128 s**, incluindo sete novos casos da integração de voz |
| Fronteira ElevenLabs | HTTP simulado; validação real de parâmetros, ASGI, arquivos MP3, ffprobe, histórico e Range |
| Cobrança | Catálogo/histórico sem POST de síntese; pedido repetido reutiliza cache; pedidos concorrentes não duplicam geração; timeout não provoca repetição automática |
| Seleção e privacidade | Teste usa ajustes não salvos, não altera voz padrão nem cria produção; troca de chave isola arquivos; respostas não incluem segredos |
| Navegação | **Oito testes passaram** com React e histórico controlado |
| Frontend | TypeScript e build Vite passaram |
| Navegador | **Seis casos passaram em 13,4 s**, Chromium, 1440×1000 e 390×844: reprodução grátis, ausência/falha de amostra, teste com seleção atual, cache após refresh e falha de geração sem repetição |

O servidor de teste e o Chromium do comando padrão encontraram restrições do ambiente. A verificação de navegador foi executada pelo runner Node disponível, com o bundle real servido por interceptação local e APIs explicitamente simuladas em `web/tests/voice-samples.spec.ts`. Não houve acesso à conta ou geração real ElevenLabs. A reprodução usou áudio sintético, sem avaliar naturalidade ou pronúncia.

Capturas desktop/mobile em `web/test-results/voice-samples/` foram inspecionadas: controles legíveis, ações separadas, disposição em coluna no celular e ausência de overflow horizontal, também verificada por teste. Essa verificação cobre a seção de voz desta rodada; não altera retroativamente o estado das revisões visuais anteriores. O comando usado, com configuração temporária sem servidor e filtrada para `voice-samples.spec.ts`, foi:

```bash
node --input-type=module -e 'process.argv = ["node", "playwright", "test", "--config", "/tmp/mycut-voice-e2e.config.mjs"]; await import("./web/node_modules/@playwright/test/cli.js");'
```

Em ambiente sem essas restrições, os mesmos casos fazem parte de `npm --prefix web run test:e2e`.

Docker foi reconstruído e API/worker ficaram saudáveis, com a imagem `sha256:f5507be0d2b9888048cab084897543f04eeb9d9161d639b04eb5fcc15f426493`. Antes da atualização, a fila não tinha produções ativas. A leitura HTTP no container confirmou `/assets/index-DipJq2Sq.js`, os dois novos botões e o histórico vazio. A consulta real, somente de leitura, à conta ElevenLabs retornou 23 vozes com amostra, incluindo a voz selecionada. Nenhuma síntese foi solicitada na conta.

## Atualização: filtro de idioma das vozes — 14/10/2026

O seletor **Idioma da voz** aparece antes da voz, inicia em Português e conserva a preferência no navegador. O catálogo agora expõe somente o idioma cadastrado e o sotaque, além dos campos anteriores. O filtro não transforma suporte multilíngue em idioma de origem: uma voz cadastrada em inglês continua em Inglês mesmo se o provedor verificar sua capacidade de falar português. Idioma ausente ou inválido fica em **Idioma não informado**, sem inferência pelo nome ou descrição. Os idiomas presentes no catálogo e **Todos os idiomas** apresentam contagens.

Alterar o filtro limpa apenas a seleção em edição que deixa de corresponder, sem modificar a voz padrão no servidor. Se um refresh restaura uma voz salva fora do filtro, ela aparece identificada como tal; salvar/testar ficam indisponíveis até uma escolha compatível. A ausência de resultados tem orientação explícita.

Passaram **oito testes da integração de voz** (`test_voice_samples`, 1,012 s), **oito casos Playwright desktop/mobile** (7,4 s) e o build TypeScript/Vite. A cobertura inclui preservação da preferência após refresh, contagens, português/inglês/idioma desconhecido, lista vazia, bloqueio de seleção oculta e a reprodução gratuita já existente. As capturas `voice-language.png` foram inspecionadas em 1440×1000 e 390×844; o teste também verificou ausência de overflow horizontal. Os testes de síntese continuam com respostas simuladas, sem consumo de créditos.

A leitura real dos metadados, sem gerar fala, identificou duas vozes cadastradas em português e 21 em inglês. A voz selecionada veio com `language=pt` e `accent=pt-brazilian`. A fila estava sem produções ativas antes de reconstruir o Docker.

## Atualização: Configurações por área — 14/10/2026

O menu **Configurações** contém **Agentes**, **Vozes** e **Ambiente**, cada um com conteúdo e URL próprios. Agentes mantém seleção e testes; Vozes reúne ElevenLabs, filtro, amostras e ajustes; Ambiente reúne comandos dos CLIs, navegador e estado dos serviços. No desktop, o submenu fica na lateral; nas telas menores, acima do conteúdo. `#/conexoes` redireciona para `#/configuracoes/agentes`. Refresh e histórico mantêm a seção; trocar de seção preserva os campos de configuração em edição.

Idioma, voz e modelo compartilham a mesma linha e altura no desktop; idioma ocupa 180 px. No celular, os campos ficam empilhados. A conexão ElevenLabs já configurada fica recolhida em **Gerenciar conexão**, com acesso à troca de chave e à desconexão.

Validação: nove testes de navegação, build TypeScript/Vite e 50 testes Python passaram. Onze casos de navegador passaram com o bundle real e APIs simuladas: cinco em desktop, cinco em celular e um de navegação/layout em tablet (1440×1000, 390×844 e 900×1000). Foram conferidos separação de conteúdo, rascunho de voz entre seções, Voltar/Avançar, refresh, link antigo, controles de conexão, altura dos seletores e ausência de overflow, além das amostras e filtro existentes. As capturas `settings-voices.png` e `settings-environment.png` estão em `web/test-results/settings/`. Nenhuma síntese real ou consumo de créditos foi usado.

## Atualização: cenas completas e cor antes da geração — 14/10/2026

O diagnóstico do projeto mostrado na interface encontrou seis cenas com `items: []`. Os artefatos da execução confirmaram que a segunda resposta de Direção visual já veio vazia e foi aprovada pela Conferência; não houve perda de campos na interface. A validação aceitava listas vazias e não exigia a quantidade de textos correspondente ao formato visual.

A saída da direção agora exige textos não vazios: fluxo com dois a quatro itens, comparação com exatamente dois e destaque com ao menos um. Uma resposta inválida recebe uma única tentativa adicional com os erros concretos; erro de conexão/provedor não é repetido por essa correção. Se a saída continuar inválida, o fluxo falha antes de publicar as cenas ou gerar voz. A operação **Criar/Refazer cenas com agentes** usa somente Direção visual e Conferência, mantém a narração e o áudio e salva os ajustes abertos antes de enfileirar.

**Cor do vídeo** aparece em Novo Short e Pauta e agentes. A opção automática permite a escolha pela direção; a opção manual envia a preferência e a aplica também ao resultado validado e à capa. Projetos antigos preservam a cor existente. O projeto observado não foi regravado por fora da interface: a captura mostrava uma cor em edição diferente da salva, e a recuperação deve usar o novo botão após salvar esses ajustes.

Validação: **60 testes Python**, **nove testes de navegação** e build TypeScript/Vite passaram. Os oito testes novos do backend cobrem a reprodução da saída vazia, correção automática, falha persistente sem checkpoint, cor manual/automática, preservação de roteiro/áudio e requisitos específicos da operação de cenas. Os testes de regressão foram executados antes da correção e falharam nas condições reproduzidas.

**Quatro casos Playwright** passaram com o bundle real e APIs simuladas, em 1440×1000 e 390×844. Verificam a seleção de cor antes de criar, preservação ao navegar, salvamento antes de gerar cenas, atualização do formulário/prévia e ausência de overflow horizontal. Capturas `theme-before-generation.png` e `scenes-from-agents.png` em `web/test-results/scene-agents/` foram inspecionadas. Não houve nova inferência real dos CLIs nem síntese ElevenLabs; os testes não qualificam a qualidade do conteúdo de uma nova geração real.

A leitura do Docker após a atualização confirmou API saudável, worker online e o bundle `/assets/index-DDVzKPiP.js` contendo os novos controles. O OpenAPI servido inclui a operação `scenes` e a cor na criação, e o modelo Python dentro do container rejeita `items: []`. O comando de atualização desta rodada encontrou uma troca concorrente do container durante a espera pelo healthcheck; a verificação posterior confirmou os dois serviços ativos e a versão esperada. O projeto original permaneceu na revisão 4, sem regeneração externa.

## Atualização: formatos, personalização e imagens por cena — 14/10/2026

**Novo Short** e **Pauta e agentes** oferecem Editorial, Radar tech, Passo a passo e Impacto. Cada formato tem composição e movimento próprios, com fonte, fundo, texto e destaque editáveis. O modo visual permite somente animações ou animações com imagens; a origem pode ser a biblioteca da produção, fontes verificadas da pauta ou ambas. O editor permite importar, selecionar e enquadrar a imagem por cena. As escolhas seguem para os agentes e ficam no projeto, no snapshot e no manifesto da versão.

Galeria, prévia, capa gerada e vídeo compartilham o renderizador Pillow. Novos temas respeitam as preferências mesmo após a direção visual. Renderizar novamente reaproveita a narração e redesenha uma capa gerada pelo MyCut no novo tema; uma capa importada é preservada. Produções antigas sem `visual_style` mantêm o renderizador anterior até a escolha de um formato.

Validação final: **72 testes Python** passaram em 27,341 s; **nove testes de navegação** e build TypeScript/Vite passaram. **15 casos Playwright** passaram em 21,7 s, cobrindo desktop 1440×1000, celular 390×844 e a largura da captura do usuário, 1640×1000. Incluem personalização, troca de formato, recuperação do catálogo, seleção por teclado, preservação após navegação/refresh, upload e enquadramento de imagem, retorno à animação e ausência de overflow. O cabeçalho do editor foi corrigido para acomodar o botão de salvar também no celular.

Os testes Python exportaram MP4s reais dos quatro formatos, verificaram mudanças entre frames de animação e confirmaram, por leitura de pixels de um frame extraído pelo FFmpeg, a presença da imagem selecionada. Também conferiram a atualização da capa gerada sem alterar o arquivo original, fonte/cores na prévia, propriedade das imagens, persistência e validação dos IDs. Downloads externos foram simulados: há testes de HTTPS, bloqueio de rede privada, redirecionamento validado e conexão fixada no IP verificado com TLS para o hostname original.

As nove capturas de galeria, personalização e cena com imagem em `.impeccable/review/` foram abertas e inspecionadas. O bundle e o renderizador das prévias são reais; APIs de projetos, agentes e imagens externas foram simuladas. A área vermelha nas capturas de cena é uma imagem sintética usada para comprovar enquadramento. Não houve inferência real, busca pública de imagem ou geração ElevenLabs nesta rodada; a pertinência das imagens escolhidas por agentes reais ainda precisa de qualificação. O detector Impeccable não reportou achados nos novos componentes.

A revisão independente identificou um P2 funcional: a origem escolhida não filtrava as imagens previamente armazenadas oferecidas ao diretor. A correção limita o prompt e a validação dos IDs ao conjunto elegível, preservando a biblioteca e seleções manuais. Dois testes adicionais cobrem a troca entre fontes/biblioteca/ambas com imagens de ambas as origens já salvas e a rejeição de uma imagem excluída pela preferência. Não houve achado visual material nas capturas fornecidas.

No verdict pass, o revisor classificou o P2 como **resolvido**, disposição **ship no escopo desse achado**. A conferência documental preservou `DESIGN.md` e `.impeccable/design.json` e registrou esta extensão em `.impeccable/short-formats.md`. Depois da inclusão de proveniência nas prévias e capas exportadas pelo novo renderizador, os **12 testes de formatos** passaram novamente em 7,329 s.

A conferência inicial no Docker identificou a ausência de `DejaVuSansCondensed-Bold.ttf`: essa fonte requer `fonts-dejavu-extra`, que foi acrescentado à imagem e às instruções locais. Após reconstruir, API e worker ficaram saudáveis. A imagem final é `sha256:34c03e689b192728315d6e3db0db4eaaba54f54717173f3329116974d28a76ef`; `/` serve `/assets/index-CUaGL1zP.js`. As chamadas HTTP dentro do container carregaram os quatro PNGs de formato (270×480) e a prévia personalizada (360×640) com cada uma das quatro fontes, verificando cor de fundo e metadados. O projeto original continuou na revisão 4; a fila estava vazia antes da atualização e após a conferência. Nenhuma produção real foi iniciada.

## Atualização: nome do canal no vídeo — 14/10/2026

O texto “MYCUT” dos formatos pode ser substituído em **Personalizar aparência › Nome do canal no vídeo**, na criação ou em Pauta e agentes. Aceita até 40 caracteres, respeita a escrita informada e pode ficar vazio para ocultar. A preferência é salva em `visual_style.channel_name`, acompanha as versões e permanece ao trocar ou restaurar um formato. O renderizador compartilhado usa o nome nas prévias, cenas e capas geradas; capas importadas e arquivos de versões anteriores são preservados. Produções antigas continuam mostrando MYCUT até personalizar.

Passaram **73 testes Python** (38,388 s), build TypeScript/Vite e **três casos Playwright** (23,9 s), em 1440×1000, 390×844 e 1232×900. O teste de renderização compara a região do cabeçalho entre nome padrão, nome personalizado e ausência nos quatro formatos, e confirma que o conteúdo abaixo não muda. Persistência, limite, normalização de espaços, troca de tema, restauração, navegação e refresh também foram conferidos. As prévias usam o renderizador real; APIs de projetos no navegador são simuladas. Nenhuma inferência nem síntese paga foi solicitada.

As capturas `.impeccable/review/channel-desktop.png`, `channel-mobile.png` e `channel-user-1232.png` foram abertas e conferidas. O detector não reportou achados nos componentes alterados.

A revisão independente retornou **ship** no escopo de `channel_name`, sem achados materiais. A conferência documental preservou os documentos centrais de design e registrou a extensão em `.impeccable/short-formats.md`.

A imagem Docker foi preparada enquanto uma produção estava ativa, e os serviços só foram reiniciados depois de a fila ficar livre. A imagem `sha256:5cbd481b25d0537db171db9d4556c26f02c712c59881ca0d1409a32782094bd2` serve `/assets/index-Bo_Q84gu.js`; API e worker estão saudáveis. A verificação HTTP no container confirmou nome personalizado e cabeçalho vazio nos quatro formatos, incluindo diferenças nos pixels e o valor nos metadados da prévia.

## Escopo ainda pendente

A qualificação real dos três CLIs exige login e acesso aos modelos no host; disponibilidade do executável não garante autenticação. A geração real ElevenLabs exige chave/voz configuradas no app e não foi executada nesta verificação. A seção de testes de voz teve interação validada no navegador com APIs simuladas; os demais fluxos de navegador mantêm os limites das rodadas anteriores. Coleta recorrente de tendências, duas execuções diárias e envio/agendamento no YouTube continuam requisitos ainda não implementados. O resultado atual vai até vídeo disponível para revisão e download.
