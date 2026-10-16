"""Lista de materiais (ADR 0005): the B-rolls a Short livre needs from tools the MyCut does not drive, clips from
Kling, Runway or Luma or images from Midjourney or Flux. The director lists each one with its prompt, suggested tool,
references and duration and puts it in the background of the planos it fills. Until its clip is imported the plano
shows the imagem provisória with camera motion, or the project background, and never blocks the export; importing
the clip, a video or an image, replaces that background."""
from pydantic import Field
from .art import MAX_REFERENCES, planos
from .pipeline import Output
from .scene_layout import Background, Key

MAX_BROLLS = 12
IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp', '.gif')


class Broll(Output):
    key: Key
    # What the clip is in the Short, in Portuguese: "Gancho: o mesmo personagem com 3 rostos".
    title: str = Field(min_length=1, max_length=100)
    # The prompt for the external tool, in English, complete and self-contained.
    prompt: str = Field(min_length=1, max_length=3000)
    tool: str = Field(min_length=1, max_length=100)
    # Keys of the Arte's bases, or ids of the production's images, to attach in the tool.
    references: list[str] = Field(max_length=MAX_REFERENCES)
    seconds: float = Field(ge=.5, le=15, allow_inf_nan=False)


GUIDE = (
    'Lista de materiais: em brolls, liste todos os B-rolls que o prompt pede para fazer fora do MyCut, sejam clipes em '
    'vídeo (Kling, Runway, Luma) ou imagens (Midjourney, Flux), até materials.max_brolls, na ordem em que aparecem no '
    'prompt: key única (minúsculas, números e hífens), title curto em português com o uso no Short, prompt em inglês '
    'completo e autocontido (copie o do prompt quando houver), tool (ferramenta sugerida, como o prompt diz), references '
    '(keys de imagens-base de images ou ids de available_images a anexar na ferramenta; [] se nenhuma) e seconds '
    '(duração no Short). Cada B-roll entra no fundo de pelo menos um plano: background kind=image com broll=key, com a '
    'imagem provisória que segura o plano até o clipe chegar, em art (a key de uma imagem de images) ou image_id, e '
    'motion diferente de none para dar movimento de câmera. Sem B-rolls no prompt, brolls=[] e broll=null em todos os '
    'fundos. ')


def checked(direction, references, problems, repair):
    """The director's B-rolls; on the last attempt invalid parts are dropped instead of reported."""
    kept, keys = [], set()
    if len(direction.brolls) > MAX_BROLLS:
        problems.append(f'brolls: liste até {MAX_BROLLS} B-rolls; foram {len(direction.brolls)}.')
    for index, item in enumerate(direction.brolls[:MAX_BROLLS] if repair else direction.brolls):
        if item.key in keys:
            problems.append(f'brolls[{index}].key: “{item.key}” repete outra key.')
            continue
        cited = list(dict.fromkeys(item.references))
        unknown = [reference for reference in cited if reference not in references]
        for reference in unknown:
            problems.append(f'brolls[{index}].references: “{reference}” não é uma imagem-base de images nem um id de '
                            'available_images.')
        keys.add(item.key)
        kept.append({**item.model_dump(), 'references': [r for r in cited if r not in unknown] if repair else cited,
                     'clip': None})
    return kept


def unused(brolls, scenes, problems, repair):
    """A B-roll no plano shows would be a clip the author makes for nothing."""
    kept = []
    for item in brolls:
        if not uses(scenes, item['key']):
            problems.append(f'brolls: o B-roll “{item["key"]}” não entra em nenhum plano; ponha broll="{item["key"]}" no '
                            'fundo do plano onde o clipe entra, ou remova-o.')
            if repair:
                continue
        kept.append(item)
    return kept


def backgrounds(scenes, key):
    """The backgrounds that show a B-roll, with the scene and plano numbers the editor shows."""
    return [(number, shot, plano['background']) for number, scene in enumerate(scenes, 1)
            for shot, plano in enumerate(planos(scene), 1) if (plano.get('background') or {}).get('broll') == key]


def uses(scenes, key):
    """Whether some plano still shows this B-roll: the author may have changed its background since."""
    return bool(backgrounds(scenes, key))


def waiting(background, broll):
    """A plano waits until it shows a video or the clip imported for its B-roll, which may be an image."""
    clip = (broll.get('clip') or {}).get('id')
    return background['kind'] != 'video' and (clip is None or background.get('asset_id') != clip)


def with_clip(scenes, key, kind, asset_id):
    """Every plano of the B-roll gets the clip as its background, keeping the darkening; an image keeps the camera
    motion of the imagem provisória."""
    for _, _, background in backgrounds(scenes, key):
        motion = background.get('motion', 'none') if kind == 'image' and background['kind'] == 'image' else 'none'
        clip = Background(kind=kind, asset_id=asset_id, motion=motion, dim=background.get('dim', 0), broll=key).model_dump()
        background.clear()
        background.update(clip)
    return scenes


def listed(project):
    """The lista de materiais as the author reads it: each B-roll with its planos and whether each waits."""
    return [{**item, 'places': [{'scene': number, 'shot': shot, 'waiting': waiting(background, item)}
                                for number, shot, background in backgrounds(project['scenes'], item['key'])]}
            for item in project.get('brolls', [])]


def missing(project):
    """The numbers of the B-rolls some plano still waits for."""
    return [number for number, item in enumerate(listed(project), 1) if any(place['waiting'] for place in item['places'])]


def note(project):
    """What a finished production of a Short livre adds to its message while clips are missing."""
    numbers = missing(project)
    if not numbers:
        return ''
    which = ', '.join(f'B-roll {number}' for number in numbers)
    return (f' · {"falta 1 clipe" if len(numbers) == 1 else f"faltam {len(numbers)} clipes"} de B-roll ({which}): '
            'veja a aba Materiais')


def listing(project):
    """materiais.txt: the list the author takes to the external tools."""
    names = {item['key']: item['title'] for item in (project.get('art') or {}).get('requests', [])}
    names |= {item['id']: item['name'] for item in project.get('images', [])}
    entries = []
    for number, item in enumerate(listed(project), 1):
        where = '; '.join(f'cena {place["scene"]}, plano {place["shot"]}' for place in item['places']) or 'nenhum plano'
        references = ', '.join(names.get(reference, reference) for reference in item['references']) or 'nenhuma'
        entries.append(f'B-ROLL {number} · {item["title"]}\nFerramenta: {item["tool"]} · {item["seconds"]:g} s\n'
                       f'Entra em: {where}\nReferências: {references}\nPrompt: {item["prompt"]}\n')
    return 'LISTA DE MATERIAIS\n\n' + '\n'.join(entries)


def check(scenes, project):
    """A plano can only show a B-roll of this Short's list; a Short with a format has none."""
    listed = {item['key'] for item in project.get('brolls', [])}
    for scene in scenes:
        for plano in planos(scene):
            key = (plano.get('background') or {}).get('broll')
            if key and key not in listed:
                raise ValueError(f'O fundo de um plano cita o B-roll “{key}”, fora da lista de materiais deste Short.')
