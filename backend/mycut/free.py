"""Short livre (ADR 0005): the prompt is the specification.

The writer reads the prompt first and lists the external factual claims; research runs only for those. The
director composes every scene in planos without the 20/60/20 skeleton, and the conference checks facts and
fidelity to the prompt. Contracts are broad, corrections bounded, and paid work degrades instead of failing."""
import math
from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit
from pydantic import Field, StringConstraints
from . import flow, store, visuals, google_fonts
from . import art as artwork, materials
from .art import ArtKey, ArtRequest, Bible
from .materials import Broll
from .block_render import inspect, text_layout
from .flow import FlowSpec
from .models import Scene, ProjectInput, CaptionStyle, Pause, VisualStyle
from .pipeline import Output, Source, Review, AgentOutputError, agent, save_editorial
from .scene_layout import VisualObject, SceneBlock, Background, Shot, Key, Motion, geometry, new_id, MAX_SHOTS, MAX_PROJECT_SHOTS, AREA

Color = Annotated[str, StringConstraints(pattern=r'^#[0-9a-fA-F]{6}$')]
ImageId = Annotated[str, StringConstraints(pattern=r'^[a-f0-9]{32}$')]
MAX_WORDS = 500
MIN_TEXT = 16


class ScriptScene(Output):
    # The time slot the prompt asks for this passage ("16–28 s"), empty when it asks none.
    timing: str = Field(max_length=40)
    narration: str = Field(min_length=1, max_length=1400)
    screen_text: list[Annotated[str, StringConstraints(max_length=300)]] = Field(max_length=6)
    visual: str = Field(max_length=1500)
    pauses: list[Pause] = Field(max_length=4)


Hashtag = Annotated[str, StringConstraints(pattern=r'^#[^\s#]{1,60}$')]


class FreeScript(Output):
    # 'script': the prompt brought the whole script and it is followed literally; 'idea': the writer wrote it.
    mode: Literal['script', 'idea']
    # Publication package: the first title is the one used; the others stay as options.
    titles: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]] = Field(min_length=1, max_length=5)
    description: str = Field(min_length=1, max_length=5000)
    tags: str = Field(min_length=1, max_length=500)
    hashtags: list[Hashtag] = Field(max_length=15)
    pinned_comment: str = Field(max_length=5000)
    scenes: list[ScriptScene] = Field(min_length=1, max_length=12)
    claims: list[Annotated[str, StringConstraints(min_length=1, max_length=600)]] = Field(max_length=12)


class Check(Output):
    claim: str = Field(min_length=1, max_length=600)
    verified: bool
    source_url: str = Field(max_length=1500)
    evidence: str = Field(max_length=350)


class ClaimResearch(Output):
    sources: list[Source] = Field(max_length=8)
    checks: list[Check] = Field(max_length=12)


class FreeObject(Output):
    type: Literal['title', 'paragraph', 'image', 'flow']
    text: str = Field(max_length=1500)
    font_size: float = Field(ge=MIN_TEXT, le=200, allow_inf_nan=False)
    color: Color | None
    align: Literal['left', 'center', 'right']
    reveal: Literal['none', 'lines', 'typing']
    image_id: ImageId | None
    # An image the Arte will generate: the key of one of the director's image requests (ADR 0005).
    art: ArtKey | None = None
    motion: Motion
    flow: FlowSpec | None


class FreeBlock(Output):
    height: float = Field(gt=0, le=100, allow_inf_nan=False)
    object: FreeObject | None


class FreeBackground(Output):
    kind: Literal['color', 'gradient', 'image']
    color: Color | None
    color_to: Color | None
    angle: float = Field(ge=0, le=360, allow_inf_nan=False)
    image_id: ImageId | None
    art: ArtKey | None = None
    # The B-roll whose clip will fill this plano; the imagem provisória holds it until the clip is imported.
    broll: Key | None = None
    motion: Motion
    dim: float = Field(ge=0, le=80, allow_inf_nan=False)


class FreeShot(Output):
    anchor: str | None = Field(max_length=200)
    transition: Literal['cut', 'fade']
    brand: bool
    background: FreeBackground | None
    blocks: list[FreeBlock] = Field(min_length=1, max_length=6)


class FreeScene(Output):
    title: str = Field(max_length=100)
    shots: list[FreeShot] = Field(min_length=1, max_length=MAX_SHOTS)


class FreeStyle(Output):
    background: Color
    text_color: Color
    font: str = Field(min_length=1, max_length=150)


class FreeDirection(Output):
    accent: Color
    style: FreeStyle
    captions: CaptionStyle
    loop: bool
    scenes: list[FreeScene] = Field(min_length=1, max_length=12)
    # Visual bible and image requests for the Arte; empty when the Short has no generated images.
    bible: Bible | None = None
    # Unbounded here: requests past the limit get a correction and are then dropped, never a failed direction.
    images: list[ArtRequest] = Field(default_factory=list)
    # Lista de materiais: the B-rolls in video or image made outside the MyCut; same correction as the images.
    brolls: list[Broll] = Field(default_factory=list)


WRITER = (
    'Leia o prompt do Short livre. Ele é a especificação: não há formato, arco narrativo ou esqueleto de cena impostos. '
    'Se o prompt já traz um roteiro completo (fala por trecho), use mode="script": cada trecho vira uma cena, na mesma ordem; '
    'narration é a fala do trecho copiada literalmente, só com ajustes de grafia e pontuação para a leitura em voz alta, '
    'sem aspas, marcações de tempo ou indicações de cena; o tempo pedido para o trecho vai em timing (vazio se não houver). '
    'Nunca reescreva, resuma, acrescente, omita ou reordene falas. '
    'screen_text traz, literalmente, o texto na tela pedido para o trecho (vazio se não houver); visual resume o que o prompt '
    'pede para mostrar. Se o prompt é só uma ideia, use mode="idea" e escreva o roteiro com liberdade de estrutura: número de '
    'cenas, ritmo e tom vêm do pedido. Até 12 cenas, até 180 s e até 500 palavras de narração no total, vídeo vertical 9:16. '
    'Uma pausa pedida na fala, como "(pausa)", não entra em narration: vira pauses, com after copiado literalmente da '
    'narração da cena (o trecho logo antes da pausa) e seconds (0,2 a 3; 0,8 quando o prompt não diz). '
    'Em claims, liste somente as afirmações factuais externas da narração e do texto na tela que precisam de fonte '
    '(ferramentas, preços, datas, números, lançamentos). Método próprio, opinião e ficção não entram; sem fatos externos, '
    'claims=[]. Pacote de publicação, aproveitando o que o prompt já trouxer: titles com 1 a 5 opções de título fiel (a '
    'primeira é a usada), descrição, tags separadas por vírgula, hashtags (cada uma começando por #) e pinned_comment, o '
    'comentário fixado pedido no prompt (vazio se não houver). '
    'Corrija os problemas em issues_to_fix.')

RESEARCH = (
    'Verifique somente as afirmações de claims, com WebSearch/WebFetch, em fontes primárias. Não pesquise nem julgue mais nada. '
    'Para cada afirmação, verified=true apenas com a página em sources e um pequeno trecho de evidência; caso contrário, '
    'verified=false, source_url="" e evidence dizendo o que faltou. Nunca invente URLs.')

DIRECTOR = (
    'Dirija o Short livre. Para cada cena de script.scenes, na mesma ordem, crie uma cena com um ou mais planos (shots). '
    'Não há esqueleto: você escolhe quantos blocos empilhados cada plano tem e as alturas (somam 100), o tipo de objeto, '
    'tela cheia (um bloco de 100 ou um fundo de imagem) e tela dividida (dois blocos). Cada bloco tem no máximo um objeto: '
    'title, paragraph, image (image_id de available_images) ou flow (Fluxo animado). O texto na tela de screen_text aparece '
    'literalmente num title ou paragraph. reveal=lines revela fichas e listas linha a linha (uma linha por quebra \\n) e '
    'reveal=typing simula digitação; reveal só vale para title e paragraph, motion só para imagens. '
    'O primeiro plano começa com a cena; cada plano seguinte começa na anchor, um trecho copiado literalmente da narração '
    'da cena e em ordem; transition=cut (corte seco) ou fade (fusão). Ritmo de corte, tom e cores vêm do prompt. '
    'Fundo do plano: color, gradient (color e color_to, com angle) ou image (image_id, com motion), e dim escurece a mídia '
    'para o texto ficar legível; background=null usa style.background. Dê aos textos color com bom contraste '
    'sobre o fundo, ou null para style.text_color. brand=false oculta a marca do canal, como num B-roll em tela cheia. '
    'A área dos blocos tem area.width × area.height px por plano. Textos concisos que caibam, font_size de 16 a 200. '
    'Não há formato de base: accent (cor de destaque) e style vêm do tom do prompt. style.background é o fundo do projeto, '
    'style.text_color a cor dos textos e style.font uma família do Google Fonts que combine com o tom (ex.: Roboto, Inter, '
    'Montserrat, Oswald, Bebas Neue, Space Grotesk, Orbitron, Exo 2, Playfair Display, Merriweather, JetBrains Mono). '
    'captions é a legenda: words (2 a 4) palavras por vez, position (top, middle ou bottom, todas na área segura, fora dos '
    '15% inferiores e da faixa direita dos botões do YouTube), font_size de 40 a 110 e keywords, as palavras da narração '
    'destacadas na cor accent (números e termos-chave pedidos). loop=true só quando o prompt pede que o último quadro case '
    'com o primeiro. Use somente image_id de '
    'available_images e nunca invente ids; objetos que não são flow usam flow=null. Não altere a narração. '
    'Corrija os problemas em issues_to_fix. ')

REVIEWER = (
    'Confira o Short livre contra o prompt, que é a especificação, e contra research. Fidelidade: quando o prompt traz um '
    'roteiro completo, narração, texto na tela, ordem dos trechos e tempos ou ritmo pedidos devem segui-lo; só ajustes de '
    'grafia e pontuação na fala são aceitos. Fatos: afirmações factuais externas precisam de verificação em research; as não '
    'verificadas devem estar em warnings, ou suavizadas quando o roteiro foi escrito pelo agente. Conteúdo autoral ou fictício '
    'não precisa de fonte. Pessoas reais identificáveis não podem ser retratadas. Reprove somente problemas concretos e '
    'descreva cada um em issues.')


class Calls:
    """Each role's calls are numbered so every attempt keeps its own saved output."""
    def __init__(self, job):
        self.job, self.count = job, {}

    def __call__(self, role, instructions, payload, model, web=False):
        self.count[role] = self.count.get(role, 0) + 1
        return agent(self.job, role, instructions, payload, model, web=web, attempt=self.count[role])


def write(ask, project, issues):
    corrections = list(issues)
    for _ in range(2):
        try:
            script = ask('writer', WRITER, {'prompt': project['brief'], 'issues_to_fix': corrections,
                                            'attachments': [image['name'] for image in project.get('images', [])]}, FreeScript)
            words = len(' '.join(scene.narration for scene in script.scenes).split())
            if words > MAX_WORDS:
                raise AgentOutputError(f'scenes: a narração tem {words} palavras; use até {MAX_WORDS}.')
            return script
        except AgentOutputError as exc:
            corrections = [*issues, str(exc)]
    raise ValueError('O roteiro livre continuou fora do formato após a correção. ' + corrections[-1])


def research(ask, claims, known, notes):
    """Checks for the claims not yet checked; any failure leaves a claim unverified, never refuses."""
    pending = [claim for claim in claims if claim not in known]
    if not pending:
        return
    try:
        result = ask('research', RESEARCH, {'claims': pending, 'date': datetime.now(timezone.utc).isoformat()},
                     ClaimResearch, web=True)
    except ValueError as exc:
        # Invalid output, CLI error or timeout: the production goes on with the claims as warnings.
        store.step(ask.job['id'], 'research', 'failed', f'Pesquisa indisponível: {exc}'[:500])
        notes.append(f'Pesquisa indisponível: {exc}'[:500])
        result = ClaimResearch(sources=[], checks=[])
    sources = {source.url: source.model_dump() for source in result.sources if public_url(source.url)}
    for check in result.checks:
        if check.claim in pending and check.verified and check.source_url in sources:
            known[check.claim] = {**check.model_dump(), 'source': sources[check.source_url]}
    for claim in pending:
        known.setdefault(claim, {'claim': claim, 'verified': False, 'source_url': '', 'evidence': '', 'source': None})


def public_url(url):
    parts = urlsplit(url)
    return parts.scheme in ('https', 'http') and bool(parts.hostname) and not parts.username and not parts.password


def unverified(script, known):
    return [claim for claim in script.claims if not known[claim]['verified']]


def verify(ask, project, script, issues, known):
    """Unverified claims become warnings in the user's script, or are softened when the agent wrote it."""
    if not script.claims:
        store.step(ask.job['id'], 'research', 'skipped', 'Sem afirmações factuais externas: pesquisa dispensada')
        return script, []
    notes = []
    research(ask, script.claims, known, notes)
    doubtful = unverified(script, known)
    if doubtful and script.mode == 'idea':
        try:
            softened = write(ask, project, [*issues, 'Suavize ou remova estas afirmações, que não puderam ser verificadas: '
                                            + '; '.join(doubtful)])
        except ValueError:
            softened = None  # The script is already paid: keep it, with its claims as warnings.
        if softened is not None:
            # Claims the softened script still makes are checked once; what stays unverified is a warning.
            research(ask, softened.claims, known, notes)
            script = softened
    return script, notes + [f'Afirmação não verificada: {claim}' for claim in unverified(script, known)]


def direct(ask, project, script, issues):
    """One bounded correction; then the composition is repaired, or rebuilt from the script if unusable.
    Returns the direction, the scenes and the warnings about what the repair changed."""
    images = project.get('images', [])
    generating = artwork.mode(project) != 'none'
    payload = {'prompt': project['brief'], 'script': script.model_dump(), 'flow_icons': flow.icon_names(),
               'available_images': [{k: v for k, v in item.items() if k != 'path'} for item in images],
               'area': {'width': AREA[2], 'height': AREA[3]},
               'art': {'max_images': artwork.MAX_IMAGES, 'max_bases': artwork.MAX_BASES} if generating else None,
               'materials': {'max_brolls': materials.MAX_BROLLS}}
    corrections = list(issues)
    for final in (False, True):
        try:
            direction = ask('director', DIRECTOR + artwork.GUIDE + materials.GUIDE + flow.GUIDE, {**payload, 'issues_to_fix': corrections},
                            FreeDirection)
        except ValueError as exc:
            if final:
                message = f'A direção não pôde ser usada ({exc}); as cenas mostram o texto na tela do roteiro.'[:500]
                store.step(ask.job['id'], 'director', 'failed', message)
                notes, style = [message], generated_style(None, [], True, [])
                styled = {**project, 'visual_style': style}
                return None, [fallback(scene, index, styled, notes) for index, scene in enumerate(script.scenes)], notes, style, [], []
            corrections = [*issues, str(exc)]
            continue
        notes, problems = [], []
        # Text is measured with the font the Short will be drawn with.
        style = generated_style(direction, problems, final, notes)
        available = {item['id'] for item in images}
        requests = artwork.requests(direction, available, problems, final) if generating else []
        bases = {item['key'] for item in requests if item['base']}
        brolls = materials.checked(direction, available | bases, problems, final)
        problems, scenes = compose(direction, script, {**project, 'visual_style': style}, final, notes, problems, requests,
                                   {item['key'] for item in brolls})
        requests = artwork.unused(requests, problems, final)
        brolls = materials.unused(brolls, scenes, problems, final)
        if final or not problems:
            return direction, scenes, notes, style, requests, brolls
        corrections = [*issues, *problems[:8]]


def generated_style(direction, problems, repair, notes):
    """The Short's visual_style from the prompt's tone, chosen by the director with no format as a base (ADR 0005)."""
    base = {'format_id': 'free', 'font': 'sans', 'media_mode': 'mixed', 'image_source': 'library'}
    if direction is None:
        return VisualStyle(**base, google_font='Roboto', captions=CaptionStyle()).model_dump()
    font = direction.style.font
    try:
        google_fonts.entry(font)
    except ValueError as exc:
        problems.append(f'style.font: {exc}')
        font = 'Roboto'
    try:
        google_fonts.install(font)
    except ValueError as exc:
        notes.append(f'A fonte {font} não pôde ser baixada ({exc}); o Short usa Roboto.'[:500])
        font = 'Roboto'
    return VisualStyle(**base, google_font=font, background=direction.style.background, text_color=direction.style.text_color,
                       captions=direction.captions, loop=direction.loop).model_dump()


def compose(direction, script, project, repair, notes, problems, requests=(), brolls=()):
    """Project scenes from the director's output, with the problems found; with repair, fixes them instead.
    An image the Arte will generate leaves its place empty and the request records where it goes; a B-roll's plano
    keeps its background waiting for that image and then for the clip."""
    if len(direction.scenes) != len(script.scenes):
        problems.append(f'scenes: crie exatamente {len(script.scenes)} cenas, uma por cena do roteiro.')
    images = {item['id'] for item in project.get('images', [])}
    art = {item['key']: item for item in requests}
    budget = MAX_PROJECT_SHOTS
    scenes = []
    for index, source in enumerate(script.scenes):
        visual = direction.scenes[index] if index < len(direction.scenes) else None
        if visual is None:
            scenes.append(fallback(source, index, project, notes))
            budget -= 1
            continue
        remaining = len(script.scenes) - index - 1
        planos = visual.shots[:max(1, budget - remaining)]
        if len(planos) < len(visual.shots):
            problems.append(f'Use até {MAX_PROJECT_SHOTS} planos no Short inteiro.')
        budget -= len(planos)
        built = [plano(shot, index, number, images, problems, art, brolls, artwork.mode(project) != 'none')
                 for number, shot in enumerate(planos)]
        markers = [(shot.pop('_art', None), [block.pop('_art', None) for block in shot['blocks']]) for shot in built]
        scene = {**built[0], 'id': new_id(), 'title': visual.title or (source.screen_text or [''])[0][:100] or f'Cena {index+1}',
                 'narration': source.narration, 'layout': 'statement', 'items': items(source),
                 'shots': [Shot(id=new_id(), **shot).model_dump() for shot in built[1:]], 'pauses': pauses(source, index, notes)}
        del scene['anchor'], scene['transition']
        for (background, blocks), stored in zip(markers, [scene, *scene['shots']]):
            artwork.add_placements(art, scene['id'], stored, background, blocks)
        scenes.append(settle(scene, index, project, problems, repair, notes))
    return problems, scenes


def plano(shot, scene, number, images, problems, art, brolls=(), generating=False):
    where = f'scenes[{scene}].shots[{number}]'
    total = sum(block.height for block in shot.blocks)
    heights = [block.height * 100 / total for block in shot.blocks]
    if not math.isclose(total, 100, abs_tol=.01):
        problems.append(f'{where}: as alturas dos blocos somam {total:g}; elas devem somar 100.')
    # Rounding is absorbed by the last block so the composition always sums to 100.
    heights = [round(h, 4) for h in heights[:-1]]
    heights.append(round(100 - sum(heights), 4))
    blocks = []
    for i, (block, height) in enumerate(zip(shot.blocks, heights)):
        value, marker = block.object, None
        if value is not None and value.type == 'image' and value.art is not None and value.image_id not in images:
            marker = requested(value.art, art, f'{where}.blocks[{i}].object', problems) and {'key': value.art, 'motion': value.motion}
            value = None
        blocks.append({**SceneBlock(height=height, object=visual_object(value, f'{where}.blocks[{i}]', images, problems)).model_dump(),
                       **({'_art': marker} if marker else {})})
    background, marker = None, None
    value = shot.background
    broll = value.broll if value else None
    if broll is not None and broll not in brolls:
        problems.append(f'{where}.background.broll: use a key de um B-roll de brolls.')
        broll = None
    if value and value.kind == 'image' and value.art is not None and value.image_id not in images:
        motion = value.motion
        if broll:
            motion = stand_in(broll, value.motion, value.art in art, generating,
                              f'{where}.background', problems)
            background = Background(kind='image', motion=motion, dim=value.dim, broll=broll).model_dump()
        marker = requested(value.art, art, f'{where}.background', problems) and {'key': value.art, 'motion': motion,
                                                                                  'dim': value.dim}
    elif broll:
        if value.image_id is not None and value.image_id not in images:
            problems.append(f'{where}.background: use um image_id de available_images.')
        # With no image, the plano waits for the clip on the project background.
        image = value.image_id if value.image_id in images else None
        motion = stand_in(broll, value.motion, image is not None, generating, f'{where}.background', problems)
        background = Background(kind='image', asset_id=image, motion=motion, dim=value.dim, broll=broll).model_dump()
    elif shot.background:
        value = shot.background
        try:
            if value.kind == 'image' and value.image_id not in images:
                raise ValueError('use um image_id de available_images.')
            background = Background(kind=value.kind, color=value.color, color_to=value.color_to, angle=value.angle,
                                    asset_id=value.image_id if value.kind == 'image' else None,
                                    motion=value.motion if value.kind == 'image' else 'none', dim=value.dim).model_dump()
        except ValueError as exc:
            problems.append(f'{where}.background: {exc}')
    return {'anchor': shot.anchor or None if number else None, 'transition': shot.transition, 'brand': shot.brand,
            'background': background, 'blocks': blocks, **({'_art': marker} if marker else {})}


def stand_in(broll, motion, image, generating, where, problems):
    """The imagem provisória holds a B-roll's plano with camera motion until the clip arrives; returns the motion,
    a slow zoom when the director gave none."""
    if generating and not image:
        problems.append(f'{where}: dê ao plano do B-roll “{broll}” uma imagem provisória em art (uma imagem de images) '
                        'ou image_id.')
    if image and motion == 'none':
        problems.append(f'{where}: dê movimento de câmera (motion) à imagem provisória do B-roll “{broll}”.')
        return 'zoom_in'
    return motion


def requested(key, art, where, problems):
    """Whether an object or background uses an image the director asked the Arte for."""
    if key in art:
        return True
    problems.append(f'{where}: use em art a key de uma imagem de images, ou um image_id de available_images.')
    return False


def visual_object(value, where, images, problems):
    if value is None:
        return None
    if value.type == 'image' and value.image_id not in images:
        problems.append(f'{where}.object: use um image_id de available_images ou outro tipo de objeto.')
        return None
    if value.type in ('title', 'paragraph') and not value.text.strip():
        return None
    if value.type == 'flow' and value.flow is None:
        problems.append(f'{where}.object: monte o flow ou use title/paragraph.')
        return None
    text = value.type in ('title', 'paragraph')
    return VisualObject(type=value.type, text=value.text if text else '', font_size=value.font_size, color=value.color,
                        align=value.align, text_vertical='center' if value.type == 'title' else 'top',
                        asset_id=value.image_id if value.type == 'image' else None, fit='cover',
                        reveal=value.reveal if text else 'none', motion=value.motion if value.type == 'image' else 'none',
                        flow=value.flow if value.type == 'flow' else None).model_dump()


def settle(scene, index, project, problems, repair, notes):
    """Text that does not fit, flows that do not fit and unknown anchors: reported, or fixed on the last attempt.
    A repaired scene is measured again, so nothing the render would refuse survives after the voice is paid."""
    scene = Scene.model_validate(scene).model_dump()
    report = inspect(scene, project)
    for item in report['warnings']:
        problems.append(f'scenes[{index}]: ' + item['message'])
        if repair and item['kind'] == 'shot_anchor':
            for shot in scene.get('shots', []):
                if shot['id'] == item['shot_id']:
                    shot['anchor'] = None
    problems += [f'scenes[{index}]: ' + item['message'] for item in report['issues']]
    if not repair:
        return scene
    for shot in [scene, *scene.get('shots', [])]:
        for block, info in zip(shot['blocks'], geometry(shot['blocks'])):
            obj = block.get('object')
            if obj and obj['type'] == 'flow':
                for step in flow.anchor_warnings(obj['flow'], scene['narration']):
                    obj['flow']['steps'][step]['anchor'] = None
            issue = next((item for item in report['issues'] if obj and item.get('object_id') == obj['id']), None)
            if issue and issue['kind'] == 'overflow':
                block['object'] = fit(obj, issue, info['object'], project, index, notes)
    for item in inspect(scene, project)['issues']:
        # Whatever still cannot be drawn leaves the plano, and the user is told.
        for shot in [scene, *scene.get('shots', [])]:
            for block in shot['blocks']:
                if block.get('object') and block['object']['id'] == item.get('object_id'):
                    block['object'] = None
                    notes.append(f'Cena {index+1}: um objeto que não cabia no bloco foi removido.')
    return Scene.model_validate(scene).model_dump()


def fit(obj, issue, box, project, index, notes):
    """The smallest change that makes an object fit its block: a smaller font, then a shorter text."""
    if obj['type'] == 'flow':
        if (issue.get('font_size') or 0) >= 22:
            return {**obj, 'font_size': issue['font_size']}
        # The flow's labels cannot be read on a phone: its nodes become a paragraph.
        labels = '\n'.join(node['label'] for node in obj['flow']['nodes'])
        obj = VisualObject(id=obj['id'], type='paragraph', text=labels, font_size=40).model_dump()
    style = visuals.resolve(project)
    original = obj['text']
    while True:
        size = next((s for s in range(int(obj['font_size']), MIN_TEXT-1, -1) if not text_layout(obj, box, style, s)[3]), None)
        if size is not None:
            obj['font_size'] = size
            break
        body = obj['text'].rstrip('…')
        words = body.split(' ')
        if len(words) > 1:
            body = ' '.join(words[:len(words) * 3 // 4 or 1])
        elif len(body) > 1:
            body = body[:len(body) * 3 // 4 or 1]
        else:
            break  # Not even one character fits: the scene's last check removes the object.
        obj['text'] = body + '…'
    if obj['text'] != original:
        notes.append(f'Cena {index+1}: o texto na tela foi encurtado para caber: “{original[:120]}”.')
    return obj


def pauses(source, index, notes):
    """The script's pauses whose passage is in the narration; any other one is dropped and the user is told."""
    kept = []
    for pause in source.pauses:
        if flow.pause_points({'narration': source.narration, 'pauses': [pause.model_dump()]}):
            kept.append(pause.model_dump())
        else:
            notes.append(f'Cena {index+1}: a pausa depois de “{pause.after}” não está na narração e foi removida.')
    return kept


def items(source):
    return [text[:100] for text in source.screen_text if text.strip()][:4]


def fallback(source, index, project, notes):
    """The script's scene with its text on screen, when the director's composition could not be used."""
    lines = [text for text in source.screen_text if text.strip()]
    title = VisualObject(type='title', text=(lines[0] if lines else source.visual or 'Cena')[:300], font_size=64,
                         align='center', text_vertical='center')
    rest = VisualObject(type='paragraph', text='\n'.join(lines[1:]), font_size=44, reveal='lines') if lines[1:] else None
    blocks = [SceneBlock(height=30, object=title), SceneBlock(height=70, object=rest)]
    scene = {'id': new_id(), 'title': title.text[:100], 'narration': source.narration, 'layout': 'statement',
             'items': items(source), 'blocks': [block.model_dump() for block in blocks], 'pauses': pauses(source, index, notes)}
    return settle(scene, index, project, [], True, notes)


def summary(script, scenes):
    """What the conference compares with the prompt: requested time, narration and texts on screen, plano by plano."""
    return [{'timing': source.timing, 'narration': scene['narration'], 'pauses': scene.get('pauses', []),
             'shots': [{'anchor': shot.get('anchor'), 'texts': [b['object']['text'] for b in shot['blocks']
                                                                if b.get('object') and b['object']['type'] in ('title', 'paragraph')]}
                       for shot in [scene, *scene.get('shots', [])]]} for source, scene in zip(script.scenes, scenes)]


def produce(job, folder):
    """Script, optional research, direction and conference of a Short livre, saved as one checkpoint."""
    project = job['snapshot']
    ask = Calls(job)
    issues, known, interrupted, kept = [], {}, [], None
    for _ in (1, 2):
        try:
            script = write(ask, project, issues)
            script, warnings = verify(ask, project, script, issues, known)
            direction, scenes, notes, style, requests, brolls = direct(ask, project, script, issues)
        except ValueError as exc:
            if kept is None:
                raise
            # The correction failed: the first round's paid work is kept for review.
            interrupted = [f'A correção pedida pela conferência não pôde ser feita: {exc}'[:500]]
            break
        checked = [known[claim] for claim in script.claims if claim in known]
        try:
            review = ask('reviewer', REVIEWER, {'prompt': project['brief'], 'script': script.model_dump(),
                                                'scenes': summary(script, scenes), 'research': checked, 'warnings': warnings}, Review)
        except ValueError as exc:
            # Invalid output, CLI error or timeout: the paid script and scenes are kept, as after a rejection.
            review = Review(approved=False, issues=[str(exc)[:500]])
        kept = script, warnings + notes, direction, scenes, style, checked, review, requests, brolls
        if review.approved:
            break
        issues = review.issues or ['A conferência não aprovou a fidelidade ao prompt.']
    script, warnings, direction, scenes, style, checked, review, requests, brolls = kept
    sources = list(dict.fromkeys(item['source']['url'] for item in checked if item['verified']))
    accent = project['accent'] if project.get('accent_locked') or direction is None else direction.accent
    if not review.approved:
        warnings = warnings + [f'Conferência: {issue}' for issue in issues] + interrupted
    values = {'title': script.titles[0], 'description': script.description, 'tags': script.tags, 'sources': '\n'.join(sources),
              'scenes': scenes, 'images': artwork.library(project.get('images', []), scenes, requests), 'accent': accent, 'research': {'checks': checked}, 'free_script': script.model_dump(),
              'agent_review': review.model_dump(), 'audio': None, 'warnings': warnings, 'visual_style': style,
              'publication': {'titles': script.titles, 'description': script.description, 'hashtags': script.hashtags,
                              'pinned_comment': script.pinned_comment},
              'art': {'mode': artwork.mode(project), 'bible': direction.bible.model_dump() if direction and direction.bible else None,
                      'requests': requests, 'estimate': None, 'then': None},
              'brolls': brolls}
    ProjectInput.model_validate({'title': script.titles[0], 'scenes': scenes, 'visual_style': style})
    job = store.checkpoint(job['id'], values)
    save_editorial(job, folder)
    if not review.approved:
        store.step(job['id'], 'reviewer', 'failed', 'Conferência apontou problemas; roteiro e cenas salvos para revisão')
        raise ValueError('A conferência não aprovou a fidelidade ao prompt após a correção. Roteiro e cenas foram salvos '
                         'para você revisar antes de gerar a voz: ' + '; '.join(issues)[:600])
    return job
