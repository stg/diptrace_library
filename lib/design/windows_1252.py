"""Portable Windows-1252 decoding and the format ANSI best-fit output view.

The public Microsoft code-page mapping supplies numeric data. Unicode remains
unchanged in the document; encode only at a file or comparison boundary.
"""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _tables():
    data = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
    return tuple(data['decode']), {int(code): byte for code, byte in data['encode'].items()}, data['default_byte']


def decode(data):
    """Decode every byte, including the five control values Python omits."""
    characters, _, _ = _tables()
    return ''.join(chr(characters[byte]) for byte in data)


def encode(text, *, best_fit=True):
    """Encode UTF-16 code units, optionally retaining only exact round trips.

    A supplementary character occupies two unsupported UTF-16 cells and thus
    two default characters, matching the Windows ANSI conversion boundary.
    """
    characters, mappings, default = _tables()
    result = bytearray()
    for index, character in enumerate(text):
        code = ord(character)
        units = (code,) if code < 0x10000 else (0xd800+((code-0x10000) >> 10), 0xdc00+((code-0x10000) & 1023))
        for unit in units:
            byte = mappings.get(unit, default)
            if not best_fit and characters[byte] != unit:
                raise UnicodeEncodeError('windows-1252', text, index, index+1, 'character is not representable')
            result.append(byte)
    return bytes(result)


def project(text):
    """The decoded text a format Windows-1252 ASC output file will contain."""
    return decode(encode(text))
