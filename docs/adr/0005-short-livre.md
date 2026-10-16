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

Implementado no MYC-5. O diretor devolve fundo, cor do texto, cor de destaque e
uma família do Google Fonts, e o projeto guarda isso como um estilo próprio
(`format_id` "free"), que nunca aparece entre os formatos e só vale para um
Short livre. Uma fonte fora do catálogo pede correção. Uma fonte que não baixa
vira Roboto, com aviso.

## Legendas

O diretor também define a legenda: de 2 a 4 palavras por vez, as
palavras-chave na cor de destaque, o tamanho e a posição (no alto, no meio ou
embaixo). Todas as posições ficam na área segura, fora dos 15% inferiores e da
faixa direita dos botões do YouTube. Uma frase de uma palavra junta-se à
vizinha, e uma pausa sempre corta a legenda. A prévia e o MP4 calculam e
desenham a legenda com o mesmo código, a partir do relógio da cena, e o
`legendas.srt` traz os mesmos trechos. Os formatos mantêm a legenda anterior.

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

Implementado no MYC-5. A pausa fica na cena como uma âncora: o trecho da
narração depois do qual ela entra e a duração, de 0,2 a 3 s. Uma pausa cujo
trecho não está na fala é removida, com aviso. Se a narração for editada
depois e o trecho sair da fala, a pausa continua salva, mas não tem efeito, e a
aba Roteiro a mostra como não aplicada. A voz é pedida por trechos, cada um com
o texto vizinho (`previous_text` e `next_text`) para manter a entonação. O
`eleven_v3` não aceita essa costura, então nele cada trecho é falado sozinho.
Os trechos são unidos com silêncio real, e os tempos das palavras são
deslocados. A estimativa sem narração soma o mesmo silêncio. Mudar uma pausa
muda o roteiro falado, e a narração salva deixa de valer.

## Loop e pacote de publicação

Quando o prompt pede loop, o último plano funde em 0,4 s no primeiro quadro do
Short, sem legenda, e o mantém nos últimos 0,1 s, na prévia e no MP4. Com um
vídeo de encerramento, o loop não é aplicado, porque o encerramento vem depois
do último quadro. Um aviso dos agentes explica isso (decisão do usuário em
16/10/2026).

O roteirista entrega o pacote de publicação: de 1 a 5 opções de título (a
primeira é a usada), descrição, tags, hashtags e o comentário fixado pedido no
prompt. Na aba Publicação, cada opção pode virar o título, e hashtags e
comentário têm um botão de copiar. O pacote não é editável nesta versão. O
`publicacao.txt` traz o pacote completo.
