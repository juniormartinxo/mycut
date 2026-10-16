---
status: accepted
---

# Short livre: o prompt como especificação

Hoje todo Short segue um molde fixo: pesquisa obrigatória, arco gancho →
explicação → consequência → encerramento e cena 20/60/20. O Short livre
(MYC-2) aceita um prompt, que pode ser uma ideia solta ou um roteiro completo,
e deixa os agentes decidirem estrutura, ritmo e composição. As decisões abaixo
saíram do grilling de 15/10/2026 e orientam as subtarefas MYC-4 a MYC-8. A
composição no tempo está na [ADR 0004](0004-planos-fundo-e-comportamentos-no-tempo.md).

## Convivência com os formatos

Livre é um quinto caminho em **Novo**, ao lado de Editorial, Radar tech, Passo
a passo e Impacto. Os quatro formatos continuam com o fluxo atual. No modo
Livre, paleta, fontes e fundo do Short nascem do tom do prompt, escolhidos pelo
diretor, sem um formato de base.

## Fidelidade ao prompt

Quando o prompt traz um roteiro completo, narração, texto na tela e ordem dos
blocos seguem o texto literalmente. Só são permitidos ajustes de grafia e
pontuação para a fala sair natural. A conferência verifica essa fidelidade além
dos fatos. Quando o prompt é só uma ideia, o roteirista escreve com liberdade
de estrutura.

## Pesquisa opcional

O roteirista lista as afirmações factuais externas (ferramentas, preços,
datas). A pesquisa só roda se a lista não estiver vazia, e só para esses itens.
Conteúdo autoral ou fictício nunca é conferido em fontes. Uma afirmação não
verificada vira aviso no roteiro completo, ou é suavizada se o roteiro foi
criado pelo agente, e nunca recusa a produção. A regra de não inventar fatos
continua valendo.

## Conferência e degradação

Implementado no MYC-4. A conferência pede uma correção ao roteiro e à direção.
Se reprovar de novo, o roteiro e as cenas já pagos ficam salvos no projeto, com
os problemas como avisos, e a produção para antes da voz, para não gastar
créditos ElevenLabs num roteiro infiel (decisão do usuário em 16/10/2026). O
mesmo vale quando a conferência falha (erro do CLI, tempo esgotado, saída
ilegível) e quando a correção não pode ser feita: fica o trabalho da primeira
rodada. Uma pesquisa que falha deixa as afirmações como não verificadas. A
direção tem uma correção; depois disso, alturas, mídias inexistentes, textos
que não cabem e âncoras fora da fala são reparados, e uma saída inutilizável
vira uma composição simples com o texto na tela do roteiro. Todo reparo é
medido de novo; texto encurtado ou objeto removido para caber vira aviso. Os anexos de
imagem entram na biblioteca da produção; os de texto são acrescentados ao
prompt.

## Personagens e avatares

No modo Livre, personagens fictícios realistas são permitidos em imagens e
B-rolls gerados. Avatares também são permitidos quando o contexto justifica o
uso, conforme ressalva do usuário no grilling. Pessoas reais identificáveis
continuam proibidas. Os quatro formatos mantêm a regra de animações e
diagramas, sem apresentadores humanos realistas.

## Mídia gerada

Um papel novo, **Arte**, configurável como os outros agentes, gera as imagens
das cenas com Codex ou Grok (o Claude Code só desenha SVG), reaproveitando a
máquina da capa. O diretor extrai do prompt a **bíblia visual** (tom, fichas de
personagem e cenário). A Arte gera primeiro as imagens-base e as anexa como
referência às seguintes, com estimativa de custo antes.

Os B-rolls em vídeo não têm integração nesta versão. O agente entrega a
**lista de materiais**, com prompt, ferramenta sugerida, referências e duração
de cada clipe, e diz com clareza o que está faltando. Enquanto o clipe não
chega, o plano usa a imagem gerada com movimento de câmera e não bloqueia a
exportação. Importar o clipe substitui o fundo do plano.

## Pausas

Pausas explícitas no roteiro livre viram silêncio no áudio, inserido entre
trechos sintetizados, sem depender de tags do provedor de voz. Planos e
legendas consideram esse silêncio. Os formatos continuam sem pausas.
