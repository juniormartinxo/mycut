---
status: accepted
---

# Pedidos de correção com aplicação direta e desfazer

No novo editor de vídeos horizontais, um pedido explícito do autor pode ser
aplicado diretamente pelo agente dentro do alcance solicitado, com opção de
desfazer. Sugestões espontâneas do agente continuam como propostas para aceitar
ou descartar. O usuário confirmou essa decisão ao aceitar Q3–Q5 na entrevista
de 2026-10-16.

Escolhemos distinguir pedidos explícitos de sugestões em vez de exigir uma
segunda aceitação para toda correção já solicitada. Isso reduz etapas na revisão
do vídeo, mantendo o alcance definido pelo autor e a possibilidade de desfazer.

A decisão revisa, para o editor horizontal, o contrato da
[ADR 0002](0002-propostas-de-agente-por-objeto.md), que exige aceitação prévia de
todas as propostas no editor atual de Shorts. Esse editor atual continua seguindo
a ADR 0002. A política ao aproveitar o novo editor nos Shorts será explicitada
na [ADR 0014](0014-documento-de-edicao-e-operacoes-compartilhadas.md); a Q42
preserva o editor antigo e permite conversão posterior opcional, sem sobrescrita.

Um pedido de correção não libera automaticamente geração paga de narração:
continua valendo a [ADR 0007](0007-autorizacao-humana-para-gerar-narracao.md).
Na Q13, o usuário confirmou a preservação dos ajustes manuais mesmo em pedidos
amplos, como "refaça esta cena". Um pedido explícito para substituir esses ajustes
libera a alteração, mantendo desfazer. Incompatibilidades devem ser apontadas,
sem sobrescrever silenciosamente o trabalho humano.

A Q30 permite editar durante a produção. Pedidos ainda não enviados são
atualizados para as dependências vigentes, respeitando autorizações de gasto;
resultados de pedidos já em andamento que conflitem com a edição ficam como
propostas. A Q33 permite refazer automaticamente mídias produzidas pelo agente
que o autor não ajustou, dentro dos limites da Q32, quando uma mudança de sentido
as afeta. Mídias ajustadas pelo autor continuam como proposta ou pendência.

Correções de grafia ou palavra sem mudança de sentido não disparam essa revisão
semântica. Mudanças em roupa, lugar ou outra característica de uma ficha também
colocam a ficha e suas imagens-base em revisão. O vínculo dos resultados às versões
está registrado na
[ADR 0013](0013-pedidos-registrados-e-resultados-vinculados-a-versoes.md). O histórico
é persistente; eventual limpeza depende de escolha humana conforme Q40, sem
introduzir descarte automático por quantidade de operações.

A Q41 definiu operações comuns para as edições humanas e dos agentes, aplicadas
pelo núcleo, com histórico e autoria. Nenhum agente escreve diretamente no
documento. Cada item registra quem fez sua última alteração; esse marcador não
substitui o histórico dos ajustes humanos que continuam protegidos. A
[ADR 0014](0014-documento-de-edicao-e-operacoes-compartilhadas.md) registra esse
contrato. Desfazer a montagem não desfaz uma chamada já enviada nem apaga seu
consumo; reaproveitar o resultado continua possível conforme Q29 e Q38.

Este registro é de planejamento e não autoriza implementação.
