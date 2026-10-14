# MyCut

<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
React, Vite e TypeScript na interface; FastAPI, worker Python e SQLite; Docker Compose. Proposta aceita pelo proprietário em 13/10/2026 com “Ok, senta o dedo”.

## Users
Junior, criador de conteúdo brasileiro, operando no computador Windows com WSL Ubuntu e RTX 5070 Ti de 16 GB.

## Product Purpose
Produzir dois Shorts por dia sobre IA com um fluxo do início ao fim por agentes: descoberta e pesquisa, roteiro, capa e direção visual, narração, montagem e publicação. Essa automação é o objetivo solicitado desde o início. O editor manual serve para revisão e ajustes, não substitui o fluxo por agentes.

## Operating Context
O primeiro Short e sua voz ElevenLabs já foram escolhidos na conversa. Preservar os arquivos originais. Novos projetos e suas versões ficam separados. O processamento deve continuar com a aba fechada enquanto os serviços estão ativos.

## Capabilities and Constraints
Estado inicial corrigido nesta rodada: o primeiro app entregou somente edição e render manuais; essa redução de escopo foi feita pelo implementador, não autorizada como substituição do objetivo. Integração solicitada: Codex CLI, Claude Code CLI e Grok CLI para agentes; ElevenLabs para voz. Agendamento e publicação continuam requisitos a implementar, não exclusões decididas pelo usuário. Interface deve distinguir trabalho em fila, execução, falha, resultado desatualizado e pronto para revisão. Arquivos pessoais e dados de execução não vão para o Git.

## Brand Commitments
Nome MyCut. Português brasileiro. Os vídeos usam animações e fluxos, sem apresentadores realistas. O laranja do Claude é específico do primeiro Short; não é uma restrição de marca do aplicativo.

## Evidence on Hand
shorts/claude-cloud contém roteiro, fontes, thumbnail, áudio e vídeo locais. Nenhuma métrica de audiência ou execução automática deve ser inventada.

## Product Principles
- Manter rastreabilidade e versões dos materiais.
- Permitir refazer uma etapa sem apagar o resultado anterior.
- Apresentar falhas e limitações com uma ação de recuperação.
- Priorizar a operação por agentes; manter revisão e edição como controles opcionais sobre resultados reais.

## Open Decisions
Distribuição para terceiros e uso remoto ainda não foram definidos. Publicação automática exige a conexão do canal e faz parte do objetivo original. Aparência da interface foi delegada junto à implementação; decisões visuais desta rodada são escolhas de implementação, não preferências permanentes do proprietário.
