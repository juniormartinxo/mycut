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

A navegação fica no endereço: `#/conexoes`, `#/fila`, `#/novo` e `#/producoes`. No editor, a URL também identifica a produção e a aba. Atualizar a página preserva essa localização; Voltar e Avançar acompanham a navegação. Links antigos `#<id-da-produção>` continuam funcionando. Alterações não salvas no editor mantêm o aviso de descarte ao sair.

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

1. No aplicativo, abra **Conexões**. Distribua os CLIs entre Pesquisa, Roteiro, Direção visual e Conferência. Escolha o modelo na lista e clique **Testar agente** em cada papel. O teste usa a seleção atual sem salvá-la; clique **Salvar agentes** quando terminar. **Padrão do CLI** deixa a escolha a cargo do CLI.
2. Na seção **ElevenLabs**, cole uma chave de API da sua conta e clique **Conectar ElevenLabs**. A chave precisa permitir listar vozes/modelos e gerar fala. Não coloque a chave no roteiro, Git ou chat. [Documentação de autenticação](https://elevenlabs.io/docs/api-reference/authentication).
3. Selecione a voz **Junior**, ou outra da sua conta, o modelo e os ajustes. Clique **Salvar voz**. A lista vem da conta conectada.
4. Em **Novo Short**, informe a **Pauta ou link** e escolha **Produzir com agentes**. Para conferir o roteiro antes de gastar voz, escolha **Roteiro e cenas primeiro**.

Conectar/listar vozes não sintetiza áudio. Produzir a voz usa créditos da conta ElevenLabs. Não há repetição automática da requisição paga após erro. O texto completo vai em uma única requisição para preservar a continuidade da narração. Os [tempos de fala retornados pelo provedor](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps) alimentam a sincronização de cenas e legendas. O MP3 de transporte fica como intermediário; a trilha usada no render é WAV normalizado.

A indicação “executor conectado” comprova o processo ativo e os executáveis disponíveis no PATH; não comprova login, saldo ou acesso a cada modelo. **Testar agente** executa uma solicitação curta pelo mesmo adaptador usado na produção, valida um desafio e mostra resposta, duração, ID solicitado e modelo informado nos metadados do CLI. O teste usa a cota do CLI; não gera voz ou vídeo. Há um teste por vez, cancelamento e limite de três minutos, incluindo espera na fila. O último resultado de cada papel permanece disponível após recarregar a página.

Claude e Grok podem informar `modelUsage`: o app distingue confirmação, modelo diferente e resolução do padrão. No adaptador Codex atual, a resposta pode ser validada, mas o modelo efetivamente usado **não é confirmado**. Uma declaração do próprio modelo nunca serve como confirmação de identidade.

Os seletores recebem IDs do cache local de modelos do Codex/Grok e da inicialização do Claude Code, sem copiar credenciais. O catálogo não comprova acesso nem login. **Atualizar modelos** relê essas fontes quando o executor está livre; se a lista faltar ou estiver antiga, abra o CLI no WSL antes de atualizar. Trocar de CLI limpa o modelo selecionado. Nomes antigos digitados à mão precisam ser selecionados novamente. Após atualizar o MyCut, reconstrua os containers e reinicie também `bash scripts/agents.sh` para carregar o novo executor.

## Fluxo de produção

1. Pesquisa abre fontes e reúne fatos com referências. Se não conseguir verificar a pauta, o fluxo para.
2. Roteiro cria narração, título, descrição e tags. Direção visual cria cenas de animação/fluxo e o conceito da capa, desenhada pelo renderizador geométrico local.
3. Conferência compara as afirmações com a pesquisa. Pode pedir uma correção; se reprovar novamente, o fluxo para antes da voz.
4. ElevenLabs gera a narração usando a voz salva. Pillow/FFmpeg renderizam o Short em 1080 × 1920, com cenas animadas e legendas.
5. Você acompanha as etapas, assiste ao resultado e baixa vídeo, capa, legendas, roteiro, publicação e manifesto.

A conferência automática é uma etapa editorial, não uma garantia de verdade. A revisão final continua disponível antes de publicar. O agente de direção usa os formatos fluxo, comparação e destaque; esta versão não gera ilustrações raster, mascotes ou logos novos por modelo de imagem.

O editor permanece para ajustar o material, importar voz/capa, gerar apenas a narração ou renderizar novamente sem pagar por outra voz. Comparações têm dois lados. Limites de edição: 12 cenas, 500 palavras, áudio até 3 minutos e 100 MB; capa até 15 MB. A geração ElevenLabs aceita até 4.000 caracteres. O agente de roteiro trabalha com até 180 palavras e 3 a 8 cenas.

Projetos e fila persistem em SQLite. Cada tentativa tem diretório próprio; etapas concluídas salvam checkpoints no projeto, e o job atualiza sua revisão. Edições concorrentes ficam bloqueadas durante a produção. Após cancelamento, resultados atrasados não podem substituir novas alterações. Ao reiniciar o worker, jobs em execução ficam marcados como interrompidos e não são repetidos automaticamente.

“Roteiro do Claude Code” era uma cópia fixa das sete cenas do primeiro Short, não um agente. Essa opção saiu da criação. O primeiro Short continua disponível como produção existente, e os arquivos originais em `shorts/claude-cloud/` permanecem intactos.

## Executar sem Docker

Requisitos: Node.js 24+, pnpm 12.8.1, Python 3.12, `uv`, FFmpeg/ffprobe e fontes DejaVu. No Ubuntu:

```bash
sudo apt-get update
sudo apt-get install ffmpeg fonts-dejavu-core
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

Passaram **36 testes de integração** do backend, incluindo diagnósticos de agentes, respostas externas controladas e render real de um áudio de teste com tempos de fala, e **oito testes de navegação** com React e histórico controlado. A versão anterior também foi validada com a narração escolhida do Short original, de 45,87 segundos. A leitura real dos três catálogos foi conferida; chamadas de inferência nesta sessão falharam por permissões locais (Codex/Grok) e sessão OAuth expirada sem renovação (Claude). Isso não comprova geração real nos provedores nem na ElevenLabs.

Na atualização de navegação, Docker build/up concluíram, os containers foram recriados e a API serviu o novo JavaScript. Os dez casos de navegador estão preparados e listados, mas não foram executados porque Chromium permaneceu bloqueado. Consulte [a evidência e seus limites](docs/verificacao-studio.md).

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
