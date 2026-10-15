"""Bring the existing Short into the studio without changing its originals."""
import json
import shutil
from .config import ROOT, DATA
from . import store
from .media import digest
from .scene_layout import new_scene


def blank(title):
    return {'title': title, 'description': '', 'tags': '#IA #Shorts', 'sources': '', 'accent': '#c85e37',
            'scenes': [new_scene(title) for title in ('O que mudou?', 'Como funciona', 'Por que isso importa')]}


def claude():
    source = ROOT / 'shorts/claude-cloud'
    paragraphs = (source / 'roteiro.txt').read_text().strip().split('\n\n')
    scenes = json.loads((source / 'storyboard.json').read_text())['scenes']
    layouts = ['flow', 'flow', 'flow', 'flow', 'comparison', 'flow', 'statement']
    items = [ ['Notebook fechado', 'Tarefa na nuvem', 'Trabalho continua'],
              ['Seu pedido', 'Máquina na nuvem', 'Resultado para revisar'],
              ['GitHub', 'Ambiente isolado', 'Branch da tarefa'],
              ['Perguntas do agente', 'Sua orientação', 'Revisar e abrir PR'],
              ['Remote Control\nComputador ativo', 'Cloud Sessions\nExecução na nuvem'],
              ['Correção ou refatoração', 'Execução', 'Sua revisão'],
              ['Qual tarefa você deixaria rodando enquanto toma um café?'] ]
    publication = (source / 'publicacao.txt').read_text()
    return {'title': publication.split('TÍTULO\n')[1].split('\n')[0],
            'description': publication.split('DESCRIÇÃO\n')[1].split('\n\nFontes:')[0],
            'tags': publication.split('TAGS DO YOUTUBE\n')[1].split('\n')[0],
            'sources': 'https://code.claude.com/docs/en/claude-code-on-the-web\nhttps://code.claude.com/docs/en/web-quickstart\nhttps://code.claude.com/docs/en/remote-control\nhttps://www.youtube.com/watch?v=-OH1y7CjIew',
            'accent': '#b8512f', 'scenes': [dict(title=s['headline'].replace('\n', ' '), narration=paragraphs[i], layout=layouts[i], items=items[i]) for i, s in enumerate(scenes)]}


def initialize_example():
    try:
        store.get_project('claude-cloud')
        return
    except store.Missing:
        pass
    source = ROOT / 'shorts/claude-cloud'
    if not (source / 'roteiro.txt').is_file():
        return
    document = claude()
    folder = DATA / 'projects/claude-cloud'
    folder.mkdir(parents=True, exist_ok=True)
    for name, key in [('brand/thumbnail.png', 'cover'), ('audio/narracao.wav', 'audio')]:
        origin = source / name
        if not origin.is_file():
            continue
        destination = folder / ('cover.png' if key == 'cover' else 'narracao.wav')
        shutil.copy2(origin, destination)
        document[key] = {'path': str(destination.relative_to(DATA)), 'name': origin.name, 'sha256': digest(destination)}
        if key == 'audio':
            from .media import probe
            document[key].update(duration=probe(destination), script_hash=store.script_hash(document), normalized=True)
    # Reuse alignment only when its exact narration matches the selected file.
    if document.get('audio') and (source / 'alignment.raw.json').is_file():
        alignment = json.loads((source / 'alignment.raw.json').read_text())
        if alignment.get('audio_sha256') == document['audio']['sha256']:
            shutil.copy2(source / 'alignment.raw.json', folder / 'alignment.json')
            document['audio']['alignment'] = str((folder / 'alignment.json').relative_to(DATA))
    store.create_project(document, 'claude-cloud')
    if document.get('audio') and (source / 'short.mp4').is_file():
        manifest = json.loads((source / 'render-manifest.json').read_text())
        if (manifest['sha256'] != digest(source / 'short.mp4')
                or manifest['audio_sha256'] != document['audio']['sha256']
                or manifest['source_script_sha256'] != digest(source / 'roteiro.txt')):
            return
        job = store.enqueue('claude-cloud', 'final', 1)
        dest = folder / 'renders' / job['id']
        dest.mkdir(parents=True)
        for name in ['short.mp4', 'capa.png', 'legendas.srt', 'publicacao.txt', 'roteiro.txt', 'render-manifest.json']:
            shutil.copy2(source / name, dest / name)
        store.finish(job['id'], 'succeeded', 'Short original importado · pronto para revisar',
                     {'directory': str(dest.relative_to(DATA)), 'duration': document['audio']['duration'], 'has_audio': True,
                      'width': 1080, 'height': 1920, 'timing': 'aligned', 'imported': True})
