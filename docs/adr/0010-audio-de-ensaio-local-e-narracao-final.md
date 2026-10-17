---
status: accepted
---

# Áudio de ensaio local e narração final

> Substituída em parte pela [ADR 0020](0020-voz-principal-omnivoice-alinhador-mms-e-rota-tts.md) (MYC-12): o Qwen
> foi reprovado e o OmniVoice local passou a ser a voz principal, inclusive na narração final. A ElevenLabs virou
> a segunda via, por escolha do autor e com a autorização da ADR 0007. Continuam valendo os trechos de fala,
> o reaproveitamento, o alinhamento com origem e confiança e as pendências da Q39 e da Q45.

O vídeo terá áudio de ensaio gerado localmente com Qwen TTS. Na Q16, o usuário
escolheu como referência uma amostra da voz Junior da ElevenLabs em português
brasileiro, para manter a pronúncia brasileira no ensaio. A narração final será
sempre gerada pela API da ElevenLabs com a voz Junior; o Qwen fica exclusivamente
para testes. O usuário definiu a separação na Q12 e reforçou a obrigatoriedade
da API na Q15.

O uso de "treino" nessa resposta é tratado como ensaio do vídeo; não define uma
etapa de treinamento ou ajuste dos pesos do modelo. A variante do Qwen e as
condições de operação ainda precisam ser escolhidas ou qualificadas. A referência
selecionada corresponde ao perfil local baseado na Junior da ElevenLabs,
documentado em [Leia e Qwen](../leia-qwen.md), em vez do perfil da gravação pessoal
original. A avaliação futura do ensaio deve incluir naturalidade e pronúncia
brasileira; a escolha da referência, sozinha, não comprova esses resultados.

A [ADR 0007](0007-autorizacao-humana-para-gerar-narracao.md) continua exigindo
autorização humana antes da geração paga. A geração local de ensaio não autoriza
chamadas à ElevenLabs. Na Q15a, o usuário confirmou a ordem da
[ADR 0008](0008-storyboard-antes-da-producao-de-midias.md): o storyboard e o áudio
local de teste ficam disponíveis enquanto a voz final aguarda autorização,
incluindo a possibilidade de imagens-base durante o storyboard aceita na Q24.
Depois de gerar a voz final, os tempos são ajustados e as mídias finais são
produzidas. Assim, os clipes são planejados considerando a duração real da voz
que estará na entrega.

Não se presume que os dois áudios tenham duração ou pausas idênticas. O áudio
local permite ensaiar a sequência; a correspondência temporal com o áudio final
precisa ser reavaliada quando ele for gerado. Na Q18, o usuário aceitou gerar e
reaproveitar áudio por trechos, refazendo os alterados e os vizinhos necessários
para manter a entonação. Antes de gerar na ElevenLabs, o alcance e o custo estimado
são apresentados para autorização. A Q27 detalhou a validade dessa autorização na
ADR 0007; a Q26 definiu o reajuste temporal na
[ADR 0012](0012-reajuste-da-montagem-apos-mudancas-na-fala.md). As fronteiras dos
trechos foram definidas na Q28: blocos de sentido, normalmente parágrafos ou pausas
naturais, sem cortar frases no meio. Cada trecho fica inteiro dentro de uma cena;
o autor pode juntar ou dividir trechos. Usar contexto textual vizinho e encadeamento
entre pedidos quando a API oferecer, regenerando vizinhos apenas quando necessário
e dentro do alcance autorizado.

Toda geração na ElevenLabs deve solicitar tempos por caractere. Esses tempos
orientam o alinhamento de textos, legendas e mídias à voz final. O áudio e seus
tempos precisam permanecer associados para permitir reaproveitamento. Na Q39,
o usuário aceitou tentar recuperar o alinhamento ausente ou inválido e, se isso
não resolver, alinhar localmente o áudio já gerado. O mesmo alinhador local atende
ao ensaio Qwen, que retorna WAV sem tempos. Cada alinhamento registra sua origem:
API, histórico ou local. Baixa confiança vira pendência antes da exportação; não
autoriza regenerar voz paga.

A Q45 permite resolver baixa confiança por conferência humana ou correção dos
tempos, mostrando forma de onda e marcas de palavras. O ajuste é por palavra ou
frase, não por caractere, e conta como ajuste humano protegido. Alinhamento ausente
ou estruturalmente inválido precisa de correção. Se a voz for regenerada, a
correção antiga permanece no histórico, mas deixa de valer para o novo áudio e
essa incompatibilidade é sinalizada; nunca é descartada silenciosamente.

Na Q29, o usuário confirmou que uma fala alterada usa Qwen na prévia, enquanto os
demais trechos podem manter a voz final válida. A interface indica o ensaio. A
duração do Qwen vale na timeline enquanto aquele trecho estiver em ensaio; quando
chega a voz final, aplicam-se os reajustes da Q26.

Os áudios são guardados pela combinação de texto, voz e configurações, incluindo
modelo e dicionário de pronúncia conforme Q27. Desfazer uma alteração e voltar à
combinação anterior torna o áudio da API novamente utilizável, sem gerar de novo.
O histórico conserva também a origem e o contexto da geração. Reaproveitamento
não dispensa a conferência das emendas com os trechos vizinhos; uma eventual nova
geração paga mantém sua autorização própria. A Q38 permite recortes e junções
quando texto e ordem são preservados: usar o alinhamento para cortar em pausas
ou fins de frase, com transição curta nas emendas e conferência para evitar
estalos e respirações cortadas. Uma emenda tecnicamente válida com entonação
inadequada gera sugestão de regeneração; não dispara geração automática.

Uma falha ou indisponibilidade da ElevenLabs deixa a narração final pendente:
o áudio de ensaio não pode ser usado como substituto na entrega final.

Na Q35, o usuário definiu legenda gravada na imagem desligada por padrão, ativável
por projeto ou prompt. Toda exportação final também produz um arquivo SRT da
narração final, sincronizado ao MP4, mesmo sem legendas gravadas na imagem.

A Q48 separou o piloto completo, de cerca de 15 minutos com voz final autorizada,
do ensaio técnico de 25 minutos. Este último usa Qwen e mídias baratas ou esboços,
sem consumo de ElevenLabs, e mede escala. Seu artefato de teste não é uma entrega
final nem uma exceção à obrigatoriedade da voz da API no vídeo finalizado.

Esta decisão introduz duas etapas de áudio para reduzir a necessidade de
regenerações pagas durante a revisão. A qualidade de voz, o custo total e o
desempenho em vídeos de 10–25 minutos ainda precisam de validação. Este registro
é de planejamento e não autoriza implementação ou geração de mídia.
