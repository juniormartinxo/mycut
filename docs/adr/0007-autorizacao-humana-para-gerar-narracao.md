---
status: accepted
---

# Autorização humana para gerar a narração

A geração paga da narração dos vídeos horizontais depende de autorização humana:
o autor avalia o texto e decide quando liberar a geração, por causa do custo da
API. Essa exceção à produção automática de ponta a ponta foi definida pelo
usuário na resposta à Q2, em 2026-10-16.

Inicialmente, a Q2 previa que os visuais poderiam ser produzidos automaticamente
antes dessa avaliação. O usuário depois propôs antecipar a revisão por meio de
um storyboard com ícones e descrições, antes de produzir as mídias finais, para
reduzir desperdício. Essa revisão da sequência foi confirmada nas Q6–Q8 e
registrada na [ADR 0008](0008-storyboard-antes-da-producao-de-midias.md): storyboard,
revisão humana, autorização para gerar, narração, ajuste de tempos e produção das
mídias finais. Aprovar o storyboard e autorizar a geração são decisões distintas.
Uma nova geração paga após alterar a fala também fica sujeita à autorização humana.

Na Q27, o usuário definiu que cada autorização vale para um único pedido, com o
custo apresentado. A autorização fica vinculada ao texto exato dos trechos,
incluindo pontuação e grafia, à voz, ao modelo, às configurações da voz e ao
dicionário de pronúncia. Mudanças nesses elementos exigem revisar o alcance e o
custo da geração e obter nova autorização para o pedido alterado. Mudanças apenas
visuais não pedem nova voz.

A Q36 definiu esse pedido autorizado como um lote identificado de trechos, com
suas versões, escolhas de voz e custo total. O lote pode executar várias chamadas
à ElevenLabs sem exigir confirmação a cada trecho. A autorização vale apenas
para esse lote e não pode ser reutilizada em lotes futuros. Se um trecho falhar,
os outros continuam autorizados; o trecho com falha segue a regra de tentativas
técnicas da Q37. Áudio já disponível e reutilizado não é nova geração.

Novas tentativas ou falhas que façam o gasto ultrapassar o valor estimado exigem
nova autorização antes do gasto adicional. O valor apresentado não pode ser
tratado como uma permissão ilimitada para repetir chamadas. A Q31 exige registrar
todo pedido pago ou com cota antes do envio, com consumo por provedor e por
produção. A retomada consulta o provedor antes de pedir decisão humana sobre um
resultado ainda desconhecido, conforme a
[ADR 0013](0013-pedidos-registrados-e-resultados-vinculados-a-versoes.md).

Se o consumo real ultrapassar o valor apresentado, os novos envios desse lote
param e aguardam nova autorização. Isso não cancela retroativamente chamadas
remotas já enviadas nem bloqueia partes independentes da produção. A Q37 exige
acompanhar consumo e teto na unidade do provedor, como caracteres ou créditos
na ElevenLabs. O limite do lote e o teto aplicável ao provedor são controles
distintos; nenhum deles é ampliado automaticamente.

A Q29 permite reutilizar um áudio da API já existente quando o autor desfaz uma
alteração e volta à combinação de texto, voz e configurações daquele áudio.
Reutilizar não é gerar outra vez e não consome uma nova autorização de gasto.
Modelo e dicionário de pronúncia continuam entre as escolhas relevantes da Q27.

Na Q30, pedidos ainda não iniciados devem ser refeitos com as dependências atuais
antes do envio. Para narração, isso não transfere a autorização de uma versão
anterior para um texto ou configuração novos: o pedido alterado aguarda a
autorização correspondente. Um pedido já enviado termina, e seu resultado fica
como proposta quando conflita com a edição atual.

Alterações na fala exigem reavaliar a sequência e sua sincronização, conforme a
[ADR 0012](0012-reajuste-da-montagem-apos-mudancas-na-fala.md). A montagem anterior
não pode ser presumida sincronizada com uma fala modificada. A regeneração parcial
e seus vizinhos necessários são apresentados antes da autorização, conforme Q18.

A decisão é específica do fluxo horizontal em planejamento. A
[ADR 0005](0005-short-livre.md) continua descrevendo as pausas e a produção dos
Shorts atuais. A relação entre lote e chamadas por trecho está definida; a interface
detalhada da autorização e a estimativa por modelo/provedor ainda precisam ser
especificadas. Este registro não autoriza implementação nem consumo da API nesta sessão.
