---
status: accepted
---

# Geração de clipes no fluxo inicial com alternativa manual

> Atualização (MYC-12): onde esta decisão supõe a voz final da API anteceder as mídias finais, vale a
> [ADR 0020](0020-voz-principal-omnivoice-alinhador-mms-e-rota-tts.md): o OmniVoice local é a voz principal,
> inclusive na narração final, e a ElevenLabs é a segunda via.

A geração automática de clipes por IA faz parte da primeira versão, conforme
a Q11. Na Q17, o usuário definiu a preferência por acionar Grok ou Gemini a partir
do ambiente local. Quando esse caminho não for possível, o agente deve entregar
o prompt pronto para o usuário gerar na plataforma e adicionar o clipe em
Recursos.

Essa escolha mantém a produção utilizável quando a automação de uma plataforma
não está disponível. O fluxo passa a admitir intervenção humana para obter o
clipe, sem exigir que o usuário invente o prompt. Contratar ou consumir uma API
paga adicional de vídeo não fez parte da decisão aceita.

Na Q21, o usuário confirmou que "local" significa executar ferramentas no
computador conectadas às plataformas pela internet, usando os acessos existentes.
A inferência dos modelos de vídeo ocorre no serviço remoto. Há indícios de
ferramentas de vídeo no CLI Grok instalado, mas nenhuma geração ou disponibilidade
de conta foi validada nesta sessão. Essa evidência não representa uma integração
de vídeo pronta no MyCut.

Na Q19, o usuário confirmou que cada pedido de clipe fica vinculado ao destino
na timeline, com prompt, referências, duração desejada e proporção. Importar o
arquivo pelo pedido adiciona o clipe em Recursos e preenche o esboço correspondente,
sem exigir reconstruir a montagem. A Q15a confirmou que a produção das mídias
finais vem depois da voz final da API e do ajuste dos tempos.

A Q20 permite gerar prévia a qualquer momento, com os materiais disponíveis,
mantendo a exportação do vídeo finalizado para quando a produção estiver concluída.
As partes independentes podem avançar enquanto um clipe aguarda importação.
A Q32 definiu uma tentativa inicial e duas novas por qualidade para cada mídia,
ampliáveis explicitamente pelo humano. Falhas técnicas sem resultado têm limite
próprio, e a contagem é preservada na retomada. Os pedidos pagos ou com cota são
registrados antes do envio, conforme a
[ADR 0013](0013-pedidos-registrados-e-resultados-vinculados-a-versoes.md). A Q37
definiu três tentativas técnicas totais e tetos por produção/provedor nas unidades
próprias, com consumo visível e bloqueio localizado. A Q50 define prioridade por
produção e alternativa automática somente entre provedores com acesso confirmado.
O limite de tentativas por mídia soma os provedores, sem reinício ao trocar.
Alcançar um teto não redireciona silenciosamente os pedidos bloqueados para outro
provedor; trabalhos independentes continuam.

Para continuidade, mídias do mesmo personagem ou cenário dentro de uma cena
preferem o mesmo provedor. Toda mídia que passar por troca de provedor exige
conferência visual contra a bíblia e as imagens-base. A existência de um CLI ou
de uma ferramenta documentada não comprova acesso na conta; essa qualificação
faz parte da prova técnica futura. O piloto completo da Q48 exige ao menos um
clipe gerado automaticamente e exercício da alternativa manual.

Esta decisão amplia o fluxo de materiais descrito para os Shorts na
[ADR 0005](0005-short-livre.md), sem alterar seu comportamento atual. É um registro
de planejamento, sem autorização para implementar ou gerar mídias nesta sessão.

Em 2026-10-17, a [qualificação do MYC-13](../qualificacao-integracoes.md) verificou os CLIs. O Grok Build
gerou um clipe com imagem-base pelo acesso existente, com o ZDR da conta desligado, mas esconde a requisição
remota (sem identificador, consumo, consulta ou recuperação) e ficou registrado como não auditável para
automação. O Gemini CLI não tem ferramenta de vídeo. Até que um controle por pedido seja comprovado, vale a
alternativa manual desta decisão.
