# Qualificação da renderização (MYC-11)

Prova técnica de 17/10/2026 para escolher o motor de composição comum aos vídeos horizontais (16:9) e aos
Shorts com motion (9:16), pedida pela Q49 e pela [ADR 0017](adr/0017-base-comum-para-shorts-com-motion-e-videos-horizontais.md).
Produz evidência e uma escolha; não é funcionalidade do produto. O código da prova está em
[`qualificacao/render/`](../qualificacao/render/README.md); vídeos, quadros e relatórios ficam em
`qualificacao/render/.saida/`, fora do Git.

**Escolha: o motor HTML determinístico** ([ADR 0019](adr/0019-motor-de-composicao-html-deterministico.md)).
Os três motores ficaram na mesma faixa de tempo no hardware alvo. O HTML foi o único em que prévia e
exportação casaram em imagem e som sem depender de caminhos fora do controle do MyCut, e não carrega as
condições de licença do Remotion para um repositório público.

## Hardware e versões

| Item | Valor |
| --- | --- |
| Máquina | AMD Ryzen 7 5700G; o WSL2 enxerga 8 CPUs lógicas (4 núcleos × 2) e 62 GB de RAM |
| GPU | NVIDIA GeForce RTX 5070 Ti, 16 GB, driver 617.42 (Windows), CUDA no WSL por `/usr/lib/wsl/lib` |
| Sistema | WSL2, kernel 6.18.54.1-microsoft-standard-WSL2 |
| Navegador | Chromium headless shell 156.0.8078.4 (Playwright 1.64) |
| FFmpeg | 6.1.1 do Ubuntu (o Remotion usa o próprio, n7.1) |
| Remotion | 4.0.536 |

A máquina é compartilhada com outros projetos. Cada relatório guarda a carga (load average) no início; as
rodadas usadas abaixo tiveram carga entre 2,8 e 10 no minuto anterior, e uma rodada anterior sob carga 11–20
foi descartada para tempos (o Remotion levou 222 s ali e 125 s com a máquina calma).

## O que foi montado

A mesma composição, com o vídeo descrito como dados por `montarCena` e o estado de cada quadro calculado por
`quadroEm(cena, t)`, foi desenhada pelos candidatos em 1080×1920 e 1920×1080, a 30 qps. Cada cena ocupa uma
região do mapa e repete o mesmo roteiro visual:

- mapa maior que o quadro (1,3 vez o quadro por cena) com a câmera que viaja, aproxima e recua;
- camadas sobrepostas, texto em Inter e JetBrains Mono embutidas;
- itens com entrada por mola, esmaecimento com desfoque, brilho e um item de vidro fosco (`backdrop-filter`);
- corte seco do mapa para uma imagem com movimento de câmera (aproximação e panorâmica), fusão para um clipe
  acelerado 2× que congela, com um item de vidro por cima, e corte de volta ao mapa;
- legenda em grupos de três palavras presas à fala, com destaques;
- narração de ensaio Qwen (local) e música sintetizada, com a música abaixando na fala e subindo nas pausas.

Todos os tempos saem de inícios de palavras alinhadas pelo Whisper local. O Short tem 65,3 s (179 palavras,
uma cena); o ensaio de escala tem 26,4 min (4.210 palavras, 28 cenas).

O código da prova é anterior ao documento de edição (MYC-14) e usa nomes próprios: lá, `cena` é o vídeo
inteiro, `capitulo` é a cena do glossário, `trecho` é um intervalo visual (mapa, imagem ou clipe) que entra por
corte ou fusão, não um trecho de fala, e `item` é o item do mapa. O documento de edição vai seguir o glossário.

Os candidatos:

1. **HTML determinístico** (`motor-html/`): a página aplica `quadroEm(t)` ao DOM. Na prévia, o relógio é o
   do áudio (WebAudio); na exportação, abas de um Chromium sem janela pedem cada quadro com `irPara(t)`,
   capturam a tela por CDP e um coordenador entrega os quadros em ordem a um único FFmpeg. O áudio é o mesmo
   grafo WebAudio, renderizado offline em blocos de 60 s.
2. **Remotion 4.0.536** (`motor-remotion/`): a mesma cena em React, com o idioma do Remotion para mídia
   (`OffthreadVideo` com `playbackRate`, `Freeze`, `Sequence`, `Img`, `Audio` com volume por quadro).
   Exportação por `renderMedia`; prévia pelo `<Player>`.
3. **Motor atual em Python/FFmpeg** (`referencia-python/`), só como referência: refaz um Short real já
   produzido (55,4 s, seis cenas em blocos) com o próprio `production.make_video`, numa cópia isolada dos
   dados. Ele não desenha mapa, câmera, mola, desfoque nem vidro, por isso não monta a mesma composição.

## Como a paridade foi provada

Compartilhar código não conta, então cada prova compara pixels e amostras de som produzidos pelos dois lados:

- **Imagem, prévia parada.** A prévia roda na resolução de prévia da Q34 (405×720 no 9:16, 1280×720 no 16:9).
  Em 37 instantes escolhidos para exercitar cada recurso (quadro antes e depois de cada corte, meio da fusão,
  mola, esmaecimento, câmera em movimento, clipe acelerado e congelado, imagem com zoom, mais uma grade
  regular), a prévia vai direto ao instante e é capturada; o mesmo quadro é decodificado do MP4 e reduzido
  ao tamanho da prévia. A semelhança é medida por SSIM.
- **Tempos.** Cada captura também é comparada com os quadros exportados vizinhos (−2 a +2). Um erro de tempo
  aparece como um vizinho claramente melhor que o próprio quadro; empates abaixo de 0,005 de SSIM são
  ruído de reamostragem (câmera lenta, cena parada). Nos cortes a diferença é grande (0,94 contra 0,34).
- **Imagem, prévia tocando.** Com a narração tocando, dez quadros da prévia são capturados no meio da
  reprodução e comparados da mesma forma. No HTML o quadro desenhado fica na tela durante a captura e o som
  segue; no Remotion lê-se o quadro do Player antes e depois da captura.
- **Clipe, independente do motor.** O clipe de esboço traz o número do quadro gravado. O contador é recortado
  do quadro exportado e comparado com os quadros-fonte k−2…k+2: o melhor casamento tem de ser o quadro que
  velocidade e congelamento mandam mostrar.
- **Som.** Um `AudioWorklet` grava o que a prévia realmente toca durante 20 s, com a posição de cada bloco na
  linha do tempo. Essa gravação é alinhada ao áudio do MP4 final por correlação cruzada (o deslocamento mede a
  sincronia) e comparada amostra a amostra, depois do ganho de masterização (resíduo), e pela curva de
  loudness momentânea a cada 100 ms.

Perdas aceitas: a prévia rasteriza texto, grade e o clipe a 405 ou 1280 px, e o MP4 passa pelo H.264. Por isso
o SSIM entre prévia e exportação fica entre 0,86 e 0,96 nos quadros de mapa e texto e mais baixo nos quadros do
clipe de esboço, cheio de ruído de alta frequência que a redução trata diferente. O padrão de referência é a
própria escala: quadros de instantes diferentes no corte dão 0,16 a 0,34.

## Resultados por critério de aceite

### 1. Paridade entre prévia e exportação

Rodada final, depois das correções da seção "Defeitos encontrados". "Incoerentes" são amostras em que um
quadro vizinho casou melhor que o próprio.

| Formato | Motor | Parada: SSIM médio (mín) | Incoerentes | Tocando: SSIM médio (mín) | Incoerentes | Clipe certo |
| --- | --- | --- | --- | --- | --- | --- |
| 9:16 | HTML | 0,928 (0,896) | 0 de 37 | 0,929 (0,834) | 1 de 10 | 8 de 8 |
| 16:9 | HTML | 0,892 (0,867) | 0 de 37 | 0,920 (0,805) | 0 de 10 | 8 de 8 |
| 9:16 | Remotion | 0,904 (0,690) | 0 de 37 | 0,902 (0,660) | 0 de 10 | 8 de 8 |
| 16:9 | Remotion | 0,914 (0,798) | 0 de 37 | 0,916 (0,732) | 0 de 10 | 8 de 8 |
| 9:16 | Python (atual) | 0,9965 (0,9944) | 0 de 47 | — | — | — |

| Som (20 s da prévia tocando) | Deslocamento | Resíduo | Loudness momentânea: diferença média (máx) |
| --- | --- | --- | --- |
| HTML 9:16 e 16:9 | 0 ms | −30 dB | −0,01 LU (0,4 LU) |
| Remotion 9:16 | 20 ms | −33,7 dB | 0,02 LU (3,3 LU) |
| Remotion 16:9 | 28 ms | −34,7 dB | −0,02 LU (10,2 LU) |

Leitura:

- **HTML.** Conteúdo, geometria, fontes, cortes, efeitos, câmera e tempos casam: nenhuma amostra parada
  incoerente e o contador do clipe certo em todas. O som tocado pela prévia é o do arquivo, sem deslocamento
  e com a loudness momentânea a menos de 0,4 LU em todos os pontos; o resíduo de −30 dB é a perda do AAC.
  A única amostra incoerente é da prévia tocando: o quadro do clipe ainda não decodificado ficou um quadro
  atrás (a prévia contou 6 a 7 atrasos assim em 20 s). Parada, o quadro do clipe é sempre exato.
- **Remotion.** Depois das mitigações, as imagens casam nos tempos. O som do Player fica 20 a 28 ms atrás do
  quadro mostrado e, nas bordas de palavras e nas rampas da música, a loudness momentânea chega a desviar
  3 a 10 LU, porque o Player aplica o volume por quadro no elemento `<audio>` (o volume medido no Player
  ficou, numa rampa, em 0,135 onde a curva pedia 0,151). A diferença média é de 0,02 LU, mas nos transientes
  a paridade da mixagem do Remotion **não fica demonstrada**: a prévia dele não toca a mesma mistura que o
  arquivo nas rampas e bordas de palavra.
- **Python (atual).** A "prévia" do app atual é outra exportação do mesmo desenho (540×960 a 24 qps), por isso
  casa quase exatamente: o som das duas é o mesmo arquivo pelo mesmo AAC (resíduo nulo, deslocamento 0 ms em
  20 s). A prova de tempos é fraca: o Short é quase estático entre quadros e só 8 das 47 amostras se distinguem
  dos vizinhos (nenhuma incoerente). E essa prévia leva 107,6 s para um Short de 55 s e não toca nem busca:
  não é uma prévia interativa. O motor atual só desenha 9:16 (1080×1920 fixo), por isso não há linha 16:9.

### 2. Nada depende de animação CSS, temporizador ou relógio; fontes e bibliotecas embutidas; sem rede

- **HTML.** Antes da página carregar, um vigia substitui `Date.now`, `performance.now`, `new Date()`,
  `setTimeout`, `setInterval`, `requestAnimationFrame` e `Element.animate` por versões que contam chamadas.
  Em todas as exportações e em todas as abas, a contagem durante a gravação foi **zero**. A página confere a
  cada 600 quadros que `document.getAnimations()` está vazio e, na carga, que nenhum elemento tem
  `transition-duration` maior que zero: zero nos dois. As seis faces de fonte são carregadas por `FontFace`
  de arquivos locais antes do primeiro quadro e conferidas com `document.fonts.check`.
- **HTML, mesmos pixels por qualquer caminho** (`medir/determinismo.mjs`). Os mesmos quadros foram capturados
  sem perda (PNG) em três navegadores novos, em ordem crescente, embaralhada e invertida. No ensaio 16:9, os
  40 quadros saíram idênticos bit a bit. No Short 9:16, 22 de 37 saíram idênticos; nos outros 15, a rodada
  em ordem crescente, em que cada quadro vem logo depois do vizinho, diferiu das outras duas:
  - em 11 quadros do mapa, 33 a 1.303 pixels (no máximo 0,06% do quadro) mudaram 1 ou 2 níveis de 255;
  - em 4 quadros do clipe, 9 pixels mudaram até 217 níveis, na borda do contorno escuro de uma letra da
    legenda (o contorno cobre ou não esses 9 pixels).

  É o Chromium reaproveitando parte da rasterização do quadro anterior. O estado do quadro é o mesmo e as
  diferenças são de borda, menores que a perda do H.264, mas o arquivo pode variar nesses pixels conforme o
  número de abas. `--disable-partial-raster` eliminou a diferença dos quadros do clipe, não a dos quadros do
  mapa. Resultados em `.saida/determinismo-short.json` e `.saida/determinismo-ensaio.json`.
- **Remotion.** A composição usa o mesmo `quadroEm(t)` a partir de `useCurrentFrame()`, sem relógio no desenho;
  as seis faces vêm dos mesmos arquivos locais, com `delayRender`, e as seis aparecem carregadas no Player. O
  vigia não pôde ser instalado no navegador que o próprio Remotion abre, então para ele o critério de relógio
  fica sem demonstração: vale só pelo código da composição, não por medição.
- **Rede.** Toda exportação e medição de paridade rodou em `unshare -rn`, um namespace de rede só com loopback:
  não existe rota para a internet durante a gravação. No HTML, o contexto do navegador ainda bloqueia e
  registra qualquer pedido fora do servidor local; nenhum aconteceu. O Remotion também exportou sem rede
  (sem chave de licença; ver a seção 3).

### 3. Licença e distribuição para um repositório público

| Peça | Licença | Condição para o MyCut |
| --- | --- | --- |
| Motor HTML (código do MyCut) | do repositório | — |
| Chromium headless shell | BSD-3 e licenças de terceiros do Chromium | Baixado pelo Playwright em cada máquina; o MyCut não redistribui |
| `playwright-core` | Apache-2.0 | Permissiva |
| Inter, JetBrains Mono (`@fontsource`) | OFL-1.1 | Podem ser embutidas e redistribuídas com o aviso |
| FFmpeg do sistema (Ubuntu) | GPL (compilado com `--enable-gpl` e libx264) | Usado como programa externo; o MyCut não distribui o binário |
| NVENC | Driver proprietário da NVIDIA no Windows | Só em tempo de execução |
| Remotion (`remotion`, `@remotion/*`) | Remotion License, *source-available* | Ver abaixo |

O Remotion é gratuito para pessoas físicas, empresas com até três funcionários, organizações sem fins
lucrativos e avaliação; empresas maiores precisam de licença paga. Num repositório público, essa condição
passa a quem usar o MyCut: uma empresa maior que rode o MyCut precisaria comprar a licença do Remotion. O
`LICENSE.md` da versão avisa que a licença muda no Remotion 5.0; a mudança não foi avaliada aqui.

Dois achados no código da versão 4.0.536:

- `renderMedia` com `licenseKey: 'free-license'` envia ao fim de cada render um evento de uso aos servidores do
  Remotion (`internalRegisterUsageEvent`, evento `cloud-render`). Sem chave, só emite um aviso no log. A prova
  rodou sem chave.
- O FFmpeg embutido no compositor do Remotion declara GPL e inclui `libfdk_aac`, sem `--enable-nonfree`. O
  FFmpeg trata essa combinação como não redistribuível. O MyCut não redistribuiria esse binário (ele vem do
  npm), mas é um ponto a confirmar com o Remotion se algum dia for empacotado.

### 4. Encode NVENC real no WSL

`medir/nvenc.mjs` codificou os 1.960 quadros 1080p do Short 16:9 exportado com `h264_nvenc` (p5, `-cq 20`)
e com `libx264` (veryfast, CRF 20), e verificou o caminho durante a execução:

| | NVENC | libx264 |
| --- | --- | --- |
| Tempo | 7,49 s (262 qps) | 11,23 s (174 qps) |
| CPU (`-benchmark`) | 12,2 s, quase toda na decodificação da fonte | 59,0 s |
| SSIM contra a fonte | 0,9986 | 0,9948 |
| Uso do codificador da GPU (nvidia-smi, a cada 200 ms) | 42,6% em média, 47% no pico | 0% |
| Bibliotecas mapeadas no processo (`/proc/<pid>/maps`) | `/usr/lib/wsl/lib/libnvidia-encode.so.1`, `/usr/lib/wsl/lib/libcuda.so.1`, `libcuda.so.1.1` do driver em `/usr/lib/wsl/drivers/…`, `libdxcore.so` | só `libx264` |
| Log | `Loaded Nvenc version 13.1`, `Nvenc initialized successfully`, `GPU #0 - < NVIDIA GeForce RTX 5070 Ti >` | — |
| Marca no arquivo | `Lavc60.31.102 h264_nvenc` | `Lavc60.31.102 libx264` |

O NVENC também funcionou dentro do namespace sem rede e nas exportações dos dois motores (o log do Remotion
mostra `Encoder: h264_nvenc, hardware accelerated: true` e o comando com `-c:v h264_nvenc`).

Na exportação completa o codificador não é o gargalo: entre NVENC e x264 a diferença ficou entre −2% e +6%
(seção 5), para um lado ou para o outro conforme o motor e o formato, dentro da variação de carga da máquina,
porque a captura de quadros satura a CPU. O ganho do NVENC é liberar CPU (59 s contra 12 s de processador para o
mesmo encode), o que pesa no vídeo longo e em máquinas com menos núcleos.

O Chromium no WSL não usa a GPU para rasterizar ou compor. Com flags de GPU (ANGLE sobre GL/EGL, rasterização
por GPU, no headless shell e no Chromium completo) a captura caiu de 12,9 para 6,1–6,3 qps e a GPU ficou em
~1%, ou seja, o caminho virou software mais lento. O teto da exportação é a CPU.

### 5. Tempo de render de um Short (9:16) contra o motor atual

| Motor | Vídeo | Quadros e codificação | Total com áudio | Velocidade | Pico de memória (PSS) |
| --- | --- | --- | --- | --- | --- |
| HTML, NVENC | 65,3 s, 9:16 | 122,9 s | 129,1 s | 0,51× | 2,0 GB |
| HTML, x264 | 65,3 s, 9:16 | 120,4 s | 126,5 s | 0,52× | 2,2 GB |
| Remotion, NVENC | 65,3 s, 9:16 | 125,0 s | 132,0 s (bundle em cache: 1,9 s) | 0,49× | 3,1 GB |
| Remotion, x264 | 65,3 s, 9:16 | 124,2 s | 130,8 s | 0,50× | 3,3 GB |
| HTML, NVENC | 65,3 s, 16:9 | 139,3 s | 145,5 s | 0,45× | 1,9 GB |
| HTML, x264 | 65,3 s, 16:9 | 147,6 s | 153,7 s | 0,43× | 2,2 GB |
| Remotion, NVENC | 65,3 s, 16:9 | 134,3 s | 141,5 s | 0,46× | 3,1 GB |
| Remotion, x264 | 65,3 s, 16:9 | 131,2 s | 138,1 s | 0,47× | 3,3 GB |
| **Python atual**, x264 | 55,4 s, 9:16 (Short real) | 102,2 s | 102,8 s | 0,54× | 0,6 GB |
| **Python atual**, prévia 540p | 55,4 s, 9:16 | 106,8 s | 107,6 s | 0,51× | — |

"Velocidade" é segundos de vídeo por segundo de exportação total, a mesma base para os três motores. HTML e
Remotion usaram quatro abas; mais abas não ajudam, porque quatro já saturam as oito CPUs lógicas (300 quadros
1080p de mapa: 2 abas 11,9 qps, 4 abas 13,0 qps, 6 abas 13,0 qps, 8 abas 12,8 qps). A carga da máquina variou
entre as rodadas; diferenças de até ~6% entre linhas estão dentro desse ruído.

No mesmo critério, o motor atual é cerca de 6% mais rápido que o HTML no 9:16 (0,54× contra 0,51×), usando um
núcleo, mas desenha uma composição bem mais simples: sem desfoque, vidro, mola nem câmera, e sem 16:9. Os
motores em navegador entregam esses efeitos em tempo de relógio parecido, usando a máquina inteira. Na
qualidade de codificação os três usam H.264 em 1080p: CRF 20 no x264 (os três motores), CQ 20 no NVENC do
motor HTML e 16 Mbit/s no NVENC do Remotion, que com aceleração por hardware só aceita taxa fixa e recusa
CRF. A diferença visível entre eles é o que cada motor consegue desenhar, não a compressão.

### 6. Ensaio de escala de 25 min (16:9)

Feito no motor escolhido, com o áudio de ensaio Qwen de 26,4 min (gerado localmente em 31 min de GPU) e as
mídias de esboço, sem ElevenLabs. O arquivo fica identificado como teste de três formas: o nome
`ENSAIO-TESTE-25min-16x9.mp4`, o título e o comentário dos metadados ("TESTE: ensaio de escala MYC-11 (Qwen e
esboços), não é entrega") e a marca "ENSAIO DE ESCALA · TESTE" desenhada em todo quadro.

| Medida | Resultado |
| --- | --- |
| Vídeo | 1581,8 s (26 min 22 s), 47.454 quadros 1920×1080 a 30 qps; 28 cenas, 112 trechos visuais, 168 itens, 4.210 palavras |
| Exportação total | 4.001 s (66,7 min), ou 0,40× o tempo real |
| Quadros e codificação (4 abas, NVENC) | 3.837 s (64,0 min), 12,4 qps, 292 ms por quadro em cada aba |
| Mixagem (grafo WebAudio offline, blocos de 60 s) | 37,4 s |
| Masterização (medir, limitador, ganho) | 37,5 s; o pico de −0,8 dBTP pediu o limitador |
| Juntar vídeo e áudio (AAC) | 69,5 s |
| Medição da Q46 no arquivo final | 18,3 s |
| Arquivo | 0,96 GB, 4,9 Mbit/s, H.264 (`h264_nvenc`) e AAC 48 kHz |
| Pico de memória na exportação (PSS) | 3,9 GB no momento de pico: Chromium 3,6 GB (4 abas e o áudio decodificado) e Node 0,3 GB. O FFmpeg chegou a 0,3 GB em outro momento, durante a codificação |
| Relógio, animações, rede | 0 chamadas, 0 animações, 0 pedidos externos; gravação em namespace sem rede |

Prévia do vídeo longo (1280×720, Chromium sem janela, `ensaio/previa.mjs`):

| Medida | Resultado |
| --- | --- |
| Carga com o áudio decodificado | 8,0 s; pico de memória de 2,6 GB (26 min de narração e música em float) |
| Busca até a tela pintada, 60 posições aleatórias no vídeo inteiro | mediana 33 ms, p95 92 ms, máximo 100 ms (inclui dois quadros de pintura, ~33 ms) |
| Busca até o quadro aplicado, 120 amostras da paridade | mediana 2 ms, p95 13 ms, máximo 16 ms |
| Tocar | primeiro quadro no ciclo de pintura seguinte; o som entra 100 ms depois (margem de agendamento) |
| Reprodução de 12 s no início, no meio e no fim | intervalo mediano de 16,7 ms nos três; p95 de 50, 50 e 16,8 ms; 12, 7 e 4 intervalos acima de 50 ms; máximo 67, 67 e 100 ms; quadro do clipe atrasado 0, 0 e 13 vezes |

No início e no meio, 5% dos intervalos entre quadros desenhados chegaram a 50 ms (três ciclos de pintura): a
reprodução é fluida na maior parte, com engasgos curtos nos trechos de mapa, os mais caros. Nas medições de
paridade aparece um intervalo máximo de 283 ms, mas ali é a própria medição que segura o quadro na tela durante
a captura; não é engasgo da prévia.

Paridade no vídeo longo: 120 amostras paradas espalhadas pelo vídeo, SSIM médio 0,901 (mínimo 0,832), 98
distinguíveis dos vizinhos e nenhuma incoerente; prévia tocando com uma incoerência (o quadro do clipe um quadro
atrás); clipe certo em 224 de 224 amostras; som sem deslocamento, resíduo de −32,2 dB e loudness momentânea a no
máximo 0,2 LU. Os 40 quadros da prova de determinismo saíram idênticos, bit a bit, nas três ordens.

Na mesma base (tempo total), a velocidade cai de 0,45–0,52× no Short para 0,40× no vídeo longo, porque o vídeo
longo tem mais tempo de mapa (o trecho mais caro) e porque mixagem, masterização e mux crescem com a duração.

### 7. Mixagem do arquivo final pela Q46

A masterização mede a mixagem, aplica um ganho único (modo linear) e só usa um limitador de pico se o ganho
levasse o pico acima de −1,5 dBTP antes do AAC. Nos Shorts não foi preciso; no ensaio, o pico de −0,8 dBTP o
acionou (com compensação de latência, para não atrasar o som). A conferência é feita no MP4 final
decodificado, por `ebur128` com pico verdadeiro:

| Arquivo | LUFS integrado | Pico verdadeiro | Taxa | Q46 |
| --- | --- | --- | --- | --- |
| Short HTML 9:16 e 16:9 (NVENC e x264) | −14,0 | −1,2 dBTP | 48 kHz | aprovado |
| Short Remotion 9:16 e 16:9 (NVENC e x264) | −14,0 | −1,6 dBTP | 48 kHz | aprovado |
| Ensaio 25 min (HTML) | −14,1 | −1,5 dBTP | 48 kHz | aprovado (com limitador) |
| Short real no motor atual (referência) | −17,0 | −1,5 dBTP | 48 kHz, mono | não aprovado (anterior à Q46) |

Dois pontos ficam abertos para o MYC-15:

- **O limitador é processamento dinâmico.** A Q46 pede medir e aplicar um ganho linear, justamente para não
  haver processamento dinâmico. No ensaio, só o ganho linear levaria o pico acima do teto, e o arquivo passou
  com o limitador; o efeito é pequeno (age só nos picos), mas é um desvio da decisão. As saídas são deixar mais
  folga de pico na mixagem (voz normalizada com teto mais baixo) para o ganho linear bastar, ou o autor aceitar
  o limitador como exceção.
- **A prévia toca a mistura antes da masterização.** O ganho de masterização (−0,5 dB nos Shorts e no ensaio) e o
  limitador só existem na exportação; a paridade de som foi medida descontando esse ganho. O glossário define a
  prévia como a mesma mixagem da exportação, então o editor precisa aplicar na prévia o ganho da última medição
  e o mesmo limitador.

Voz × música na fala (`medir/partes.mjs`): a narração e a música são renderizadas separadas pelo mesmo grafo
da exportação e comparadas pela loudness momentânea só nos instantes com fala, nos primeiros 5 minutos do
vídeo (o Short inteiro). A música ficou 19,9 LU abaixo da voz no Short e 20,0 LU nos 5 primeiros minutos do
ensaio: dentro da faixa de 15 a 20 LU da Q46, mas no limite. O ganho de partida
da música na fala (−18 dB) deve subir para algo como −16 dB quando virar padrão de template. Inteligibilidade,
ducking e emendas ainda pedem escuta humana; os números não provam isso.

### 8. Motor escolhido, evidência e limitações no hardware alvo

O HTML determinístico, pelos motivos da [ADR 0019](adr/0019-motor-de-composicao-html-deterministico.md):
tempo equivalente ao Remotion, paridade medida sem desvios fora do controle do MyCut e licenças permissivas.

Limitações no hardware alvo:

- A exportação é limitada pela CPU: cerca de 12 a 13 quadros 1080p por segundo com efeitos, ou 0,40–0,52× o
  tempo real no total. O Chromium não usa a GPU no WSL; o NVENC só alivia a codificação.
- Na prévia tocando, o quadro do clipe pode ficar um quadro atrás quando ainda não foi decodificado; a
  pré-carga de 20 quadros reduz, não elimina. Parada, é exato.
- A prévia foi medida num Chromium sem janela, com áudio sem dispositivo de saída. A resposta e a sincronia
  num navegador com janela e placa de som precisam ser conferidas no editor (MYC-15).
- O clipe entra como sequência de quadros JPEG preparada antes. Isso ocupa disco e tempo de preparação
  proporcionais à duração das mídias.
- O desenho final não é bit a bit idêntico por qualquer ordem em todos os quadros: até 0,06% dos pixels do mapa
  podem variar 1 ou 2 níveis, e bordas de letras com contorno podem cobrir ou não alguns pixels (seção 2). O modo de quadros controlados do Chromium (`HeadlessExperimental.beginFrame`)
  fica como caminho a avaliar no MYC-15.
- No vídeo longo, o áudio decodificado inteiro custa cerca de 1,2 GB na página da prévia e na aba que mixa; a
  prévia de vídeos mais longos vai precisar decodificar o áudio por trechos.
- Os itens do mapa fora do enquadramento da câmera saem do desenho (também em função só de t). No ensaio isso
  mudou pouco a velocidade (11,1 para 11,6 qps no fim do vídeo); o custo é dominado pelos efeitos no quadro.

### 9. Nenhuma geração paga

A narração do ensaio e do Short de teste é Qwen local; imagens, clipe e música são esboços gerados pelo
FFmpeg. A referência Python reusou uma narração ElevenLabs que já existia no disco, sem nova chamada. Nenhuma
chamada a ElevenLabs ou a provedor de imagem ou vídeo foi feita.

## Defeitos encontrados pela prova

A comparação quadro a quadro encontrou problemas que o código compartilhado escondia:

| Defeito | Motor | Como apareceu | Correção ou mitigação |
| --- | --- | --- | --- |
| Vidro fosco amostra o fundo errado na prévia | HTML e Remotion | Na prévia reduzida o cartão de vidro mostrava amarelo onde o fundo era azul; a exportação, em escala 1, estava certa | A prévia reduz com `zoom`, não com `transform: scale()`; no Remotion, o Player fica em escala 1 dentro de um contêiner com `zoom` |
| Quadro do clipe atrasado ou travado | HTML | Com `<video>`, a captura mostrava o quadro anterior, e buscar um instante dentro do mesmo quadro nunca avisava (`requestVideoFrameCallback`), travando a exportação | O clipe passou a ser uma sequência de quadros JPEG, decodificados com `img.decode()` |
| Voz 3 dB mais alta na prévia | Remotion | Narração mono: o Chrome copia o canal inteiro para os dois lados e o FFmpeg do Remotion (`-ac 2`) atenua 3 dB. Resíduo de −7,7 dB e diferença média de −2,6 LU | Narração preparada em estéreo |
| Cor do clipe diferente na exportação | Remotion | Vídeo sem marcação de cor: amarelo (255, 238, 1) no MP4 contra (255, 255, 2) no Player | Clipe marcado como BT.709 na preparação: (251, 251, 0) |
| Dois laços de desenho na prévia | HTML | Pausar e tocar de novo antes do próximo quadro deixava o laço antigo vivo: intervalo mediano de 0 ms e 153 atrasos do clipe no ensaio | Cada `tocar()` tem uma geração; um laço de geração antiga para sozinho |
| Som 2 ms atrasado no arquivo | Medição de som | Só quando o limitador entrou (ensaio): a correlação achou 95 amostras de deslocamento | `alimiter` com `latency=true`; o ensaio foi remasterizado e voltou a 0 ms |

## Como reproduzir

Instruções em [`qualificacao/render/README.md`](../qualificacao/render/README.md). Os testes do núcleo puro
(`quadroEm`, envelope da música, montagem da cena) rodam com `pnpm test` nessa pasta.
