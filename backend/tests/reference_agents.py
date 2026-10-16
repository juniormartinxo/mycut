"""The reference prompt's Short livre ("Da Ideia ao Filme com IA", MYC-2) as the agents would answer it.

Plain data shared by the backend's end-to-end test and the browser's simulated runner: the writer follows the prompt's
script literally, the director cuts every 1,5 to 3 s of speech with full-screen B-rolls, a split screen and the
character sheet revealed line by line, and asks the Arte for the two bases first."""
from pathlib import Path

PROMPT = (Path(__file__).parent / 'fixtures' / 'prompt-de-referencia.md').read_text()

ACCENT, BACKGROUND, TEXT = '#f2b544', '#0b2a33', '#e6f1f2'  # The flower's amber against the ship's teal.

# The passages of the prompt's "Roteiro segundo a segundo", in order: (time, narration, text on screen, visual).
PASSAGES = [
    ('0–3 s', 'Seus vídeos de IA mudam de rosto a cada cena? O problema não é a ferramenta.', 'O PROBLEMA NÃO É A IA',
     'Mesmo personagem com 3 rostos diferentes (B-roll 1).'),
    ('3–8 s', 'É que você pula a pré-produção. Olha: tudo começa com uma frase simples.', '1 FRASE → 1 FILME',
     'Tela do chat; a frase do astronauta sendo digitada.'),
    ('8–16 s', 'Primeiro, o tom: gênero, paleta e luz. Isso vira a regra de todas as cenas.', 'ETAPA 1: TOM',
     'Paleta teal e âmbar sobre o plano geral da nave (B-roll 3).'),
    ('16–28 s', 'Depois, a ficha do personagem com números exatos: idade, altura, peso, cicatriz. Número a IA não inventa.',
     'ETAPA 2: FICHA COM NÚMEROS', 'Ficha da astronauta linha a linha; corta para o retrato em estúdio (B-roll 2).'),
    ('28–38 s', 'Terceiro, o cenário sozinho, sem ninguém. Ele vira a referência fixa do mundo.', 'ETAPA 3: CENÁRIO VAZIO',
     'Corredor vazio da nave (B-roll 3) com 24 mm no canto.'),
    ('38–50 s', 'Por último, a decupagem: plano, movimento de câmera e física. Você anexa ficha e cenário em cada cena e o '
     'rosto não muda mais.', 'ETAPA 4: CENA = FICHA + CENÁRIO + PROMPT',
     'Tela dividida: retrato + corredor, que se fundem no plano em movimento (B-roll 4).'),
    ('50–58 s', 'Resultado: isso. O prompt completo está no comentário fixado.', 'PROMPT NO COMENTÁRIO FIXADO',
     'Payoff: a flor nas luvas (B-roll 5) e a porta do módulo fechando (B-roll 6).'),
]
PAUSE = {'after': 'Resultado: isso.', 'seconds': .8}  # "Resultado: isso." (pausa) "O prompt completo…"
TITLES = ['Por que seu vídeo de IA muda o rosto do personagem', 'Da ideia ao filme com IA em 4 etapas',
          'O segredo dos filmes de IA consistentes']
HASHTAGS = ['#Shorts', '#IA', '#InteligenciaArtificial', '#Midjourney', '#Kling', '#Runway', '#FilmeComIA',
            '#EngenhariaDePrompt', '#CriadorDeConteudo']
PINNED = ('Prompt-mestre: você é um diretor de cinema e transforma a minha história num documento de pré-produção '
          'completo. Junto de cada prompt em inglês, traga a tradução em português')


def script():
    description = next(line[2:] for line in PROMPT.splitlines() if line.startswith('> '))
    scenes = [{'timing': timing, 'narration': narration, 'screen_text': [screen], 'visual': visual, 'pauses': []}
              for timing, narration, screen, visual in PASSAGES]
    scenes[-1]['pauses'] = [dict(PAUSE)]
    return {'mode': 'script', 'titles': TITLES, 'description': description, 'tags': 'IA, filme com IA, Midjourney, Kling',
            'hashtags': HASHTAGS, 'pinned_comment': PINNED, 'claims': [], 'scenes': scenes}


BIBLE = {'tone': 'Ficção científica intimista com tensão de sobrevivência: azul-petróleo frio e cinza metálico na nave, '
                 'contra o âmbar quente da flor.',
         'sheets': [{'kind': 'character', 'name': 'Comandante Ira Vale',
                     'description': '38 anos, 172 cm, 64 kg, olhos cinza-esverdeados, cabelo preto raspado nas laterais, '
                                    'cicatriz diagonal de 3 cm na sobrancelha esquerda, traje EVA branco-gelo.'},
                    {'kind': 'setting', 'name': 'Nave abandonada Halcyon',
                     'description': 'Corredor cilíndrico de alumínio escovado, cabos flutuando, luz de emergência vermelha, '
                                    'brilho âmbar vazando da escotilha.'}]}


def image(key, title, prompt, references=(), base=False, aspect='9:16'):
    return {'key': key, 'base': base, 'title': title, 'aspect': aspect, 'references': list(references), 'prompt': prompt}


# The bases first: Ira's character sheet and the empty corridor; every other image attaches the bases it cites.
IMAGES = [
    image('ira', 'Ficha da Comandante Ira Vale', 'Studio character reference sheet, 85mm lens, Commander Ira Vale, '
          '38-year-old woman, 3 cm diagonal scar across left eyebrow --ar 3:2', base=True, aspect='3:2'),
    image('corredor', 'Corredor vazio da Halcyon', 'Wide establishing shot, 24mm lens, interior of an abandoned derelict '
          'spaceship corridor, empty, no people --ar 9:16', base=True),
    image('rostos-still', 'Três rostos da astronauta', 'Close-up portrait, 50mm lens, a female astronaut in a white '
          'spacesuit, helmet off, cinematic lighting'),
    image('ira-corredor', 'Ira avança pelo corredor', 'Medium shot, 50mm lens, Commander Ira Vale pulls herself along '
          'the wall rail in zero gravity', ['ira', 'corredor']),
    image('flor-still', 'A flor nas luvas', 'Macro close-up, 100mm lens, gloved hands cupping a glowing amber alien '
          'flower', ['ira']),
    image('porta-still', 'A porta do módulo', 'Wide shot, 35mm lens, the escape pod hatch slides shut at the end of a dark '
          'corridor', ['ira', 'corredor']),
]


def broll(key, title, tool, references, seconds, prompt):
    return {'key': key, 'title': title, 'tool': tool, 'references': references, 'seconds': seconds, 'prompt': prompt}


# The prompt's six B-rolls, in its table's order.
BROLLS = [
    broll('rostos', 'Gancho: o mesmo personagem com 3 rostos', 'Midjourney/Flux, 3 gerações', [], 3,
          'Close-up portrait, 50mm lens, a female astronaut in a white spacesuit inside a spaceship, helmet off, looking '
          'at camera, cinematic lighting --ar 9:16'),
    broll('retrato', 'Etapa 2: retrato de estúdio da Ira', 'Midjourney/Flux', [], 4,
          'Studio character reference sheet, 85mm lens, Commander Ira Vale --ar 3:2'),
    broll('corredor-vivo', 'Corredor vivo', 'Kling/Runway', ['corredor'], 5,
          'Wide shot, 24mm lens, slow dolly forward down an abandoned spaceship corridor, no people, photorealistic'),
    broll('ira-avanca', 'Ira avança pelo corredor', 'Kling/Runway', ['ira', 'corredor'], 5,
          'Medium shot, 50mm lens, tracking shot moving backward in front of the subject, Commander Ira Vale pulls '
          'herself forward hand over hand along a wall rail'),
    broll('flor', 'A flor nas luvas', 'Kling/Luma', ['ira'], 4,
          'Macro close-up, 100mm lens, static camera, gloved hands gently cupping a small alien flower that glows warm amber'),
    broll('porta', 'A porta do módulo fecha', 'Kling/Runway', ['ira', 'corredor'], 4,
          'Wide shot, 35mm lens, locked-off static camera, the heavy pod hatch slides shut and the frame falls to darkness'),
]


def text(kind, value, size, color=None, align='center', reveal='none'):
    return {'type': kind, 'text': value, 'font_size': size, 'color': color, 'align': align, 'reveal': reveal,
            'image_id': None, 'art': None, 'motion': 'none', 'flow': None}


def picture(art, motion='zoom_in'):
    return {'type': 'image', 'text': '', 'font_size': 16, 'color': None, 'align': 'center', 'reveal': 'none',
            'image_id': None, 'art': art, 'motion': motion, 'flow': None}


def gradient():
    return {'kind': 'gradient', 'color': BACKGROUND, 'color_to': '#05080a', 'angle': 180, 'image_id': None, 'art': None,
            'broll': None, 'motion': 'none', 'dim': 0}


def full_screen(art, broll=None, motion='zoom_in', dim=30):
    """A B-roll or generated image filling the whole frame, behind the blocks."""
    return {'kind': 'image', 'color': None, 'color_to': None, 'angle': 0, 'image_id': None, 'art': art, 'broll': broll,
            'motion': motion, 'dim': dim}


def plano(blocks, anchor=None, background=None, transition='cut'):
    return {'anchor': anchor, 'transition': transition, 'brand': False, 'background': background or gradient(),
            'blocks': [{'height': height, 'object': value} for height, value in blocks]}


def caption(screen):
    """The screen text over the upper part, above the captions and out of the YouTube buttons' strip."""
    return [(22, text('title', screen, 64, ACCENT)), (78, None)]


def direction():
    on_screen = [screen for _, _, screen, _ in PASSAGES]
    scenes = [
        [plano(caption(on_screen[0]), background=full_screen('rostos-still', 'rostos')),
         plano(caption(on_screen[0]), 'de rosto a cada cena?', full_screen('rostos-still', 'rostos', 'pan_left')),
         plano([(100, text('title', on_screen[0], 96, ACCENT))], 'problema não é a ferramenta.')],
        [plano([(30, text('title', on_screen[1], 80, ACCENT)), (70, None)]),
         # The chat: the astronaut's sentence typed on screen.
         plano([(30, text('title', on_screen[1], 64, ACCENT)),
                (70, text('paragraph', 'Uma astronauta encontra uma flor alienígena numa nave abandonada enquanto o ar acaba.',
                          48, TEXT, 'left', 'typing'))], 'tudo começa com uma frase')],
        [plano(caption(on_screen[2])[:1] + [(78, text('paragraph', 'Azul-petróleo\nCinza metálico\nÂmbar da flor', 56, ACCENT,
                                                    reveal='lines'))],
               background=full_screen('corredor', 'corredor-vivo', dim=50)),
         plano(caption(on_screen[2]), 'Isso vira a regra', full_screen('corredor', 'corredor-vivo', 'pan_right'))],
        [plano([(22, text('title', on_screen[3], 60, ACCENT)), (78, text('paragraph', 'Etapa 2/4', 40, TEXT))]),
         # The character sheet, line by line.
         plano([(22, text('title', on_screen[3], 60, ACCENT)),
                (78, text('paragraph', 'Idade: 38 anos\nAltura: 172 cm\nPeso: 64 kg\nCicatriz: 3 cm', 64, TEXT, 'left',
                          'lines'))], 'com números exatos:'),
         plano([(50, picture('ira')), (50, text('paragraph', 'Olhos cinza-esverdeados\nCicatriz de 3 cm', 52, ACCENT,
                                                  reveal='lines'))], 'altura, peso, cicatriz.'),
         plano(caption(on_screen[3]), 'Número a IA não inventa.', full_screen('ira', 'retrato'))],
        [plano(caption(on_screen[4]), background=full_screen('corredor', 'corredor-vivo')),
         # The lens on the helmet's HUD, in the corner.
         plano([(22, text('title', '24 mm', 56, ACCENT, 'left')), (78, None)], 'Ele vira a referência',
               full_screen('corredor', 'corredor-vivo', 'zoom_out'))],
        [plano([(100, text('title', on_screen[5], 80, ACCENT))]),
         # An English prompt with its translation side by side.
         plano([(50, text('paragraph', 'static camera\n85mm lens', 56, TEXT, reveal='lines')),
                (50, text('paragraph', 'câmera parada\nlente 85 mm', 56, ACCENT, reveal='lines'))],
               'plano, movimento de câmera e física.'),
         # Split screen: portrait and corridor, then the two fuse into the moving shot.
         plano([(50, picture('ira', 'none')), (50, picture('corredor', 'none'))], 'Você anexa ficha e cenário'),
         plano([(100, None)], 'em cada cena e o rosto', full_screen('ira-corredor', 'ira-avanca', 'pan_left', 0), 'fade')],
        [plano([(100, None)], background=full_screen('flor-still', 'flor', dim=0)),
         plano(caption(on_screen[6]), 'O prompt completo', full_screen('porta-still', 'porta', 'zoom_out'))],
    ]
    return {'accent': ACCENT, 'style': {'background': BACKGROUND, 'text_color': TEXT, 'font': 'Roboto'},
            'captions': {'words': 3, 'position': 'bottom', 'font_size': 72,
                         'keywords': ['ficha', 'cenário', 'números', 'tom', 'decupagem']},
            'loop': True, 'bible': BIBLE, 'images': [dict(item) for item in IMAGES],
            'brolls': [dict(item) for item in BROLLS],
            'scenes': [{'title': screen[:100], 'shots': shots} for screen, shots in zip(on_screen, scenes)]}


APPROVED = {'approved': True, 'issues': []}
