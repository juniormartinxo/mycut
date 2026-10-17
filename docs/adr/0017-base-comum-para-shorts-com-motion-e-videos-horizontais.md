---
status: accepted
---

# Base comum para Shorts com motion e vídeos horizontais

Em 2026-10-17, duas frentes de planejamento chegaram a soluções paralelas para o mesmo problema:
- o épico MYC-9 (Shorts com motion livre: cena em HTML, mapa, câmera, templates e direção com
  versões);
- o plano horizontal (MYC-10 a MYC-22, ADRs 0006–0016).

Seguir as duas criaria dois motores, dois modelos de documento, dois vocabulários e dois jeitos de
pedir alterações ao agente. Nas Q59–Q63 o usuário aceitou convergir tudo numa base comum.

- **Um motor.** A qualificação do MYC-11 serve aos dois formatos (9:16 e 16:9). Os candidatos são:
  - o HTML determinístico do protótipo do MYC-9 (quadro calculado como função do tempo e gravado
    num Chrome sem janela);
  - o Remotion, com a licença a avaliar;
  - o render atual em Python/FFmpeg, só como referência de comparação.

  Os critérios somam os dois lados: paridade entre prévia e exportação quadro a quadro, mola,
  desfoque, brilho e vidro fosco, fontes embutidas sem rede, nenhuma animação por relógio, ensaio
  de 25 min, NVENC no WSL e mixagem a −14 LUFS. O motor em HTML não estava escolhido: tinha sido
  aprovado só como protótipo, que verificou o determinismo do quadro sem gravar MP4 nem medir tempo.
- **Um documento.** O documento de edição da [ADR 0014](0014-documento-de-edicao-e-operacoes-compartilhadas.md)
  recebe as faixas no tempo (horizontal) e o mapa com câmera (Shorts) como recursos do mesmo modelo.
  Os tempos ficam presos à fala nos dois casos, com o reajuste da
  [ADR 0012](0012-reajuste-da-montagem-apos-mudancas-na-fala.md). O "modelo de cena livre" do
  MYC-9 deixa de ser um modelo próprio.
- **Um vocabulário.** Vale o do glossário (cena, faixa, item). Mapa (do vídeo inteiro, com cada cena
  numa região), câmera, esmaecimento, marca do canal, template, ousadia, objeto livre e pedido de
  versões são acrescentados. Nos Shorts com motion, os elementos do mapa também são itens. "Bloco" e "plano" mantêm o sentido do
  editor atual de Shorts.
- **Um mecanismo de agente.** Valem as ADRs [0009](0009-pedidos-de-correcao-com-aplicacao-direta.md)
  e [0016](0016-contexto-dos-agentes-no-mycut-e-passagem-continua.md):
  - um pedido explícito é aplicado direto, com desfazer;
  - um **pedido de versões** gera N propostas do mesmo pedido, e nada é aplicado até o autor
    escolher uma ou misturar; a escolha vira operações comuns;
  - as orientações do canal, aprendidas com o que o autor aceita e descarta, entram no pacote de
    contexto.
- **Templates** são formato e não composição: fundo padrão, cores, fontes, estilo dos objetos e da
  legenda e orientação aos agentes. Servem aos dois formatos.

A ordem da [Q42](../planejamento-video-horizontal.md) se mantém (Q61):
1. a base comum: motor (MYC-11), documento (MYC-14), prévia e exportação (MYC-15);
2. o piloto horizontal;
3. o motion nos Shorts (MYC-9), com os Shorts atuais intocados até lá.

O Short livre ([ADR 0005](0005-short-livre.md)) continua no motor atual até o motion nos Shorts ser
aceito com o ponta a ponta do Argon. Depois migra como mais um tipo de produção no documento novo,
com conversão opcional (Q63). Template para o Short livre fica fora por enquanto.

A decisão troca autonomia entre as frentes por uma dependência explícita: o MYC-9 passa a esperar
pela base comum e pelo piloto horizontal. Em troca, o MyCut evita manter dois motores e dois
modelos e permite que melhorias de motion e de edição sirvam aos dois formatos. Este registro é de
planejamento e não autoriza implementação.
