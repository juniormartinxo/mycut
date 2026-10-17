---
status: accepted
---

# Canal como dono dos padrões e das orientações

Em 2026-10-17 (Q67–Q69), o usuário definiu que o MyCut passa a ter **canal** como entidade e que
cada projeto pertence a um canal. Até aqui, o mais próximo disso era o texto `channel_name` no
estilo visual de cada projeto. As orientações do canal, aprendidas com o que o autor aceita e
descarta ([ADR 0017](0017-base-comum-para-shorts-com-motion-e-videos-horizontais.md)), não podem
misturar as preferências de um canal de Shorts sobre IA com as de um canal dark de histórias.

O canal guarda:
- o nome e a marca;
- o template padrão de cada formato;
- a voz e as configurações padrão da narração;
- as orientações do canal;
- mais tarde, a publicação no YouTube.

Um projeto herda esses padrões e pode sobrescrevê-los no próprio projeto. Trocar um padrão do
canal não altera material já gerado nem dispara nova geração. Os tetos de consumo continuam por
produção e provedor ([ADR 0013](0013-pedidos-registrados-e-resultados-vinculados-a-versoes.md)).

Por decisão do usuário, o canal é o **primeiro card a ser executado** (MYC-33), antes da
qualificação técnica e do documento de edição. Isso cria uma exceção explícita à Q61: os projetos
de Shorts existentes são vinculados a um canal padrão antes do piloto horizontal. A mudança se
limita a esse vínculo. Cada projeto mantém o próprio `channel_name` e renderiza exatamente como
antes.

As orientações do canal aprendem só com o que o autor aceita e descarta. Aprender com os ajustes
que o autor refaz no editor fica num card próprio (MYC-34): o MyCut detecta padrões recorrentes no
mesmo canal e **propõe** uma orientação com a evidência, que só vale depois de aceita, no padrão de
proposta da [ADR 0009](0009-pedidos-de-correcao-com-aplicacao-direta.md).

A alternativa rejeitada foi uma lista global de preferências, mais simples, mas que misturaria
canais de linguagens diferentes e exigiria migração assim que um segundo canal existisse. Este
registro é de planejamento e não autoriza implementação.
