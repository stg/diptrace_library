"""Stable case normalization for design-file labels and resource paths."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _lowercase_mapping():
    data = json.loads(Path(__file__).with_name('windows_lowercase.json').read_text(encoding='utf-8'))
    return {int(key): chr(value) for key, value in data['mapping'].items()}


def lowercase(text):
    """Apply the measured single-character mappings without Unicode expansion."""
    mapping = _lowercase_mapping()
    return ''.join(mapping.get(ord(character), character) for character in text)


def label_lowercase(text):
    """Normalize a public label key, including its established ending rule."""
    raw = lowercase(text).encode('utf-16-le', errors='surrogatepass')
    if len(raw) > 2 and raw[-2:] in (b'\r\x00', b'\n\x00'):
        raw = raw[:-4]+raw[-2:]
    return raw.decode('utf-16-le', errors='surrogatepass')
