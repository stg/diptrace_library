"""Independent schema-46 wire encoding from ordinary editable scalar values.

No source buffer, offsets or format object layout participate in encoding.
Values outside the format writer's representable domain raise instead of being
silently clamped. Numeric precision follows the measured binary64 writer rule.
"""
import math
from decimal import Decimal


NUMBER_LIMIT = 100_000


class Encoder:
    def __init__(self):
        self.buffer=bytearray()

    def integer(self,value):
        if isinstance(value,bool) or int(value)!=value or not -1_000_000<=value<=1_000_000:
            raise ValueError('DCH integer requires an integer in -1000000..1000000')
        self.buffer.extend((int(value)+1_000_000).to_bytes(3,'big'))

    def number(self,value):
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise TypeError('DCH number requires a numeric value')
        value=float(value)
        if not math.isfinite(value) or not -NUMBER_LIMIT<=value<=NUMBER_LIMIT:
            raise ValueError('DCH number requires a finite value in -100000..100000')
        units=round(value*10_000)+1_000_000_000
        self.buffer.extend(units.to_bytes(4,'big'))

    def boolean(self,value):
        if type(value) is not bool:
            raise TypeError('DCH boolean requires a bool')
        self.buffer.append(int(value))

    def color(self,value):
        if isinstance(value,bool) or int(value)!=value or not 0<=value<=0xffffff:
            raise ValueError('DCH color requires an integer in 0..0xffffff')
        self.buffer.extend(int(value).to_bytes(3,'little'))

    def text(self,value):
        if not isinstance(value,str):
            raise TypeError('DCH text requires a string')
        encoded=value.encode('utf-16-be',errors='surrogatepass')
        length=len(encoded)//2
        if length>65535:
            raise ValueError('DCH text exceeds 65535 UTF-16 code units')
        self.buffer.extend(length.to_bytes(2,'big'))
        self.buffer.extend(encoded)
