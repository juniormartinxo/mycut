# Short: Da Ideia ao Filme com IA

## Conceito

Um Short vertical de 55 a 60 segundos que mostra como transformar uma ideia contada "para um amigo" em um filme de IA consistente, em 4 etapas: tom, personagem, cenário e decupagem.

A sacada do vídeo é ser meta: o próprio Short é construído ao vivo. O espectador vê a frase do astronauta virar uma ficha, a ficha virar uma imagem e a imagem virar a cena final. O payoff no fim é o mini-filme pronto.

| Item | Definição |
| --- | --- |
| Formato | 9:16, 1080×1920, 24 fps |
| Duração | 55–60 s (abaixo do limite de 3 min, mas curto para reter) |
| Voz | Narração em off, ritmo rápido, tom de bastidor |
| Visual | Gravação de tela + B-rolls gerados por IA em tela cheia |
| História-exemplo | Astronauta, flor alienígena, nave abandonada, ar acabando |
| Promessa do gancho | "Seus vídeos de IA mudam de rosto a cada cena? O problema não é a ferramenta." |

**Gancho alternativo** (teste A/B): abrir direto no plano final da flor brilhando e dizer "Isso aqui começou com uma frase de 20 palavras."

## Roteiro segundo a segundo

Seis blocos, um por etapa do método. Cada bloco termina com um corte seco para manter a retenção; o texto na tela repete a ideia-chave para quem assiste sem som.

| Tempo | Narração (off) | Texto na tela | Visual |
| --- | --- | --- | --- |
| 0–3 s | "Seus vídeos de IA mudam de rosto a cada cena? O problema não é a ferramenta." | O PROBLEMA NÃO É A IA | Montagem rápida: mesmo personagem com 3 rostos diferentes (B-roll 1), tremendo de leve |
| 3–8 s | "É que você pula a pré-produção. Olha: tudo começa com uma frase simples." | 1 FRASE → 1 FILME | Tela do chat; a frase do astronauta sendo digitada |
| 8–16 s | "Primeiro, o tom: gênero, paleta e luz. Isso vira a regra de todas as cenas." | ETAPA 1: TOM | Paleta de cores animada (teal e âmbar) sobre o plano geral da nave (B-roll 3) |
| 16–28 s | "Depois, a ficha do personagem com números exatos: idade, altura, peso, cicatriz. Número a IA não inventa." | ETAPA 2: FICHA COM NÚMEROS | Ficha da astronauta aparecendo linha a linha; corta para o retrato em estúdio (B-roll 2) |
| 28–38 s | "Terceiro, o cenário sozinho, sem ninguém. Ele vira a referência fixa do mundo." | ETAPA 3: CENÁRIO VAZIO | Corredor vazio da nave (B-roll 3) com lente sugerida escrita no canto: 24 mm |
| 38–50 s | "Por último, a decupagem: plano, movimento de câmera e física. Você anexa ficha e cenário em cada cena e o rosto não muda mais." | ETAPA 4: CENA = FICHA + CENÁRIO + PROMPT | Tela dividida: retrato + corredor → se fundem no plano em movimento (B-roll 4) |
| 50–58 s | "Resultado: isso." (pausa) "O prompt completo está no comentário fixado." | PROMPT NO COMENTÁRIO FIXADO | Payoff: close da flor brilhando nas luvas (B-roll 5) e porta do módulo fechando (B-roll 6) |

**Loop:** o último quadro (porta fechando, tela escura) casa com o primeiro corte rápido do gancho, para o Short reiniciar sem emenda visível.

## Material de demonstração

Estas são as fichas que aparecem na tela nas etapas 1 a 3. Gere primeiro as imagens-base daqui; elas são as referências anexadas em todos os B-rolls.

### Tom

Ficção científica intimista com tensão de sobrevivência. Paleta: azul-petróleo frio e cinza metálico na nave, contra o âmbar quente da flor. Luz: luzes de emergência piscando, lanterna do capacete como luz principal, flor como luz prática. Emoção: solidão que vira esperança.

### Personagem: COMANDANTE IRA VALE

| Atributo | Valor |
| --- | --- |
| Idade | 38 anos |
| Altura / peso | 172 cm / 64 kg |
| Rosto | Maçãs do rosto altas, mandíbula estreita, nariz reto e fino |
| Olhos | Cinza-esverdeados |
| Cabelo | Preto, raspado nas laterais, curto em cima |
| Marca fixa | Cicatriz diagonal de 3 cm na sobrancelha esquerda |
| Traje | EVA branco-gelo, faixa laranja no ombro direito, patch "VALE" no peito |

- **Versão A (limpa):** traje imaculado, rosto descansado, viseira transparente.
- **Versão B (crítica):** traje com fuligem nos joelhos e luvas, rosto suado, lábios ressecados, condensação na borda da viseira, indicador de O₂ piscando vermelho no pulso.

```
Studio character reference sheet, 85mm lens, neutral mid-gray seamless backdrop, soft even key light, full body front view and close-up portrait side by side. Commander Ira Vale, 38-year-old woman, 172 cm tall, 64 kg, lean athletic build, high cheekbones, narrow jaw, straight thin nose, grey-green eyes, short black hair shaved on the sides, 3 cm diagonal scar across left eyebrow. Wearing an ice-white EVA spacesuit with an orange stripe on the right shoulder and a chest name patch, helmet held under arm. Photorealistic, sharp detail, consistent proportions, no text, no background props --ar 3:2
```

### Cenário: NAVE ABANDONADA "HALCYON"

Corredor cilíndrico de painéis de alumínio escovado, com cabos soltos flutuando em gravidade zero e poeira suspensa. Painéis riscados, ferrugem nas juntas, uma luz de emergência vermelha pulsando a cada 2 s. Ao fundo, uma escotilha entreaberta com um brilho âmbar vazando. Lentes: 24 mm para planos gerais, 50 mm para meio-primeiro plano, 100 mm macro para a flor.

```
Wide establishing shot, 24mm lens, interior of an abandoned derelict spaceship corridor, cylindrical brushed aluminum panels, scratched and corroded seams, loose cables floating in zero gravity, dust particles suspended in the air, a single red emergency light pulsing, cold teal ambient light, faint warm amber glow leaking from a half-open hatch at the far end, volumetric haze, empty, no people, cinematic, photorealistic --ar 9:16
```

## Prompts dos B-rolls

Seis clipes de 3 a 5 s em 9:16. Os prompts ficam em inglês porque Midjourney, Flux, Kling, Runway e Luma seguem instruções em inglês com mais precisão; o público brasileiro vê a tradução na legenda. Os 4 a 6 são o "mini-filme" do payoff e devem usar como referência o retrato da Ira e o corredor gerados antes.

| # | Uso no Short | Plano / câmera | Referências | Ferramenta |
| --- | --- | --- | --- | --- |
| 1 | Gancho (o erro) | Close, câmera fixa | Nenhuma, de propósito | Midjourney/Flux, 3 gerações |
| 2 | Etapa 2 | Retrato de estúdio | — | Midjourney/Flux |
| 3 | Etapas 1 e 3 | Plano geral, dolly lento | Corredor | Kling/Runway |
| 4 | Etapa 4 | Meio-primeiro plano, tracking | Ira B + corredor | Kling/Runway |
| 5 | Payoff | Macro, câmera fixa | Ira B | Kling/Luma |
| 6 | Payoff / loop | Plano geral, sem movimento | Ira B + corredor | Kling/Runway |

**B-roll 1 — o erro (gere 3 vezes sem referência, para os rostos variarem):**

```
Close-up portrait, 50mm lens, a female astronaut in a white spacesuit inside a spaceship, helmet off, looking at camera, cinematic lighting --ar 9:16
```

**B-roll 3 — corredor vivo:**

```
Wide shot, 24mm lens, slow dolly forward down an abandoned spaceship corridor, loose cables drifting slowly in zero gravity, dust particles floating and catching the light, red emergency light pulsing every two seconds, amber glow flickering from a half-open hatch at the end, cold teal ambient light, no people, photorealistic, cinematic
```

**B-roll 4 — Ira avança pelo corredor:**

```
Medium shot, 50mm lens, tracking shot moving backward in front of the subject. Commander Ira Vale, woman with grey-green eyes and a scar over her left eyebrow, wearing a soot-stained white EVA suit with an orange shoulder stripe, helmet visor up, sweat on her face, pulls herself forward hand over hand along a wall rail in zero gravity, her body drifting slightly with each pull, floating cables pushed aside by her shoulder, red emergency light pulsing across her face, dust swirling in her wake, photorealistic, cinematic
```

**B-roll 5 — a flor (câmera parada):**

```
Macro close-up, 100mm lens, static camera, no camera movement. Gloved hands in a soot-stained white spacesuit gently cupping a small alien flower with translucent petals that glow warm amber from within, the petals slowly opening and closing like breathing, tiny luminous spores drifting upward and off the petals, the amber glow lighting the fingers of the gloves, shallow depth of field, dark teal background, photorealistic
```

**B-roll 6 — a porta fecha (final e loop):**

```
Wide shot, 35mm lens, locked-off static camera, no camera movement. At the end of a dark spaceship corridor, Commander Ira Vale in a soot-stained white EVA suit drifts into a small escape pod holding a glowing amber flower against her chest, the heavy pod hatch slides shut from left to right with a slight shudder, the amber glow is cut off and the frame falls to near darkness, only a red emergency light pulsing, dust settling, photorealistic, cinematic
```

Dica de consistência: no Kling e no Runway, use o retrato da Ira como imagem de referência do personagem e o corredor como primeiro quadro (ou referência de cena). No Midjourney, use `--cref` com o retrato e `--sref` com o corredor.

## Recursos visuais por trecho

O grosso do Short são imagens suas: B-rolls e gravação de tela. Os recursos de banco entram só como acabamento.

| Tempo | Recurso principal | Acabamento | Onde pegar |
| --- | --- | --- | --- |
| 0–3 s | Tela dividida com os 3 rostos diferentes (B-roll 1) | Efeito de glitch no corte entre rostos | CapCut (efeitos) |
| 3–8 s | Gravação de tela do chat com a frase sendo digitada | Zoom suave e cursor destacado | OBS ou gravador do CapCut |
| 8–16 s | B-roll 3 com a paleta teal e âmbar animada | Overlay de poeira e partículas | Mixkit, Pexels |
| 16–28 s | Ficha aparecendo linha a linha, depois B-roll 2 | Moldura de ficha técnica, números em âmbar, barra "Etapa 2/4" | Canva |
| 28–38 s | B-roll 3 (corredor vazio) | HUD de capacete com "24 mm" no canto; corte de 1 s de estrelas reais | Pixabay (HUD), NASA (estrelas) |
| 38–50 s | Retrato + corredor fundindo no B-roll 4 | Prompt em inglês com tradução sobreposta | CapCut ou Canva |
| 50–58 s | B-rolls 5 e 6 em tela cheia | Granulação de filme e vazamento de luz âmbar | Mixkit, Pexels |

**Fontes**

- [Mixkit](https://mixkit.co): vídeos e overlays grátis (partículas, luz, poeira).
- [Pexels](https://www.pexels.com) e [Pixabay](https://pixabay.com): fotos e vídeos grátis, incluindo elementos de HUD e texturas.
- [NASA Image and Video Library](https://images.nasa.gov): imagens reais do espaço, em geral de uso livre; não use o logo da NASA como se fosse patrocínio.
- [ESA](https://www.esa.int/ESA_Multimedia/Images): muitas imagens livres, mas com crédito obrigatório na descrição.
- Bibliotecas do CapCut e do Canva: efeitos, molduras e elementos gráficos já dentro do editor.

Não use cenas de filmes, personagens famosos, imagens do Google ou vídeos de IA de outros criadores. Mesmo nos sites gratuitos, confira a licença de cada arquivo antes de baixar.

## Edição e publicação

O B-roll 2 usa o prompt da ficha da Ira, na seção anterior.

**Edição**

- Legendas grandes e centralizadas, 2 a 4 palavras por vez, destaque em âmbar nas palavras-chave (números, "ficha", "cenário").
- Corte a cada 1,5 a 3 s; nunca deixe a gravação de tela parada mais de 2 s sem zoom ou destaque.
- Quando um prompt em inglês aparecer na tela, sobreponha a tradução resumida em português, com as palavras destacadas lado a lado (ex.: "static camera" → "câmera parada", "85mm lens" → "lente 85 mm"). Assim o espectador aprende os termos que precisa usar.
- Narração com sotaque e expressões naturais do Brasil ("olha", "sacou?"); evite termos técnicos em inglês falados sem explicar.
- Trilha: ambiente sci-fi grave, com um "hit" no corte para o payoff (50 s). Som da porta fechando no fim.
- Mantenha texto e rostos fora dos 15% inferiores e da faixa direita, onde ficam os botões do YouTube.

**Título** (opções)

1. Por que seu vídeo de IA muda o rosto do personagem
2. Da ideia ao filme com IA em 4 etapas
3. O segredo dos filmes de IA consistentes

**Descrição**

> O erro número 1 em vídeo com IA é pular a pré-produção. Neste Short eu transformo uma frase em um mini-filme usando tom, ficha de personagem com números exatos, cenário de referência e decupagem cena a cena. Ferramentas: Midjourney, Flux, Kling, Runway e Luma. Os prompts finais ficam em inglês porque as ferramentas entendem melhor, mas o método é todo em português. O prompt completo está no comentário fixado.

**Hashtags:** #Shorts #IA #InteligenciaArtificial #Midjourney #Kling #Runway #FilmeComIA #EngenhariaDePrompt #CriadorDeConteudo

**Comentário fixado:** cole o prompt-mestre em português (o template de diretor de cinema que gera o documento completo), para o espectador reutilizar com a própria história. Acrescente no fim do template a linha "Junto de cada prompt em inglês, traga a tradução em português", para quem não domina o idioma acompanhar o que está pedindo à IA.
