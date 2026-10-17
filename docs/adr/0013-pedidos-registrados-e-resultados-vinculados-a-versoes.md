---
status: accepted
---

# Pedidos registrados e resultados vinculados a versões

A produção longa admite edição humana e falhas durante gerações remotas. Nas
Q30–Q31, o usuário definiu registrar todo pedido pago ou com cota antes de enviá-lo,
preservando exatamente o conteúdo enviado, e salvar progresso, resultados,
autorizações e consumo por provedor e por produção. Isso permite retomar sem
refazer trabalho válido nem presumir que perder a resposta significa não ter gerado.

Se uma dependência mudar antes do envio, o pedido é refeito com a versão atual,
respeitando a autorização de narração da
[ADR 0007](0007-autorizacao-humana-para-gerar-narracao.md). Depois de enviado, o
registro do que foi pedido permanece preservado. Uma mudança durante a execução
não faz o resultado substituir a edição humana: ele termina e fica como proposta
quando houver conflito. Resultados compatíveis podem ser aplicados automaticamente.

Na retomada, consultar primeiro o provedor para tentar confirmar e recuperar a
geração; pedir decisão humana apenas quando a dúvida persistir. O registro local
ajuda a conciliar pedidos, mas não garante que todo provedor ofereça consulta,
recuperação ou proteção contra geração duplicada. Pedidos com resultado desconhecido
continuam diferentes de falhas técnicas confirmadas sem resultado.

A Q32 separa o limite de tentativas por qualidade das tentativas por falha técnica.
O primeiro é uma tentativa inicial mais duas novas por mídia, com ampliação
explícita pelo autor. A Q37 fechou as falhas técnicas confirmadas sem resultado
em três tentativas totais, com intervalos crescentes. Retomar não zera contadores.
Os tetos são configuráveis por produção e provedor, usando unidades próprias:
caracteres ou créditos na ElevenLabs, número de gerações no Grok/Gemini. A interface
mostra consumo em relação ao teto. Atingir um teto para somente os envios daquele
provedor no alcance do limite; o trabalho independente continua. Uma falha técnica
não consumir tentativa de qualidade não significa ser gratuita ou liberar gasto
acima do autorizado. Liberar tentativas extras para uma mídia não aumenta
automaticamente o teto da produção.

Na Q43, pausar impede novos envios sem bloquear edições humanas ou prévia. Pedidos
já enviados continuam sendo acompanhados e seus resultados são guardados, sem
presumir cancelamento ou estorno remoto. Fechar a janela não cancela o serviço
local; desligar o computador interrompe o serviço, e a retomada segue a consulta
e recuperação da Q31. Com a janela fechada, o autor deve ser notificado quando
houver pendência, teto atingido ou dúvida sobre um pedido enviado. A Q44 definiu
central persistente no MyCut e notificações do Windows, uma por pendência nova,
com resumo agrupado por produção quando várias surgirem juntas. Como o backend
está no WSL, a ponte no lado Windows precisa ser verificada na prova técnica;
toast via `powershell.exe` é um exemplo, não uma integração já qualificada.
Notificação apenas na página não atende ao requisito de janela fechada. Se o
sistema bloquear notificações, a interface informa essa condição e conserva as
pendências na central.

Pausa voluntária, bloqueio de envios por um teto e pendência que impede exportação
são condições distintas. Elas não devem bloquear automaticamente a edição, a
prévia ou trabalhos independentes. A autorização por lote e a continuidade dos
trechos que não falharam estão na ADR 0007.

A decisão favorece continuidade e edição durante trabalhos demorados, em troca
de manter versões, pedidos, consumo e resultados parcialmente aplicáveis. Este
registro é de planejamento e não autoriza implementação ou geração nesta sessão.

Em 2026-10-17, a [qualificação do MYC-13](../qualificacao-integracoes.md) verificou a ponte: um toast via
`powershell.exe` com AUMID próprio, disparado por um serviço de usuário no WSL com a janela fechada, foi
entregue, e o bloqueio pelo app é detectado. O Não perturbe não é detectável: com ele ligado o aviso vai só
para a Central de Notificações, o que reforça a central do MyCut como garantia.
