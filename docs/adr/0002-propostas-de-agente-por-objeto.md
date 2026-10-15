---
status: accepted
---

# Alterações de agentes como propostas por objeto visual

Um objeto visual pode ser marcado como assunto de uma conversa com o agente,
usando seu conteúdo como contexto. A marcação permanece visível e não
dispara alterações automaticamente. O agente apresenta mudanças em uma
prévia, identificando os objetos afetados, para o usuário aceitar ou descartar
antes de substituir a versão atual; isso vale para conteúdo, tamanho e estilo.

Escolhemos propostas explícitas em vez de aplicar automaticamente as edições
do agente, permitindo avaliar a composição antes de alterar o trabalho atual.
Essa decisão define o contrato de colaboração do novo editor e foi confirmada
pelo usuário em 2026-10-15.

Se o objeto ou o bloco que o contém mudar enquanto o agente trabalha, a
proposta anterior fica desatualizada e não pode sobrescrever a edição atual.
O usuário pode pedir uma nova proposta considerando o conteúdo atualizado.
Essa regra de conflito foi confirmada na segunda rodada da entrevista.

Conversas e marcações persistem no projeto ao fechar o editor. Uma conversa
pode ser resolvida e reaberta. Trocar o conteúdo preserva a conversa; excluir
seu objeto arquiva o histórico sem transferi-lo para outro objeto.

Cada pedido tem alcance explícito: objeto selecionado, bloco vazio ou cena
inteira. O agente recebe a cena e a narração como contexto, mas só propõe
alterações dentro do alcance escolhido. Uma mudança de altura pode compensar
apenas um vizinho imediato, movendo uma borda por vez. A prévia inclui esse
ajuste de altura; a aceitação ou o descarte aplica-se ao conjunto.
Essas regras foram confirmadas na terceira rodada da entrevista em 2026-10-15.
