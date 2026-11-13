"""Layer materials and pad delays supplied by the schema-43 extension."""
from .preamble import _fields


def read_layer_stack(reader, board):
    if reader.header.version <= 42:
        return None
    reader.field_into(board, 'LayerStackName', 'text')
    items = reader.add(board, 'LayerStackItems')
    for index in range(reader.count('layer stack items')):
        item = reader.add(items, 'LayerStackItem', index)
        reader.field_into(item, 'Lay', 'integer')
        material = reader.add(item, 'Material')
        reader.field_into(material, 'Name', 'text')
        reader.field_into(material, 'Type', 'integer')
        reader.field_into(material, 'VariableThickness', 'boolean')
        _fields(reader, material, 'number', 'Thickness Constant TraceWidth')
    for component in board.select('Components/Component'):
        for pad in component.select('Pattern/Pads/Pad'):
            reader.field_into(pad, 'SignalDelay', 'number')
    settings = board.one('Settings')
    _fields(reader, settings, 'boolean', 'StackLength SignalDelayLength')
    return items
