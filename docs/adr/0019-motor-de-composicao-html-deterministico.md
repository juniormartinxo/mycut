---
status: accepted
---

# Motor de composição em HTML determinístico

Em 2026-10-17, a qualificação do MYC-11 comparou, com a mesma composição em 9:16 e 16:9, o HTML
determinístico do protótipo do MYC-9, o Remotion 4.0.536 e o render atual em Python/FFmpeg como
referência ([relatório](../qualificacao-renderizacao.md)). Pela Q49, a escolha saía de uma prova
técnica; pela [ADR 0017](0017-base-comum-para-shorts-com-motion-e-videos-horizontais.md), o motor
serve aos dois formatos.

**O motor de composição escolhido é o HTML determinístico.** O vídeo é descrito como dados e o estado de
cada quadro é uma função só do tempo (`quadroEm(cena, t)`). A mesma página desenha a prévia, tocando com
o relógio do áudio ou parada num instante, e a exportação, em que abas de um Chromium sem janela
pedem cada quadro e o FFmpeg codifica (NVENC quando houver). O som é o mesmo grafo WebAudio nos dois
casos: tocado em tempo real na prévia e renderizado offline na exportação, depois masterizado pela
Q46.

Por que este e não o Remotion:
- **Desempenho equivalente.** No hardware alvo os dois ficaram na mesma faixa de tempo de
  exportação. O gargalo é a captura de quadros pelo Chromium na CPU, igual nos dois.
- **Paridade sob controle do MyCut.** As diferenças entre prévia e exportação encontradas no Remotion
  vêm de caminhos que o MyCut não controla: o Player e o renderizador decodificam vídeo e misturam
  áudio por caminhos diferentes (cor de vídeo sem marcação, mono para estéreo), e o Player reduz a
  composição com `transform`, que quebra o vidro fosco. Mesmo com as mitigações, a mistura que o Player toca
  desvia até 10 LU da exportada nas rampas da música. No motor HTML os dois lados passam pelo
  mesmo código e pelo mesmo navegador, e os desvios encontrados (o mesmo `transform`, o quadro do
  `<video>` e um laço de desenho duplicado na prévia) foram corrigidos no próprio motor. Resta uma
  variação de rasterização do Chromium em bordas, de poucos pixels, conforme a ordem dos quadros.
- **Licença.** O MyCut é público. O Remotion exige licença paga de empresas com mais de três
  pessoas, condição que passaria a quem usa o MyCut. Com a chave `free-license`, o renderizador envia
  um evento de uso aos servidores do Remotion a cada render. O motor HTML usa só peças com licença
  permissiva (Chromium, Playwright, fontes OFL) e o FFmpeg do sistema.
- **Continuidade.** É o modelo do protótipo do MYC-9 e cabe no contrato de documento e operações da
  [ADR 0014](0014-documento-de-edicao-e-operacoes-compartilhadas.md) sem um segundo runtime React.

O custo da escolha fica com o MyCut: a mídia de vídeo entra como sequência de quadros preparada
(o `<video>` não é confiável para quadros exatos), a reprodução de clipes longos na prévia precisa
de pré-carga, e o gerenciamento de memória, a retomada da exportação e o paralelismo são código
próprio. O Remotion resolveria parte disso (`OffthreadVideo`), mas as diferenças medidas entre a
prévia e o arquivo dele teriam de ser contornadas fora dele.

Regras que passam a valer para o motor:
- nada de animação CSS, transição, temporizador ou relógio do sistema no desenho de um quadro;
- fontes e bibliotecas locais, carregadas antes do primeiro quadro, e gravação sem rede;
- vídeo de entrada com cor marcada e convertido para o formato de edição (quadros) na preparação;
- narração em estéreo ou com regra explícita de mono para estéreo, igual na prévia e na exportação;
- a prévia reduz a composição com `zoom`, nunca com `transform: scale()`.

O Short livre e os Shorts atuais continuam no motor Python até as migrações previstas na
ADR 0017. Este registro escolhe o motor; o documento de edição (MYC-14) e a prévia e exportação do
editor (MYC-15) ainda serão construídos sobre ele.
