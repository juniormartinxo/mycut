# Issue tracker: It's a Plan

Issues e especificações do MyCut ficam em [jm/MYC](http://localhost:43101/jm/MYC).
Use o servidor MCP `itsaplan`, com `projectKey: "jm.MYC"`.
Os identificadores legíveis são `MYC-N`.

## Consultar e resolver IDs

- Para `MYC-N`, chame `get_issue_by_number({projectKey: "jm.MYC", sequenceNumber: N})`.
  Use o `id` numérico retornado nas operações que recebem `issueId` ou `parentId`.
- Antes de escrever, consulte `get_project({projectKey: "jm.MYC"})` para resolver
  colunas, tipos, rótulos, campos, opções e responsáveis atuais. IDs pertencem ao
  projeto e devem ser resolvidos a cada sessão.
- Use `search_issues` para procurar por texto e verificar duplicatas antes de criar.
  Use `list_issues` para filtros de coluna, responsável, tipo ou pai.
  Respeite o limite de resultados e explicite quando uma consulta não cobre todo o projeto.
- Leia o ticket completo com `get_issue`; consulte `list_issue_activity` para
  entender a conversa antes de responder ou acrescentar um comentário.

## Publicar e trabalhar em tickets

Quando uma skill disser "publish to the issue tracker", crie uma issue com
`create_issue`. Quando disser "fetch the relevant ticket", leia a issue pelo
identificador ou ID numérico.

- Escreva títulos e descrições em português, com escopo e critérios de aceite.
- Escolha a coluna por `stateType`: `backlog` para propostas,
  `unstarted` para trabalho pronto, `started` ao iniciar,
  `completed` ao concluir e `canceled` ao abandonar.
  Se várias colunas compartilham o mesmo tipo, escolha a etapa adequada entre as
  retornadas pelo projeto; ao iniciar, use a primeira por `position`.
- A triagem é independente da coluna. Siga [triage-labels.md](triage-labels.md)
  quando uma skill pedir para aplicar ou remover um papel de triagem.
- Para subtarefas, use `parentId` com o ID numérico do pai em
  `create_issue` ou `update_issue`. Publique um ticket por unidade de trabalho.
- Registre dependências nativas com
  `link_issues({issueId: <bloqueado>, targetIssueId: <bloqueador>, kind: "blocked_by"})`.
  Crie bloqueadores primeiro quando publicar um conjunto de tickets.
- `update_issue.labelIds` substitui todos os rótulos: preserve os rótulos
  existentes que não fazem parte da mudança solicitada.
- Use `add_comment` quando a tarefa ou skill pedir comunicação no ticket.
  Ao responder a um comentário, forneça `replyToId`. Na conclusão normal,
  comente apenas se houver trabalho pendente ou uma entrega explicitamente solicitada.
- Após cada escrita, releia a issue com `get_issue` e confira os campos alterados,
  relacionamentos ou comentários antes de informar que a operação foi concluída.

## Wayfinding

- O mapa é uma issue; cada ticket é uma subtarefa ligada por `parentId`.
- Use os rótulos `wayfinder:map` e `wayfinder:<tipo>` definidos pela skill,
  resolvendo-os em `get_project`. Se faltarem, solicite sua criação a quem tiver
  permissão de administrar rótulos antes de publicar o mapa.
- Consulte os filhos com `list_issues({projectKey: "jm.MYC", parentId: <mapa>})`.
  Leia seus bloqueadores e responsáveis para encontrar trabalho aberto,
  desbloqueado e sem responsável, seguindo a ordem registrada no mapa.
- Assuma um ticket com `update_issue.assigneeUserId`, resolvendo o responsável
  entre os membros atuais do projeto.
- Ao resolver, registre a resposta e a referência na issue do mapa e conclua
  o ticket. Use os vínculos nativos para avaliar bloqueios.

**PRs as a request surface: no.**
