"""Layer materials and pad delays supplied by the schema-43 extension."""
from .preamble import _fields


def read_layer_stack(reader, board):
    if reader.header.version <= 42:
        return None
    reader.field(board, 'LayerStackName', 'text')
    items = board.add('LayerStackItems')
    for index in range(reader.count('layer stack items')):
        item = items.add('LayerStackItem', index)
        reader.field(item, 'Lay', 'integer')
        material = item.add('Material')
        reader.field(material, 'Name', 'text')
        reader.field(material, 'Type', 'integer')
        reader.field(material, 'VariableThickness', 'boolean')
        _fields(reader, material, 'number', 'Thickness Constant TraceWidth')
    for component in board.select('Components/Component'):
        for pad in component.select('Pattern/Pads/Pad'):
            reader.field(pad, 'SignalDelay', 'number')
    settings = board.one('Settings')
    _fields(reader, settings, 'boolean', 'StackLength SignalDelayLength')
    return items
