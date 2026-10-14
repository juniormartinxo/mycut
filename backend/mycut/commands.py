"""User-chosen command for each CLI. Parsed without a shell; expanded only on the host."""
import os
import re
import shlex
import shutil
from .bridge import PROVIDERS

DEFAULTS = {p: p for p in PROVIDERS}
ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*=')


def parse(text):
    """Split into leading NAME=value assignments and the executable with its arguments."""
    if not isinstance(text, str) or not text.strip() or len(text) > 500 or any(ord(c) < 32 for c in text):
        raise ValueError('Informe o comando em uma linha, com até 500 caracteres.')
    try:
        words = shlex.split(text)
    except ValueError:
        raise ValueError('O comando tem aspas sem fechamento.') from None
    split = next((i for i, word in enumerate(words) if not ASSIGNMENT.match(word)), len(words))
    if split == len(words):
        raise ValueError('Informe o executável do CLI depois das variáveis.')
    return words[:split], words[split:]


def configured(provider):
    from .integrations import read
    try:
        return read()['commands'][provider]
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULTS[provider]


def expand(word):
    return os.path.expanduser(os.path.expandvars(word))


def environment(provider):
    """Variables the command sets, expanded with the runner's HOME and environment."""
    try:
        assignments, _ = parse(configured(provider))
    except ValueError:
        return {}
    return {name: expand(value) for name, value in (a.split('=', 1) for a in assignments)}


def launcher(provider):
    """argv prefix for the provider, or None when the executable is not on the runner's PATH."""
    try:
        _, words = parse(configured(provider))
    except ValueError:
        return None
    executable = shutil.which(expand(words[0]))
    if not executable:
        return None
    variables = environment(provider)
    prefix = [shutil.which('env') or '/usr/bin/env', *(f'{k}={v}' for k, v in variables.items())] if variables else []
    return [*prefix, executable, *(expand(word) for word in words[1:])]
