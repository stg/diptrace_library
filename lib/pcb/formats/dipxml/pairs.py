"""Differential XML geometry enters the same PCB routing identity assembler."""
from ....common.model import Element
from ....common.xml_records import enum_value, point
from .keys import pad_position, position
from .routing import ROUTE_MODES, read_trace, resolve_pad_endpoints


CENTER_TYPES = ('Paired', 'Turn', 'Connection', 'Unpaired')


def _side_points(record, center, side, *, units, layers, vias):
    collection = center.add(side+'Points')
    for index, source in enumerate(record.rows(side+'Points', side+'Point')):
        source.integer('Id', index)
        node = collection.add(side+'Point', index)
        for name, value in zip(('X', 'Y'), point(source, units)):
            node.add(name, value)
        node.add('Lay', position(source.integer('Lay', -1), layers, label='side-point layer', path=source.node.path))
        node.add('ViaStyle', position(source.integer('ViaStyle', -1), vias, label='side-point via', path=source.node.path))
        for name in ('Necked', 'Selected', 'Arc'):
            node.add(name, source.boolean(name, False))
        node.add('Meander', source.integer('Meander', 0))
        node.add('ShieldGroup', source.integer('ShieldGroup', -1))
        node.add('MeanderAngle', source.number('MeanderAngle', 0))
        source.finish()


def _centers(record, segment, *, units, layers, vias):
    collection = segment.add('CenterPoints')
    for index, source in enumerate(record.rows('CenterPoints', 'CenterPoint')):
        source.integer('Id', index)
        node = collection.add('CenterPoint', index)
        for name, value in zip(('X', 'Y'), point(source, units)):
            node.add(name, value)
        node.add('Lay', position(source.integer('Lay', -1), layers, label='center layer', path=source.node.path))
        node.add('ViaStyle', position(source.integer('ViaStyle', -1), vias, label='center via', path=source.node.path))
        node.add('Type', enum_value(source.value('Type', 'Paired'), CENTER_TYPES))
        node.add('PosTraceSide', source.integer('PosTraceSide', -1))
        for side in ('Pos', 'Neg'):
            node.add(side+'ShieldGroup', source.integer(side+'ShieldGroup', -1))
        for name in ('Necked', 'Selected', 'PhaseError'):
            node.add(name, source.boolean(name, False))
        for side in ('Pos', 'Neg'):
            for end in ('Start', 'End'):
                name = side+'Trace_'+end+'Point'
                node.add(name, source.integer(name, -1))
            _side_points(source, node, side, units=units, layers=layers, vias=vias)
        source.finish()


def read_pairs(record, board, *, placements, units, layers, vias, classes, version, removed=False):
    kind = 'RemovedDifferentialPair' if removed else 'DifferentialPair'
    collection, separate = board.add(kind+'s'), []
    for index, source in enumerate(record.rows(kind+'s', kind)):
        pair = collection.add(kind, index)
        pair.add('Number', source.integer('Id', index))
        pair.add('Enabled', source.boolean('Enabled', True))
        pair.add('Name', source.text('Name', ''))
        for side in ('Pos', 'Neg'):
            pair.add(side+'Net', source.integer(side+'Net'))
        pair.add('NetClass', position(source.integer('NetClass', -1), classes,
                                      label='pair net class', path=source.node.path))
        pair.add('CustomColor', source.boolean('CustomColor', False))
        pair.add('TraceColor', source.integer('TraceColor', 0))
        if not removed:
            pair.add('AutoPadPoints', source.boolean('AutoPadPoints', True))
            pair.add('RouteMode', enum_value(source.value('RouteMode', 'Ratlines'), ROUTE_MODES))
        pads = pair.add('PadPoints')
        for ordinal, item in enumerate(source.rows('PadPoints', 'PadPoint')):
            item.integer('Id', ordinal)  # The row's output counter is not its selection domain.
            node = pads.add('PadPoint', ordinal)
            for side in ('Pos', 'Neg'):
                component, pad = item.integer(side+'Comp', -1), item.integer(side+'Pad', -1)
                node.add(side+'Comp', component)
                node.add(side+'Pad', -1 if (component, pad) == (-1, -1) else pad_position(component, pad, placements))
            item.finish()
        segments = pair.add('Segments')
        for ordinal, item in enumerate(source.rows('Segments', 'Segment')):
            item.integer('Id', ordinal)
            node = segments.add('Segment', ordinal)
            for name in ('PosTrace', 'NegTrace', 'StartPoint', 'EndPoint', 'StartSegment', 'EndSegment'):
                node.add(name, item.integer(name, -1))
            _centers(item, node, units=units, layers=layers, vias=vias)
            item.finish()
        for side in (() if removed else ('Pos', 'Neg')):
            traces = pair.add(side+'SeparateTraces')
            for ordinal, item in enumerate(source.rows(side+'SeparateTraces', side+'Trace')):
                data = read_trace(item, units=units, layers=layers, vias=vias, version=version,
                                  ordinal=ordinal, side=side)
                resolve_pad_endpoints(data.trace, placements)
                traces.append(data.trace)
                separate.append(data)
        source.finish()
    return tuple(separate)
