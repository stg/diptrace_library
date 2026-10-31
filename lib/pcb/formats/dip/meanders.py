"""Stored length-tuning geometry; importing it does not calculate routing."""


def _point(reader, point, *, side=False):
    reader.field(point, 'Meander', 'integer')
    reader.field(point, 'MeanderAngle', 'number')
    if side:
        reader.field(point, 'Arc', 'boolean')


def _side_points(reader, pair):
    for center in pair.select('Segments/Segment/CenterPoints/CenterPoint'):
        for collection, kind in (('PosPoints', 'PosPoint'), ('NegPoints', 'NegPoint')):
            for point in center.select(collection+'/'+kind):
                _point(reader, point, side=True)


def read_meanders(reader, board):
    if reader.header.version <= 43:
        return
    for net in board.select('Nets/Net'):
        reader.field(net, 'MeanderGap', 'number')
        for point in net.select('Traces/Trace/Points/Point'):
            _point(reader, point)
    for pair in board.select('DifferentialPairs/DifferentialPair'):
        _side_points(reader, pair)
        for collection, kind in (('PosSeparateTraces', 'PosTrace'), ('NegSeparateTraces', 'NegTrace')):
            for point in pair.select(collection+'/'+kind+'/Points/Point'):
                _point(reader, point)
    for pair in board.select('RemovedDifferentialPairs/RemovedDifferentialPair'):
        _side_points(reader, pair)
