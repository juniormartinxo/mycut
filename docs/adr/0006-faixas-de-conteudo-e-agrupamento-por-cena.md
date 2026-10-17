---
status: accepted
---

# Faixas por conteúdo e agrupamento por cena

O editor de vídeos horizontais organizará as cenas em sequência na linha do
tempo, com faixas para visuais sobrepostos, narração, música, efeitos sonoros
e textos. Os conteúdos de uma cena ficam agrupados para edição, sem exigir uma
faixa exclusiva para cada cena. Uma música, por exemplo, pode atravessar várias
cenas.

A Q9 definiu a cena como uma unidade de sentido da história. Ela pode conter
várias falas, mídias, textos, cortes e pausas: trocar uma imagem não exige criar
outra cena, e uma frase não equivale obrigatoriamente a uma cena.

Na Q28, o usuário definiu que cada trecho de fala pertence integralmente a uma
cena: uma cena pode conter vários trechos, mas um trecho não atravessa sua borda.
Isso não restringe conteúdos como música, que continuam podendo atravessar cenas.
Na Q34, proporção e resolução foram definidas como propriedades do projeto desde
o início. O piloto horizontal é 1920×1080, mas o modelo do editor deve também
comportar 1080×1920 para o futuro uso em Shorts, sem fixar 16:9.

Escolhemos essa organização em vez de uma faixa por cena para que vídeos longos
continuem navegáveis e conteúdos que atravessam cenas tenham uma representação
natural. A decisão foi confirmada pelo usuário na Q1 da entrevista de 2026-10-16.

As [ADR 0001](0001-composicao-de-cenas-em-blocos.md) e
[ADR 0004](0004-planos-fundo-e-comportamentos-no-tempo.md) descrevem o editor
atual de Shorts em blocos. Na Q42, o usuário definiu manter esse editor intocado
até o núcleo novo passar pelo piloto horizontal. O novo núcleo poderá então
atender a novos Shorts; converter os antigos será opcional, projeto a projeto,
preservando os originais sem sobrescrevê-los. A
[ADR 0012](0012-reajuste-da-montagem-apos-mudancas-na-fala.md) registra o reajuste
de tempos após mudanças na fala, incluindo conteúdos que atravessam cenas.

Este registro faz parte do planejamento. A sessão não autoriza implementação.
