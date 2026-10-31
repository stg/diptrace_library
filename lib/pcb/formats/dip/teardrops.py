"""Teardrop parameters and saved geometry, without fill generation."""
from .preamble import _fields


def _parameters(reader, owner):
    params = owner.add('TeardropParams')
    _fields(reader, params, 'integer', 'PadVia Smd Trace TJunc')
    _fields(reader, params, 'number', 'PadViaWidth PadViaLength SmdWidth SmdLength TraceLength TJuncLength')


def read_teardrops(reader, board):
    if reader.header.version <= 48:
        return
    for pad in board.select('Components/Component/Pattern/Pads/Pad'):
        _parameters(reader, pad)
    for net in board.select('Nets/Net'):
        _parameters(reader, net)
        for trace in net.select('Traces/Trace'):
            connected = trace.add('ConnectedTeardrops')
            for _ in range(reader.count('trace teardrops')):
                reader.record(connected, 'Item', 'integer')
        teardrops = net.add('Teardrops')
        for index in range(reader.count('net teardrops')):
            teardrop = teardrops.add('Teardrop', index)
            reader.field(teardrop, 'Lay', 'integer')
            _fields(reader, teardrop, 'number', 'DrawX DrawY')
            points = teardrop.add('Points')
            for point_index in range(reader.count('teardrop polygon points')):
                point = points.add('Point', point_index)
                _fields(reader, point, 'number', 'X Y')
