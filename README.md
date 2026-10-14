# MyCut

Produção de Shorts sobre inteligência artificial em português brasileiro, com animações, fluxos, diagramas e narração.

O objetivo é automatizar a descoberta de pautas, a pesquisa, o roteiro, a voz, as imagens, a montagem e a publicação de **dois Shorts por dia** usando agentes de IA. O estúdio web local agora conecta Codex CLI, Claude Code CLI e Grok CLI para transformar uma pauta em roteiro, cenas, capa, narração ElevenLabs e vídeo. A coleta recorrente de tendências, o calendário de duas produções diárias e a publicação automática no YouTube ainda precisam ser implementados; continuam sendo parte do objetivo do produto.

## Abrir o aplicativo

No Linux ou WSL, a partir da raiz do repositório, com Docker e Docker Compose disponíveis:

```bash
mkdir -p .data
docker compose up --build -d
```

Abra **http://localhost:8321**. A primeira construção baixa as dependências. A API serve a interface compilada e o worker processa a fila em outro container. Fechar a aba não interrompe uma produção; os serviços e o computador precisam continuar ligados.

A navegação fica no endereço: `#/configuracoes/agentes`, `#/configuracoes/vozes`, `#/configuracoes/ambiente`, `#/fila`, `#/novo` e `#/producoes`. No editor, a URL também identifica a produção e a aba. Atualizar a página preserva essa localização; Voltar e Avançar acompanham a navegação. Links antigos `#/conexoes` e `#<id-da-produção>` continuam funcionando. Alterações não salvas no editor mantêm o aviso de descarte ao sair.

O arquivo `web/pnpm-workspace.yaml` autoriza o script de instalação do `esbuild` e é copiado antes de instalar as dependências na imagem. Essa configuração também vale para a instalação local; não é necessário executar `pnpm approve-builds` interativamente no container.

Para alinhar **áudios importados sem tempos de fala**, prepare o modelo local uma vez:

```bash
docker compose exec worker python -m mycut.download_model
```

Isso baixa o Whisper `large-v3` para o volume persistente `models`. Não há cobrança por chamada nem envio do áudio para uma API; o alinhamento roda na CPU. O primeiro Short pode reutilizar seu alinhamento já salvo quando o áudio é exatamente o mesmo. Prévias sem narração e vozes geradas pela integração ElevenLabs não precisam desse modelo: a integração recebe os tempos de fala do provedor.

```bash
docker compose logs -f api worker  # acompanhar serviços
docker compose stop                # parar sem apagar projetos
```

A configuração atende somente o computador local, sem login. Não foi preparada para exposição pública. O bind de `.data` usa o usuário de ID 1000, padrão deste WSL; em outro sistema, o diretório precisa permitir escrita a esse usuário.

## Conectar os agentes e a ElevenLabs

Com os três CLIs instalados e autenticados no WSL, abra outro terminal na raiz do MyCut:

```bash
bash scripts/agents.sh
```

Mantenha esse executor aberto junto com os containers. Ele usa o login local de cada CLI, sem copiar credenciais para o Docker. API, worker e executor compartilham a pasta `.data`. Se você usar `MYCUT_DATA_DIR` fora do Docker, todos precisam apontar para os mesmos dados.

Por padrão, o executor chama `codex`, `claude` e `grok`. Em **Configurações › Ambiente › Comandos dos CLIs**, você pode trocar o comando de cada um para usar outro perfil ou login. Por exemplo, `CLAUDE_CONFIG_DIR=~/.config/cloak/profiles/amjr/claude claude` ou `cloak exec --profile amjr claude`. Variáveis `NOME=valor` antes do executável, `~` e `$VAR` são expandidas no WSL. O comando roda sem shell, então aliases, funções e pipes não funcionam. O executor relê os comandos a cada chamada, sem reiniciar, e atualiza a lista de modelos depois de salvar. Esses comandos são executados no seu computador; a API aceita a alteração apenas da própria interface local.

### Navegador para a pesquisa

Alguns sites, como o `openai.com`, respondem 403 à leitura automática dos CLIs. Nesse caso, a etapa de Pesquisa pode abrir a página no Chrome do Windows, como uma pessoa faria. Isso vale para Claude Code, Codex e Grok. O executor abre o Chrome Canary (ou o Chrome) com a porta de depuração `9222` e um perfil próprio em `%LOCALAPPDATA%\MyCut\ChromeProfile`, sem os seus logins. Cada CLI recebe o [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) com uma versão fixa e apenas as ferramentas de navegar, ler (snapshot), clicar, rolar e fechar abas. Formulários, digitação, uploads e execução de JavaScript ficam fora. O texto das páginas é tratado como dado, não como instrução.

Configure em **Configurações › Ambiente › Navegador para pesquisa**: ative ou desative, informe o caminho do `chrome.exe` se a detecção automática não achar, escolha a porta e use **Abrir e testar**. Requisitos: Node.js com `npx` no WSL e rede espelhada (`networkingMode=mirrored` no `.wslconfig`), para o WSL alcançar a porta do Chrome no Windows. Desde o Chrome 136, a depuração remota [não funciona no perfil padrão](https://developer.chrome.com/blog/remote-debugging-port), por isso o perfil é separado. Se um site exigir login, entre nele só nessa janela do MyCut.

Se o Chrome ou o MCP falharem, a pesquisa continua com a busca e a leitura dos próprios CLIs e registra a falta do navegador nas limitações. Sem fonte verificada, o fluxo continua parando antes do roteiro. No Grok, as execuções com navegador usam `--trust` na pasta temporária e desligam os MCPs importados do Claude e do Cursor. Nesse modo, chamar outro servidor MCP encerra a execução.

1. No aplicativo, abra **Configurações › Agentes**. Distribua os CLIs entre Pesquisa, Roteiro, Direção visual e Conferência. Escolha o modelo na lista e clique **Testar agente** em cada papel. O teste usa a seleção atual sem salvá-la; clique **Salvar agentes** quando terminar. **Padrão do CLI** deixa a escolha a cargo do CLI.
2. Abra **Configurações › Vozes**. Na seção **ElevenLabs**, cole uma chave de API da sua conta e clique **Conectar ElevenLabs**. A chave precisa permitir listar vozes/modelos e gerar fala. Não coloque a chave no roteiro, Git ou chat. [Documentação de autenticação](https://elevenlabs.io/docs/api-reference/authentication).
3. Selecione a voz **Junior**, ou outra da sua conta, o modelo e os ajustes. Clique **Salvar voz**. A lista vem da conta conectada.
4. Em **Novo Short**, informe a **Pauta ou link**, escolha um formato e personalize fonte, fundo, texto e destaque. Defina se quer somente animações ou também imagens. Os agentes recebem essas escolhas antes de criar o roteiro e as cenas. Escolha **Produzir com agentes** ou, para conferir o roteiro antes de gastar voz, **Roteiro e cenas primeiro**.

Conectar/listar vozes não sintetiza áudio. Produzir a voz usa créditos da conta ElevenLabs. Não há repetição automática da requisição paga após erro. O texto completo vai em uma única requisição para preservar a continuidade da narração. Os [tempos de fala retornados pelo provedor](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps) alimentam a sincronização de cenas e legendas. O MP3 de transporte fica como intermediário; a trilha usada no render é WAV normalizado.

Em **Configurações › Vozes**, o catálogo carrega automaticamente. Depois de conectar, a chave e a ação de desconectar ficam em **Gerenciar conexão**. **Ouvir amostra · grátis** reproduz o áudio pronto fornecido pela voz, quando disponível, sem gerar fala. Essa amostra não reflete o modelo ou os ajustes do formulário; uma voz sem amostra mostra a indisponibilidade, sem gerar áudio como alternativa. O campo [`preview_url`](https://elevenlabs.io/docs/api-reference/voices/search) vem do catálogo do provedor.

Antes de escolher a voz, use **Idioma da voz**. O filtro inicia em **Português**, mostra a quantidade de vozes por idioma e mantém sua preferência neste navegador após refresh. Há opções **Todos os idiomas** e **Idioma não informado**. A seleção usa o idioma cadastrado em `labels.language`, não a capacidade multilíngue do modelo; o nome da voz também mostra idioma e sotaque quando informados. Trocar o filtro não altera a voz padrão salva: uma seleção que fica fora dele precisa ser escolhida novamente para salvar ou gerar um teste. Filtrar não gera fala nem consome créditos.

**Testar com meu texto** aceita até 300 caracteres e usa a seleção atual, sem alterar a voz padrão salva nem criar uma produção. O botão **Gerar teste (usa créditos)** informa a cobrança antes do clique; não é uma prévia gratuita de texto personalizado. Os últimos cinco testes aparecem com texto, voz, modelo e ajustes e podem ser reouvidos após recarregar a página. Repetir texto, voz, modelo e ajustes reutiliza o MP3 local, sem nova geração. O cache fica em `.data/voice-tests/`, separado por chave conectada, e não é versionado. [Regras de consumo e limites das regenerações gratuitas no site](https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/is-there-a-way-to-preview-audio-without-losing-quota-before-downloading).

A indicação “executor conectado” comprova o processo ativo e os executáveis disponíveis no PATH; não comprova login, saldo ou acesso a cada modelo. **Testar agente** executa uma solicitação curta pelo mesmo adaptador usado na produção, valida um desafio e mostra resposta, duração, ID solicitado e modelo informado nos metadados do CLI. O teste usa a cota do CLI; não gera voz ou vídeo. Há um teste por vez, cancelamento e limite de três minutos, incluindo espera na fila. O último resultado de cada papel permanece disponível após recarregar a página.

Claude e Grok podem informar `modelUsage`: o app distingue confirmação, modelo diferente e resolução do padrão. No adaptador Codex atual, a resposta pode ser validada, mas o modelo efetivamente usado **não é confirmado**. Uma declaração do próprio modelo nunca serve como confirmação de identidade.

Os seletores recebem IDs do cache local de modelos do Codex/Grok e da inicialização do Claude Code, sem copiar credenciais. O catálogo não comprova acesso nem login. **Atualizar modelos** relê essas fontes quando o executor está livre; se a lista faltar ou estiver antiga, abra o CLI no WSL antes de atualizar. Trocar de CLI limpa o modelo selecionado. Nomes antigos digitados à mão precisam ser selecionados novamente. Após atualizar o MyCut, reconstrua os containers e reinicie também `bash scripts/agents.sh` para carregar o novo executor.

## Fluxo de produção

1. Pesquisa abre fontes e reúne fatos com referências. Se não conseguir verificar a pauta, o fluxo para.
2. Roteiro cria narração, título, descrição e tags. Direção visual cria cenas de animação/fluxo. A capa não faz parte deste fluxo: ela é criada à parte, na aba **Capa**.
3. Conferência compara as afirmações com a pesquisa. Pode pedir uma correção; se reprovar novamente, o fluxo para antes da voz.
4. ElevenLabs gera a narração usando a voz salva. Pillow/FFmpeg renderizam o Short em 1080 × 1920, com cenas animadas e legendas.
5. Você acompanha as etapas, assiste ao resultado e baixa vídeo, capa, legendas, roteiro, publicação e manifesto.

A conferência automática é uma etapa editorial, não uma garantia de verdade. A revisão final continua disponível antes de publicar. O agente de direção usa cenas de fluxo, comparação e destaque; no modo com imagens, pode selecionar uma imagem pertinente da biblioteca ou das fontes verificadas. As cenas não usam ilustrações geradas por modelo de imagem; isso acontece somente no chat da capa.

O editor permanece para ajustar o material, importar voz (aba **Áudio**) ou capa (aba **Capa**), gerar apenas a narração ou renderizar novamente sem pagar por outra voz. Comparações têm dois lados. Limites de edição: 12 cenas, 500 palavras, áudio até 3 minutos e 100 MB; capa até 15 MB. A geração ElevenLabs aceita até 4.000 caracteres. O agente de roteiro trabalha com até 180 palavras e 3 a 8 cenas.

Na aba **Cenas**, **Criar cenas com agentes** recupera cenas incompletas; quando preenchidas, a ação aparece como **Refazer cenas com agentes**. Ela salva os ajustes abertos, chama apenas Direção visual e Conferência e recria os diagramas, preservando o roteiro, o áudio e a capa. Usa a cota dos CLIs, sem gerar outra voz. Fluxos exigem de dois a quatro textos, comparações exatamente dois e destaques ao menos um; respostas vazias recebem uma tentativa automática de correção e não são publicadas se continuarem inválidas.

Projetos e fila persistem em SQLite. Cada tentativa tem diretório próprio; etapas concluídas salvam checkpoints no projeto, e o job atualiza sua revisão. Edições concorrentes ficam bloqueadas durante a produção. Após cancelamento, resultados atrasados não podem substituir novas alterações. Ao reiniciar o worker, jobs em execução ficam marcados como interrompidos e não são repetidos automaticamente.

“Roteiro do Claude Code” era uma cópia fixa das sete cenas do primeiro Short, não um agente. Essa opção saiu da criação. O primeiro Short continua disponível como produção existente, e os arquivos originais em `shorts/claude-cloud/` permanecem intactos.

### Formatos, cores e imagens

Escolha o visual em **Novo Short** ou **Pauta e agentes**. Os formatos alteram a composição e a animação, além da paleta:

| Formato | Composição |
| --- | --- |
| Editorial | Fundo claro, fonte serifada e blocos com entrada suave. |
| Radar tech | Fundo escuro, etapas alternadas e entradas laterais. |
| Passo a passo | Guia lateral e etapas reveladas em sequência. |
| Impacto | Tipografia maior, blocos contrastantes e entrada com escala. |

Você pode trocar a fonte entre sem serifa, serifada, monoespaçada e condensada; ajustar cores de fundo, texto e destaque; e restaurar os valores do formato. As miniaturas e a prévia da cena usam o mesmo renderizador do vídeo. Essas escolhas pertencem à produção e ficam registradas em cada versão. Projetos antigos mantêm o visual anterior até você escolher um formato.

Em **Personalizar aparência › Nome do canal no vídeo**, substitua “MYCUT” pelo nome ou @ do seu canal (até 40 caracteres). Deixe vazio para ocultar o texto. A escolha permanece ao trocar ou restaurar um formato e aparece nas cenas e nas capas geradas ao renderizar novamente; capas importadas não são alteradas.

**Somente animações** impede o uso automático de imagens. Em **Animações e imagens**, escolha a origem: fontes da pauta, imagens importadas na biblioteca da produção ou ambas. O agente de pesquisa pode sugerir até três imagens de páginas verificadas. O MyCut baixa imagens HTTPS públicas e registra sua origem. Se nenhuma imagem elegível estiver disponível, as cenas usam animações; os avisos aparecem no editor. A origem limita a seleção automática, sem apagar imagens já armazenadas nem substituir suas escolhas manuais.

Em **Cenas**, selecione uma imagem por cena ou mantenha a animação. Você também pode importar PNG, JPG ou WebP de até 15 MB, com limite de 24 imagens por produção, e escolher entre mostrar a imagem inteira ou preencher a área com corte. Para usar sua biblioteca antes dos agentes, crie a produção sem iniciar a geração, importe as imagens em Cenas e execute os agentes em Pauta e agentes. Refazer apenas as cenas reutiliza a pesquisa existente; uma nova busca de imagens acontece na produção completa.

Após mudar o visual, **Renderizar cenas atuais** aplica as alterações reutilizando a narração existente. Capas importadas ou criadas no chat permanecem como estão; capas compostas pelo antigo agente de direção seguem o visual atual.

### Encerramento

Na aba **Encerramento**, importe um MP4, MOV ou WebM de até 100 MB e 60 segundos, ou escolha um vídeo da biblioteca compartilhada entre as produções. A prévia da aba reproduz somente o encerramento. O vídeo preserva a imagem inteira no formato vertical e usa seu próprio áudio, quando houver.

Marque **Incluir no final deste Short** para acrescentá-lo após a última cena. A inclusão começa desativada, para que cada produção receba o clipe somente após sua escolha; importar um vídeo o disponibiliza na biblioteca. Desmarcar mantém o arquivo para uso posterior. Clique em **Salvar alterações** para guardar a escolha ou em **Renderizar cenas atuais** para salvar e gerar o Short com ela, reutilizando a narração existente. O vídeo já renderizado permanece como estava até a nova renderização. Cenas e encerramento juntos devem ter no máximo 180 segundos; se ultrapassarem, encurte as cenas ou desative a inclusão.

### Capa

A aba **Capa** é um chat: descreva a capa, anexe até 4 imagens de referência (PNG, JPG ou WebP, até 15 MB cada) e escolha o agente e o modelo no topo do chat. Cada mensagem gera uma imagem 9:16, e o pedido seguinte recebe a conversa e a última imagem, para ajustes como “deixe o fundo mais escuro”. A imagem só vira capa quando você clica em **Usar como capa**. Também é possível importar uma capa pronta.

- **Grok** usa `image_gen`/`image_edit` e **Codex** usa a geração de imagens do próprio CLI; os CLIs recebem somente essas ferramentas.
- **Claude Code** não tem gerador de imagens: desenha a capa em SVG (formas, gradientes, texto e os anexos), que o MyCut converte em PNG com `resvg`. O SVG não pode usar scripts nem referenciar arquivos além dos anexos.

O chat roda numa fila própria do worker: gerar uma imagem não bloqueia a edição nem uma produção em andamento, e há uma geração por vez por produção. O custo aparece em **Custos** como versão “Capa”. É preciso reiniciar `bash scripts/agents.sh` depois de atualizar o MyCut, porque o executor passou a trocar anexos e imagens com os CLIs. Alterar formato ou cores não solicita uma nova voz nem consome créditos ElevenLabs.

## Executar sem Docker

Requisitos: Node.js 24+, pnpm 12.8.1, Python 3.12, `uv`, FFmpeg/ffprobe e fontes DejaVu. No Ubuntu:

```bash
sudo apt-get update
sudo apt-get install ffmpeg fonts-dejavu-core fonts-dejavu-extra
uv venv --python 3.12 .venv-app
uv pip install --python .venv-app/bin/python -r backend/requirements.txt
pnpm --dir web install --frozen-lockfile
npm --prefix web run build
bash scripts/start.sh
```

O modelo Whisper só é necessário para alinhar áudio importado sem tempos de fala. Para baixá-lo: `PYTHONPATH=backend .venv-app/bin/python -m mycut.download_model`. Em outro terminal, rode `bash scripts/agents.sh` para conectar os CLIs. `scripts/start.sh` inicia API e worker e encerra ambos com Ctrl+C. Para reutilizar outro ambiente Python compatível, informe `MYCUT_PYTHON=/caminho/absoluto/bin/python`.

Durante o desenvolvimento, mantenha os serviços acima ativos e rode `pnpm --dir web dev` em outro terminal. Abra http://localhost:5173; o Vite encaminha `/api` para a porta 8321.

| Variável | Padrão | Uso |
| --- | --- | --- |
| `MYCUT_DATA_DIR` | `.data` na raiz | Banco, uploads e versões |
| `MYCUT_WHISPER_MODEL` | `large-v3` | Modelo do faster-whisper |
| `MYCUT_WHISPER_DIR` | não definido | Caminho para um modelo local já baixado |
| `MYCUT_WEB_DIR` | `web/dist` | Interface compilada |
| `MYCUT_SEED` | `1` | Use `0` para iniciar sem importar o exemplo |

Para backup, pare os serviços e copie `.data` inteira. Os áudios originais em `audios/` e o material de `shorts/` continuam separados; preserve-os também.

## Verificação

```bash
uv pip install --python .venv-app/bin/python -r backend/requirements-test.txt
PYTHONPATH=backend .venv-app/bin/python -m unittest discover -s backend/tests -v
npm --prefix web run build
npm --prefix web run test:navigation
docker compose config --quiet
```

Testes de navegador usam dados temporários e API/worker reais. Com a porta 8321 livre e a interface compilada:

```bash
pnpm --dir web exec playwright install chromium
npm --prefix web run test:e2e
```

O cenário cobre criação, salvamento, proteção de texto não salvo, comparação, atualização entre abas, exportação real e download em desktop e celular. Screenshots e traces ficam em `web/test-results/`.

Passaram **45 testes de integração** do backend, incluindo diagnósticos de agentes, testes curtos de voz, respostas externas controladas e render real de um áudio de teste com tempos de fala, e **oito testes de navegação** com React e histórico controlado. A versão anterior também foi validada com a narração escolhida do Short original, de 45,87 segundos. A leitura real dos três catálogos foi conferida; chamadas de inferência na rodada anterior falharam por permissões locais (Codex/Grok) e sessão OAuth expirada sem renovação (Claude). Isso não comprova geração real nos provedores nem na ElevenLabs.

Na atualização de navegação, Docker build/up concluíram, os containers foram recriados e a API serviu o novo JavaScript. Na rodada das amostras de voz, **seis casos de navegador passaram em desktop/mobile**, usando o bundle real e respostas de API simuladas, sem consumir créditos. As capturas dessa tela foram inspecionadas. Isso não qualifica a síntese real nem substitui os casos de navegador das funcionalidades anteriores, que ficaram bloqueados naquela rodada. Consulte [a evidência e seus limites](docs/verificacao-studio.md).

## Direção editorial e visual

- Explicar notícias, modelos e ferramentas de IA com um ângulo próprio para o público brasileiro.
- Verificar as informações em fontes originais e manter as referências junto ao roteiro.
- Usar animações, fluxos e ilustrações que expliquem a narração, sem pessoas realistas geradas por IA.
- Revisar pronúncia, naturalidade, legibilidade e sincronização antes de publicar.

O Short do Claude Code usa creme, laranja e terracota, com a marca e o mascote na capa. A paleta acompanha esse assunto; não define a identidade de todas as produções futuras.

## Estrutura

```text
backend/mycut/                 API, armazenamento, mídia, renderização e worker
backend/tests/                 Integração ASGI, SQLite e exportação com FFmpeg
web/                           React, Vite, TypeScript e testes Playwright
scripts/start.sh               API + worker locais
scripts/agents.sh              Executor dos CLIs autenticados no WSL
compose.yaml                   API + worker em containers
.data/                         Dados pessoais do app (ignorado pelo Git)
docs/
  visao-e-experimentos.md       Histórico, propostas e resultados dos testes
experiments/narration/
  compare.py                   Comparação de narrador e voz pessoal
  refine.py                    Comparação de referências da voz pessoal
  narrate.py                   Narração de novos roteiros com o perfil local
  run.sh                       Instalação e execução do experimento Qwen
shorts/claude-cloud/
  roteiro.txt                  Texto da narração
  storyboard.json              Planejamento das cenas
  sources.json                 Referências da pauta
  publicacao.txt               Título, descrição, hashtags e tags do YouTube
  brand/                       Capa, referências visuais e prompt de criação
  align.py                     Alinhamento de cenas e legendas
  render.py                    Cenas, animações, legendas e exportação
  audio_review.py              Validação da avaliação da narração
  compare_narration.py          Experimento de correção da voz local
  finish.sh                    Narração disponível → alinhamento → vídeo
```

## Fluxo original por linha de comando

Execute a partir da raiz do projeto, em Linux ou WSL. Requisitos: Python 3.12, `uv`, FFmpeg com `ffprobe` e fontes DejaVu. Em Ubuntu, as dependências de sistema podem ser instaladas com:

```bash
sudo apt-get update
sudo apt-get install ffmpeg fonts-dejavu-core
```

Com `uv` disponível, prepare o ambiente mínimo para renderizar:

```bash
uv venv --python 3.12 .venv-narration
uv pip install --python .venv-narration/bin/python numpy Pillow
.venv-narration/bin/python shorts/claude-cloud/render.py --preview
```

Em uma cópia nova, sem áudio nem `timing.json`, esse comando cria uma **prévia sem narração, com tempos estimados**. Abra `shorts/claude-cloud/index.html` no navegador para assistir. O comando `--assets` gera somente as imagens das cenas, o storyboard e a cópia da capa.

As saídas são locais e ignoradas pelo Git. O renderizador não sobrescreve um MP4 existente: mova a versão anterior antes de renderizar novamente. Se já houver `timing.json`, ele exigirá o áudio correspondente e usará os tempos reais.

## Produção com narração

No ambiente já preparado, com a narração selecionada em `shorts/claude-cloud/audio/` e seu manifesto:

```bash
bash shorts/claude-cloud/finish.sh
```

O comando alinha a fala e renderiza o vídeo. Ele requer a biblioteca `faster-whisper` e o modelo `Systran/faster-whisper-large-v3` disponível no cache local `~/.cache/huggingface/hub/`; o alinhamento roda em CPU e não baixa pesos automaticamente. Na ausência do manifesto de áudio, o script tenta gerar a narração com o perfil Qwen local, que também precisa estar preparado.

A narração ElevenLabs do primeiro Short foi importada manualmente. O MP3 escolhido, os WAVs, os manifestos de áudio e os perfis pessoais não são distribuídos neste repositório. Uma cópia nova permite gerar a prévia visual; a produção com voz depende da preparação desses materiais locais.

Saídas principais:

| Arquivo local | Conteúdo |
| --- | --- |
| `shorts/claude-cloud/short.mp4` | Vídeo final com narração |
| `shorts/claude-cloud/previa.mp4` | Prévia de menor resolução |
| `shorts/claude-cloud/index.html` | Página para assistir e navegar pelas cenas |
| `shorts/claude-cloud/capa.png` | Cópia da capa usada na apresentação |
| `shorts/claude-cloud/legendas.srt` | Legendas alinhadas |
| `shorts/claude-cloud/render-manifest.json` | Hashes e informações do render |

Nenhum desses comandos publica no YouTube. A revisão final e o envio ainda são manuais.

## Experimentos de voz local

Os experimentos usam Qwen3-TTS e foram executados pelo proprietário em uma RTX 5070 Ti de 16 GB. Eles dependem de gravações, recortes, transcrições e perfis locais que não estão no Git.

Com as referências preparadas, o executor instala as dependências e baixa os modelos necessários:

```bash
bash experiments/narration/run.sh
```

`--cpu` permite executar a comparação sem CUDA. O refinamento e a geração com o perfil pessoal reutilizam versões e pesos já disponíveis; não são um assistente de configuração para uma instalação nova. Consulte o [histórico de experimentos](docs/visao-e-experimentos.md) para os requisitos e as avaliações de cada rodada.

## Arquivos versionados e arquivos locais

O Git inclui código, documentação, roteiros, fontes, metadados de publicação e os materiais de `brand/` necessários à capa. A arte final da capa é um recurso usado pelo renderizador, com prompt e origem registrados.

O `.gitignore` exclui gravações pessoais, perfis de voz, resultados de experimentos, vídeos, áudios, renders derivados, versões antigas, caches, pesos de modelos, ambientes virtuais, credenciais e configurações locais. Esses arquivos continuam no computador; ignorá-los não os apaga.

## Próximas etapas

1. Qualificar os provedores com os logins/voz reais e ampliar a direção visual para ilustrações e logos quando necessários.
2. Integrar coleta recorrente de tendências, upload e agendamento no canal.
3. Automatizar duas produções diárias, com retomada após falhas e acompanhamento de desempenho.

O [histórico de visão e experimentos](docs/visao-e-experimentos.md) preserva as propostas e decisões anteriores.
