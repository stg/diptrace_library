"""Small vector-font metrics API over an independent semantic advance table.

This measures text for compatibility layout; it does not store font contours or
format objects. FontSize/FontWidth/FontScale remain editable document fields.
The built-in profile contains measured character advances and line height.
"""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import struct
from typing import Mapping



@dataclass(frozen=True)
class TextMetrics:
    width: float
    height: float


@dataclass(frozen=True)
class VectorFontMetrics:
    advances: Mapping[int, float]
    line_height: float = 1.492
    unit_scale: float = 1.095
    unknown_advance: float = .6
    mono_advance: float = .606
    mono_line_height: float = 1.618

    def measure(self, text, *, size=1., spacing=0., monospaced=False):
        """Measure format vector text, including doubled/markup '~' markers.

        Spacing is in physical units. UTF-16 code units supply character lookup,
        so an unsupported supplementary character occupies two fallback cells.
        The empty-string width retains the compatibility trailing-gap rule;
        the enclosing text-box adapter decides its minimum size.
        """
        unit = float(size)*self.unit_scale
        spacing = float(spacing)
        if not math.isfinite(unit) or not math.isfinite(spacing):
            raise ValueError('text size and spacing must be finite')
        if abs(unit) < .0001:
            unit = .5
        gap = spacing/unit
        raw = text.encode('utf-16-le', errors='surrogatepass')
        codes = [value[0] for value in struct.iter_unpack('<H', raw)]
        position, i = 0., 0
        while i < len(codes):
            code = codes[i]
            i += 1
            if code == ord('~'):
                if i == len(codes) or codes[i] != code:
                    continue
                i += 1
            if monospaced:
                position += self.mono_advance + gap
            elif code in self.advances:
                position += self.advances[code]
                position += gap
            else:
                position += gap
                position += self.unknown_advance
        return TextMetrics((position-gap)*unit, (self.mono_line_height if monospaced else self.line_height)*unit)


@lru_cache(maxsize=1)
def builtin_vector_metrics():
    data = json.loads(Path(__file__).with_name('vector_font_metrics.json').read_text(encoding='utf-8'))
    return VectorFontMetrics({int(code): value for code, value in data['advances'].items()},
        data['line_height'], data['unit_scale'], data['unknown_advance'])
