---
status: accepted
---

# Documento de edição e operações compartilhadas

O storyboard, os agentes, o editor, a prévia e a exportação compartilham um
documento de edição versionado. Na Q41, o usuário definiu que tanto as edições
humanas quanto as dos agentes passam por operações aplicadas pelo mesmo núcleo;
nenhum agente escreve diretamente no documento. O formato tem versão de esquema
para permitir migrações futuras.

Esse caminho comum sustenta validação de dependências, proteção dos ajustes
humanos, autoria, edição concorrente, histórico e desfazer/refazer. Cada item
guarda se sua última alteração foi feita por agente ou humano. O registro da
última alteração não elimina a proteção de escolhas humanas anteriores que
continuem vigentes.

A decisão concentra as regras em um contrato único e mantém a composição editável,
em vez de permitir que cada agente ou tela altere o estado por caminhos próprios.
As operações representam cenas, faixas, mídias, trechos, tempos e efeitos, sem
impor uma estrutura narrativa ou template visual. O modelo é comum a diferentes
proporções; Q42 preserva o editor de Shorts atual até o piloto horizontal passar.

A aplicação de uma operação de edição e o envio de uma geração remota são ações
distintas: desfazer não estorna consumo nem reenvia chamadas ao refazer. Pedidos
pagos e com cota seguem as ADRs 0007 e 0013. A Q47 exige congelar uma revisão para
exportar MP4 e SRT correspondentes, com a revisão no nome dos arquivos. Edições
durante a exportação continuam permitidas, mas o resultado anterior não representa
a revisão nova. Exportações anteriores são preservadas até remoção explícita.

Na Q49, o usuário definiu escolher o motor por uma prova técnica na futura
implementação. Prévia e exportação devem usar o mesmo motor ou demonstrar
equivalência, incluindo efeitos, sincronização e reprodução de mídias. A prova
também verifica encode NVENC na RTX 5070 Ti no WSL, escala de 25 minutos e
licenciamento, com atenção a opções source-available. Nenhuma dessas capacidades
de runtime foi demonstrada nesta sessão. Este registro não autoriza implementação.
