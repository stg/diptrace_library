"""The symbol-parameter prefix of a standalone component part."""
from ....common.symbol_codec import read_symbol_parameters
from ....common.symbol_records import SYMBOL


def read_part_parameters(reader, parts):
    """Consume only this prefix; the physical/pin/drawing payload follows it."""
    part = reader.add(parts, 'Part')
    read_symbol_parameters(reader, part)
    return part.bind_schema(SYMBOL)
