---
status: accepted
---

# Contexto dos agentes no MyCut e passagem contínua de trabalho

Nas Q51–Q56, decididas em 2026-10-17, o usuário definiu como conversar com os agentes no editor
horizontal e como o contexto sobrevive à troca de agente, de provedor ou ao fechamento da página.
O Storyboard e a Montagem oferecem conversa sempre com o alcance visível: item, trecho de fala,
cena, sequência de cenas ou projeto inteiro. Selecionar um conteúdo define o alcance, e as conversas
ficam guardadas por alvo, podendo ser resolvidas e reabertas. No Storyboard, a conversa de uma cena
ou do projeto abre num modal próprio, compartimentado das demais conversas.

A memória fica no MyCut, não na sessão do CLI. Os CLIs continuam efêmeros, como no estúdio atual.
As conversas, as mensagens, o resumo versionado de cada conversa e as notas de passagem ficam no
SQLite local do projeto, fora do Git. O pacote de contexto enviado em cada chamada é guardado no
acervo por conteúdo ([ADR 0015](0015-recursos-por-conteudo-fora-do-git.md)) e referenciado pelo
pedido registrado ([ADR 0013](0013-pedidos-registrados-e-resultados-vinculados-a-versoes.md)).
O arquivo na fila do executor é apenas uma cópia de transporte.

Cada chamada recebe um pacote de tamanho controlado:
- o estado atual do alcance no documento de edição, que é a fonte da verdade;
- as fichas relevantes da bíblia visual;
- as regras de proteção humana;
- o resumo da conversa e as últimas mensagens completas;
- as notas de passagem daquele alvo.

Uma conversa sobre o projeto inteiro recebe o roteiro e o mapa de cenas, e o agente pede o detalhe
de cenas específicas quando precisar.

A passagem de trabalho é **contínua**, nunca preparada só na hora da troca. Depois de cada resposta,
o MyCut atualiza o resumo e grava a nota de passagem da execução (intenção, decisões, pendências e o
que não deve mudar), ligada às operações e ao alvo. Por isso, trocar de papel, trocar Codex por
Claude, fechar e reabrir a página ou retomar após uma falha usam o mesmo mecanismo. Quem assume
entende a conversa sem depender da memória de um modelo. Uma resposta interrompida não apaga o
último estado gravado e fica marcada como incompleta.

O provedor de cada papel continua sendo escolhido nas conexões, e o autor pode trocar em qualquer
conversa. Quando um CLI atinge o limite de uso, o MyCut avisa pela central de pendências e por
notificação e oferece continuar com o outro, sem trocar sozinho. Etapas automáticas pausam só
aquele papel até a escolha do autor.

A alternativa rejeitada foi manter sessões persistentes dos CLIs (por exemplo, retomar a sessão do
Codex ou do Claude). Isso prenderia a conversa a um provedor, deixaria o contexto fora da auditoria
e do controle de tamanho e contrariaria o executor efêmero e restrito do estúdio. O custo da decisão
é manter resumo e notas sempre atualizados e aceitar que um agente sabe apenas o que o pacote
contém. Este registro é de planejamento e não autoriza implementação.
