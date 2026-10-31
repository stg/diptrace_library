"""Scalar wire encodings shared by DipTrace document families.

Document signatures, supported revisions and record layouts belong to their
adapters. A reader receives the text mode selected by that adapter; schema
numbers have different meanings in different document families.
"""
from decimal import Context, Decimal, ROUND_HALF_EVEN


NUMBER_LIMIT = 100_000
_NUMBER_QUANTUM = Decimal('.0001')


def _number_units(value, format_name):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError(f'{format_name} number requires a numeric value')
    value = value if isinstance(value, Decimal) else Decimal(str(value))
    if not value.is_finite() or not -NUMBER_LIMIT <= value <= NUMBER_LIMIT:
        raise ValueError(f'{format_name} number requires a finite value in -100000..100000')
    # Round once, independently of callers. Ten digits cover the full wire
    # range and its four fractional places without an intermediate float tie.
    context = Context(prec=10, rounding=ROUND_HALF_EVEN)
    return int(value.quantize(_NUMBER_QUANTUM, context=context).scaleb(4, context=context))


def quantized_number(value, *, format_name='binary'):
    """Project a value with exactly the scalar writer's precision and range."""
    return Decimal(f'{_number_units(value, format_name)}e-4')


class BinaryReader:
    error_type = ValueError

    def __init__(self, data, *, offset=0, unicode_text=True, source=None,
                 ansi_encoding='cp1252'):
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError('binary input must be bytes, bytearray or memoryview')
        if type(offset) is not int or not 0 <= offset <= len(data):
            raise ValueError('binary starting offset is outside the input')
        self.data = bytes(data)
        self.pos = offset
        self.source = source
        self.unicode_text = unicode_text
        self.ansi_encoding = ansi_encoding

    def take(self, length):
        if length < 0 or self.pos + length > len(self.data):
            raise self.error_type(f'truncated field at byte {self.pos:#x}: need {length}, '
                                  f'have {len(self.data)-self.pos}')
        raw = self.data[self.pos:self.pos+length]
        self.pos += length
        return raw

    def integer(self):
        return int.from_bytes(self.take(3), 'big') - 1_000_000

    def number(self):
        # Decimal construction is exact, even with a low caller precision.
        units = int.from_bytes(self.take(4), 'big') - 1_000_000_000
        return Decimal(f'{units}e-4')

    def boolean(self):
        start = self.pos
        value = self.take(1)[0]
        if value not in (0, 1):
            raise self.error_type(f'invalid boolean {value} at byte {start:#x}')
        return bool(value)

    def color(self):
        return int.from_bytes(self.take(3), 'little')

    def text(self):
        if self.unicode_text:
            length = int.from_bytes(self.take(2), 'big')
            return self.take(length*2).decode('utf-16-be', errors='surrogatepass')
        start = self.pos
        length = self.integer()
        if length < 0:
            raise self.error_type(f'negative string length at byte {start:#x}')
        raw = self.take(length)
        if self.ansi_encoding.lower().replace('_', '-') in ('cp1252', 'windows-1252'):
            from .text.windows_1252 import decode
            return decode(raw)
        return raw.decode(self.ansi_encoding)

    def count(self, label):
        start = self.pos
        value = self.integer()
        if value < 0 or value > len(self.data) - self.pos:
            raise self.error_type(f'invalid {label} count {value} at byte {start:#x}')
        return value


class BinaryWriter:
    format_name = 'binary'

    def __init__(self):
        self.buffer = bytearray()

    def integer(self, value):
        if isinstance(value, bool) or int(value) != value or not -1_000_000 <= value <= 1_000_000:
            raise ValueError(f'{self.format_name} integer requires an integer in -1000000..1000000')
        self.buffer.extend((int(value)+1_000_000).to_bytes(3, 'big'))

    def number(self, value):
        units = _number_units(value, self.format_name)
        self.buffer.extend((units+1_000_000_000).to_bytes(4, 'big'))

    def boolean(self, value):
        if type(value) is not bool:
            raise TypeError(f'{self.format_name} boolean requires a bool')
        self.buffer.append(int(value))

    def color(self, value):
        if isinstance(value, bool) or int(value) != value or not 0 <= value <= 0xffffff:
            raise ValueError(f'{self.format_name} color requires an integer in 0..0xffffff')
        self.buffer.extend(int(value).to_bytes(3, 'little'))

    def text(self, value):
        if not isinstance(value, str):
            raise TypeError(f'{self.format_name} text requires a string')
        encoded = value.encode('utf-16-be', errors='surrogatepass')
        length = len(encoded)//2
        if length > 65535:
            raise ValueError(f'{self.format_name} text exceeds 65535 UTF-16 code units')
        self.buffer.extend(length.to_bytes(2, 'big'))
        self.buffer.extend(encoded)
