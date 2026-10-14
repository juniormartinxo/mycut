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

## Escopo ainda pendente

A qualificação real dos três CLIs exige login e acesso aos modelos no host; disponibilidade do executável não garante autenticação. A geração real ElevenLabs exige chave/voz configuradas no app. A interação no navegador continua sem execução nesta sessão pelas restrições já descritas. Coleta recorrente de tendências, duas execuções diárias e envio/agendamento no YouTube continuam requisitos ainda não implementados. O resultado atual vai até vídeo disponível para revisão e download.
