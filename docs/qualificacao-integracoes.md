# Qualificação das integrações locais (MYC-13)

Prova técnica de 17/10/2026 para as integrações que rodam no computador do autor: clipes por Grok e Gemini a
partir dos CLIs instalados (Q17, Q21, Q50 e [ADR 0011](adr/0011-geracao-de-clipes-e-alternativa-manual.md)) e
notificações do Windows emitidas pelo serviço no WSL com a janela do MyCut fechada (Q43, Q44 e
[ADR 0013](adr/0013-pedidos-registrados-e-resultados-vinculados-a-versoes.md)). Produz evidência, não
funcionalidade do produto. O código está em [`qualificacao/integracoes/`](../qualificacao/integracoes/README.md);
clipes, sessões e respostas dos CLIs ficam em `qualificacao/integracoes/.saida/`, fora do Git.

## Resultado

| Critério | Grok Build | Gemini CLI |
| --- | --- | --- |
| Acesso | Confirmado: login grok.com, ferramentas de imagem e vídeo liberadas na conta | Login `oauth-personal` funcionando, segundo o autor após atualizar para 0.64.0; não testado com prompt nesta prova |
| Vídeo com referência | **Gerado**: `reference_to_video` com `first_frame`, depois de desligar o ZDR da conta | **Indisponível pelo CLI**: nenhuma ferramenta de vídeo |
| Controle por pedido | Parcial: um prompt restrito resultou em uma chamada, mas quem decide é o modelo; cada chamada aparece depois de decidida | Não se aplica |
| Identificador e consumo | Sessão e turno escolhidos/devolvidos; tokens e custo de texto informados. Sem id remoto do vídeo nem consumo em gerações | Não se aplica |
| Consulta e recuperação | Não há: o envio e a espera são internos à ferramenta | Não se aplica |
| Sem cota | Não exercitado; há mensagens próprias no binário (seção Grok) | Não se aplica |
| Auditável para automação | **Não**: esconde a requisição remota (envio e espera internos, sem id nem consumo da geração) | Não se aplica |

**Notificações: qualificadas.** Um toast disparado de uma unidade systemd de usuário no WSL, sem janela do
MyCut aberta, foi entregue e visto pelo autor. O bloqueio pelo app é detectado. O Não perturbe não é detectável.
O toast ainda não abre o projeto ao ser clicado (lacuna da Q44, abaixo).

Consequência para o plano: o Grok gera clipes com o acesso existente, mas pelo critério desta prova fica
**não auditável para automação**: o pedido ao servidor acontece dentro da ferramenta, sem identificador,
consumo, consulta ou recuperação, e a decisão de chamar é do modelo do agente. Com isso, não cumpre o
registro antes do envio e a retomada da ADR 0013. Pela Q50, nenhum dos dois provedores entra como alternativa
automática por enquanto. O caminho é a alternativa manual (prompt pronto e importação pelo pedido). Um portão
por chamada, que exige aprovação antes de cada `reference_to_video` (seção Grok), pode tornar o controle por
pedido auditável; ele fica para qualificar na MYC-20, sem resolver a falta de recuperação.

## Autorizações de cota

Registradas na conversa de implementação da MYC-13, em 17/10/2026, como respostas do autor a perguntas
explícitas, antes de cada uso:

| Antes de | Pergunta | Resposta do autor |
| --- | --- | --- |
| Rodada 1 (18:18) | Gerar clipe no Grok Build, headless, restrito a `reference_to_video`, 480p, 16:9, 6 s | "Até 2 gerações": a segunda só se a primeira falhar tecnicamente sem resultado |
| — | Mandar um prompt de texto ao Gemini CLI para confirmar o login | "gemini e agy atualizados e funcionando" (nenhum prompt enviado) |
| Rodada 2 (18:35) | Depois da recusa por ZDR: registrar e parar, ou desligar o ZDR e testar | "Desligo o ZDR e testamos" |

Uso efetivo: **1 geração de vídeo** (rodada 2). A rodada 1 foi recusada pelo provedor antes de gerar. As duas
rodadas gastaram tokens de texto do modelo do agente: 31.136 e 31.985 tokens, US$ 0,0146 e US$ 0,0164 pelo
custo que o próprio CLI informa. Manter ou religar o ZDR depois da prova é decisão do autor; religado, o vídeo
volta a ser recusado.

## Ambiente

| Item | Valor |
| --- | --- |
| Windows | 11, versão 26H2 (NT 10.0.26300), Windows PowerShell 5.1.26100 |
| WSL | 3.0.3.0, kernel 6.18.54.1, systemd 255, Ubuntu 24.04 |
| Grok Build | 1.0.50 (stable), modelo `grok-4.7-build` |
| Gemini CLI | 0.47.0 no início da prova, 0.64.0 depois da atualização feita pelo autor |
| Antigravity CLI (`agy`) | 1.4.1, só como observação |

## Grok Build

### O que o CLI oferece

O `grok` é um agente de código. Não tem um comando de vídeo; o vídeo é uma ferramenta que o modelo chama.
Pela documentação local (`~/.grok/docs`), pela skill embutida `imagine` e pelo binário:

- Ferramentas de mídia: `image_gen`, `image_edit` e `reference_to_video`. Não existe texto para vídeo: o
  vídeo parte de imagens. `reference_to_video` aceita até 14 `images` de referência (re-renderizadas),
  `first_frame`/`last_frame` fixos, até 4 `keyframes`, até 3 `voices` predefinidas, `aspect_ratio`,
  `duration` de 1 a 15 s e `resolution_name` 480p ou 720p.
- `/imagine-video` monta um roteiro de tomadas, gera imagens-base com `image_gen` e anima cada uma. Um pedido
  dessa forma vira várias gerações escolhidas pelo modelo, o que não serve para registrar e limitar por pedido.
- No modo headless (`-p`/`--prompt-file`) dá para limitar as ferramentas (`--tools`), proibir subagentes,
  limitar turnos e escolher o id da sessão (`--session-id`). A saída `streaming-json` publica cada chamada
  de ferramenta (`tool_call`) com os argumentos exatos e cada atualização (`tool_call_update`) com o status.
- A configuração remota da conta tinha `video_gen_enabled` e `image_gen_enabled` ligados. O binário traz a
  mensagem de bloqueio para os planos gratuito e X Basic ("Video generation is a SuperGrok feature…").

### Rodadas

`sondar_grok.sh` fez um pedido com uma imagem-base desenhada localmente (1280×720, barco de papel no terço
esquerdo, sem `image_gen`), pedindo uma única chamada com `first_frame`, 16:9, 6 s e 480p. Restrições:
`--tools reference_to_video`, `--disallowed-tools Agent`, `--no-subagents`, `--disable-web-search`,
`--max-turns 3` e `GROK_MAX_PARALLEL_VIDEO_GEN_CALLS=1`. A rodada 2 também usou `--deny MCPTool`, acrescentado
depois que a rodada 1 mostrou que `--tools` não remove os servidores MCP.

| Rodada | Início | Duração | Resultado |
| --- | --- | --- | --- |
| 1 | 18:18:53 | 42 s | Uma chamada, recusada: "Video generation tools are unavailable under zero data retention (ZDR). To enable, either turn off /privacy mode to disable ZDR or supply a user-hosted storage bucket" |
| 2 | 18:35:42 | 44 s (17,9 s na ferramenta) | Uma chamada, concluída: `videos/1.mp4` dentro da pasta da sessão em `~/.grok/sessions/` |

O clipe da rodada 2 tem **736×400**, H.264 a **24 qps**, 6,04 s, áudio AAC estéreo de 48 kHz com som ambiente
gerado (média −41,5 dB, pico −26,8 dB) e uma capa MJPEG. O primeiro quadro reproduz a imagem-base, e o barco
atravessa até o terço direito como pedido. Para o MyCut: "480p 16:9" não sai em 16:9 exato (1,84:1) nem a
30 qps, então a importação precisa ajustar enquadramento e taxa. O áudio vem junto e deve entrar mudo por padrão.
O arquivo fica com permissão 0600 fora da pasta de trabalho; o adaptador copia pelo caminho de `rawOutput.path`.

### Respostas aos critérios

- **Acesso.** Confirmado com a conta do autor (login grok.com, sem chave de API). O vídeo exige o ZDR
  desligado ou um bucket S3 próprio (`tools.zdr_video_output_s3`); o bucket seria outro serviço contratado,
  fora do aprovado na ADR 0011.
- **Controle por pedido.** Na rodada 2, um prompt resultou em exatamente uma chamada de `reference_to_video`,
  com os argumentos pedidos. É o modelo do agente que decide chamar; as restrições acima reduzem, mas não
  impedem por contrato, uma segunda chamada no mesmo turno. O adaptador deve contar e limitar as gerações pelos
  eventos `tool_call`, não pelo prompt. Esse evento chega com status `pending` e o `events.jsonl` registra
  `permission_requested` antes da execução: num modo de permissão com aprovação por chamada (modo `default`
  com o agente em `stdio`/ACP), o adaptador poderia registrar e liberar cada geração antes do envio. A prova
  usou `bypassPermissions` e não exercitou esse portão. Observação: `--tools` não remove os servidores MCP
  configurados no `~/.grok` do usuário (o evento `available_commands` anunciou 390 ferramentas). `--deny MCPTool`
  bloqueia a execução, mas elas continuam anunciadas. O adaptador deve rodar com um `GROK_HOME`/config sem MCP.
- **Identificador e consumo.** Existem o id da sessão (escolhido por nós), o id do turno (`requestId` no
  evento `end`) e o id da chamada (`toolCallId`). O id da geração no servidor da xAI não é devolvido no
  sucesso; o binário só o cita em erros ("Video generation request expired (request_id=…)", "failed on the
  server (request_id=…)"). O consumo informado (`grok usage <sessão>` e o evento `end`) é só de tokens e custo
  do texto. Não há contagem de gerações nem saldo de cota de vídeo: o MyCut conta as próprias gerações.
- **Consulta e recuperação.** Não há ferramenta nem comando para consultar uma geração ou baixar de novo um
  resultado. O envio e a espera acontecem dentro de `reference_to_video`. Se o serviço cair durante a espera,
  o pedido fica com resultado desconhecido, sem id remoto para conciliar. Não foi provocada uma interrupção:
  custaria uma terceira geração não autorizada.
- **Sem cota.** Não exercitado: exigiria esgotar a cota. O binário tem os tipos `UsageLimitReached`,
  `UsagePoolExhausted`, `RateLimited` e `GlobalRateLimit` e a mensagem de bloqueio por plano; a skill instrui o
  agente a relatar e não repetir. A recusa por ZDR mostrou o caminho: `tool_call_update` com `status: failed` e
  a mensagem do provedor em `rawOutput.message`, sem arquivo.
- **Auditabilidade.** O CLI esconde a requisição remota: envio, espera, id e consumo da geração ficam dentro
  da ferramenta. Pelo critério da prova, o Grok Build fica **registrado como não auditável para automação**.
  O que ele expõe é a chamada de ferramenta: argumentos, status e arquivo de cada geração, e, no `events.jsonl`
  da sessão, início, permissão e fim com duração. Isso basta para contar depois, não para registrar antes do
  envio nem para retomar (ADR 0013).

## Gemini CLI

- O login é `oauth-personal` (Gemini Code Assist para pessoas físicas). As ferramentas embutidas da 0.47.0 e
  da 0.64.0 são de arquivo, shell, busca, web, planejamento e tarefas. Não há ferramenta de imagem nem de
  vídeo, nem extensões ou servidores MCP instalados.
- O pacote 0.47.0 trazia o SDK `@google/genai` com tipos de `generateVideos` (Veo), mas sem ferramenta
  exposta ao modelo. Gerar com Veo exigiria uma chave da Gemini API ou um projeto Vertex AI com cobrança:
  outra API, fora do aprovado.
- **Conclusão:** o Gemini CLI não gera vídeo. Fica registrado como sem acesso automático a clipes, e a
  Q50 não o inclui entre as alternativas automáticas. O caminho é a alternativa manual: gerar no app Gemini e
  importar pelo pedido.
- O `agy` (Antigravity CLI 1.4.1), também do Google e instalado, expõe `generate_image`, mas não vídeo; o
  binário tem só tipos de resposta de vídeo do Vertex AI.

## Notificações do Windows

### Ponte

`ponte_windows.py` roda no WSL e chama o `powershell.exe` do Windows pela interoperabilidade. O
`ponte_windows.ps1` faz o lado Windows:

1. Registra o AUMID `MyCut` em `HKCU\Software\Classes\AppUserModelId\MyCut` com `DisplayName`. Assim o toast
   sai com o nome MyCut sem atalho no Menu Iniciar, e o MyCut aparece em Configurações > Sistema > Notificações
   depois do primeiro aviso.
2. Remove da Central um aviso anterior com a mesma `Tag`/`Group` e mostra o toast pelo `ToastNotificationManager`
   (WinRT). Sem essa remoção, um aviso antigo com a tag repetida faria a conferência do passo 3 dar entregue
   mesmo que o novo não aparecesse. A remoção entrou depois da revisão do PR e foi conferida reenviando a
   mesma tag.
3. Devolve o `ToastNotifier.Setting`, a chave global `PushNotifications\ToastEnabled` e as tags presentes na
   Central de Notificações (`History.GetHistory`). `Show()` não falha quando o app está bloqueado, então a
   entrega é conferida no histórico.

Um processo do serviço não tem o `PATH` com as pastas do Windows: a primeira tentativa a partir do systemd
falhou com `FileNotFoundError: 'powershell.exe'`, e a ponte passou a usar o caminho fixo como alternativa.
Também não herda o `WSL_INTEROP` do terminal; a ponte usa o mesmo alias `/run/WSL/1_interop` de
`scripts/agents.sh`.

### Verificações

Disparos com `systemd-run --user` (o mesmo contexto do `mycut-agents.service`), com as janelas e abas do
MyCut fechadas, conferidos pelo histórico e pelo autor:

| Hora | Situação | Ponte | Autor |
| --- | --- | --- | --- |
| 18:14:48 | MyCut liberado, Não perturbe desligado | `entregue: true`, `liberada` | Viu o aviso na tela |
| 18:16:12 | Autor desligou o MyCut em Configurações | `entregue: false`, `bloqueada_no_app` | — |
| 18:16:51 | MyCut religado, Não perturbe ligado | `entregue: true`, `liberada` | Só na Central, sem aviso na tela |

O Windows ainda oferece `DisabledForUser`, `DisabledByGroupPolicy`, `DisabledByManifest` e `ToastEnabled = 0`
(todas as notificações desligadas). A ponte os traduz, mas eles não foram provocados nesta máquina.

### Limites encontrados

- **Antes do primeiro toast**, `Setting` falha com "Element not found" (0x80070490): o Windows ainda não
  conhece o app. A ponte informa `desconhecida`, que não significa bloqueio.
- **Não perturbe não é detectável.** Com ele ligado, o toast entra na Central sem aviso na tela, e a ponte vê
  `liberada` e `entregue`. `SHQueryUserNotificationState` respondeu `QUNS_ACCEPTS_NOTIFICATIONS` nos dois
  estados. O estado WNF não documentado `WNF_SHEL_QUIETHOURS_ACTIVE_PROFILE_CHANGED` ficou em 1 nos dois
  (só o carimbo mudou). A central do MyCut continua sendo a garantia, como pede a Q44. A interface pode
  avisar que o Não perturbe silencia os avisos, sem afirmar o estado atual.
- **Não gravar o registro de configurações à mão.** Na primeira tentativa, gravar `Enabled = 0` em
  `HKCU\…\Notifications\Settings\<AUMID>` bloqueou o app, mas gravar 1 ou apagar o valor não liberou mais. O
  Windows passou a guardar o estado na própria base, e nem a tela de Configurações recuperou aquela entrada. O
  AUMID de teste foi removido, e a prova recomeçou com o `MyCut` limpo. O MyCut só lê o estado e orienta o
  autor a mudar pela tela de Configurações.
- **Acesso ao projeto (Q44) não verificado.** O toast da prova não tem `launch` nem `activationType`, então
  clicar nele não abre o MyCut. Sem um ativador COM registrado, o caminho a verificar na implementação é a
  ativação por protocolo (`activationType="protocol"` com a URL do projeto no navegador).
- O ícone do MyCut no aviso não foi configurado (`IconUri` no registro do AUMID); fica para a implementação.
- As respostas JSON da ponte não foram guardadas em arquivo: a tabela de verificações é o registro delas.
