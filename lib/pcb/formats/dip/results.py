"""Persisted initial design-rule results and their object references."""
from ....common.model import SourceSpan
from .preamble import _fields


def read_initial_results(reader, board):
    if reader.header.version <= 34:
        return None
    drc = board.one('DRC')
    reader.field_into(drc, 'RealTimeMode', 'integer')
    reader.field_into(drc, 'DRCDone', 'boolean')
    errors = reader.add(board, 'DesignErrors')
    for index in range(reader.count('design errors')):
        start = reader.pos
        error = reader.add(errors, 'DesignError', index)
        reader.field_into(error, 'Enabled', 'boolean')
        _fields(reader, error, 'number', 'X Y Value Rule')
        _fields(reader, error, 'integer',
                'Type ObjectType1 ObjectType2 Object1 SubObject1 Point1 '
                'Object2 SubObject2 Point2 ExtObject1 ExtObject2')
        layers = reader.add(error, 'Lays')
        for _ in range(reader.count('error layer flags')):
            reader.record(layers, 'Item', 'boolean')
        error.source = SourceSpan('dip', start, reader.pos, reader.source)
    return errors
