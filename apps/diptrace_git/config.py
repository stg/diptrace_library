"""Portable settings and per-design reconstruction instructions."""
from pathlib import PurePosixPath

from .files import read_json

CONFIG = '.diptrace-git.json'
SIGNATURE = 'diptrace-git/1'
METADATA_SUFFIX = '.git.json'
NOTE = 'diptrace-git: records the binary output version for rebuilding this design from its text companion.'


def validate_rule(rule):
    if not rule or any(char in rule for char in '\r\n\0\\'):
        raise ValueError('rules must be single Git-style patterns using forward slashes')
    if rule.startswith('#') or rule.strip() != rule or '..' in PurePosixPath(rule).parts:
        raise ValueError(f'unsupported selection rule: {rule!r}')
    # Positive rules also become ignore entries. Restrict them to the supported
    # binary extension so a broad selection cannot hide unrelated project files.
    if not rule.startswith('!') and not rule.lower().endswith('.dch'):
        raise ValueError('positive rules must end in .dch; exclusions may use !directory/**')


def load_config(repo):
    path = repo.path(CONFIG)
    if not path.is_file():
        raise ValueError('no .diptrace-git.json; run init in this repository first')
    config = read_json(path)
    if config.get('format') != SIGNATURE or config.get('text_format') not in ('dchxml', 'asc'):
        raise ValueError('unsupported diptrace-git configuration')
    if not isinstance(config.get('rules'), list) or not all(isinstance(r, str) for r in config['rules']):
        raise ValueError('configuration rules must be a list of patterns')
    if type(config.get('fallback_earlier', False)) is not bool:
        raise ValueError('fallback_earlier must be true or false')
    for rule in config['rules']:
        validate_rule(rule)
    return config


def new_config(text_format='dchxml', fallback=False):
    return {'format': SIGNATURE, 'text_format': text_format,
            'fallback_earlier': fallback, 'rules': []}


def companions(binary, text_format):
    return str(PurePosixPath(binary).with_suffix('.' + text_format)), binary + METADATA_SUFFIX


def manifest(binary, version, text_format):
    text, _ = companions(binary, text_format)
    return {'format': SIGNATURE, 'purpose': NOTE,
            'binary': {'path': binary, 'version': version}, 'text': {'path': text}}


def load_manifest(repo, name):
    value = read_json(repo.path(name))
    try:
        binary = value['binary']['path']
        version = value['binary']['version']
        text = value['text']['path']
        text_format = PurePosixPath(text).suffix.lstrip('.')
        if (value['format'] != SIGNATURE or type(version) is not int
                or not binary.lower().endswith('.dch') or text_format not in ('asc', 'dchxml')
                or companions(binary, text_format) != (text, name)):
            raise ValueError()
        repo.path(binary)
        repo.path(text)
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ValueError(f'{name}: invalid reconstruction metadata') from None
    return value
