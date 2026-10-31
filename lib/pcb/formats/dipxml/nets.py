"""PCB XML membership and supplied routing geometry before identity assembly."""
from ....common.xml_records import enum_value, length, point
from ...model.definitions import NET
from ..assembly.routing_inputs import NetInput
from ..errors import PcbError
from .pad_options import read_teardrop_params
from .keys import position, pad_position
from .routing import ROUTE_MODES, read_trace, resolve_pad_endpoints


def _teardrops(record, net, *, units, layers):
    target = net.add('Teardrops')
    seen = set()
    for index, source in enumerate(record.rows('Teardrops', 'Teardrop')):
        key = source.integer('Id', index)
        if key < 0:
            key = index
        if key in seen:
            raise PcbError(f'{source.node.path}: duplicate teardrop Id {key}')
        seen.add(key)
        item = target.add('Teardrop', key)
        item.add('Lay', position(source.integer('Lay'), layers, label='teardrop copper layer', path=source.node.path))
        for name, value in zip(('DrawX', 'DrawY'), point(source, units, ('DrawX', 'DrawY'))):
            item.add(name, value)
        points = item.add('Points')
        for index, vertex in enumerate(source.rows('Points', 'Point')):
            vertex.integer('Id', index)
            node = points.add('Point', index)
            for name, value in zip(('X', 'Y'), point(vertex, units)):
                node.add(name, value)
            vertex.finish()
        source.finish()


def read_nets(record, board, *, placements, units, layers, vias, classes, version):
    """Read named current data; source key maps remain importer state only."""
    target, prepared, trace_points, seen = board.add('Nets'), [], {}, set()
    for source in record.rows('Nets', 'Net'):
        key = source.integer('Id')
        if key in seen:
            raise PcbError(f'{source.node.path}: duplicate net Id {key}')
        seen.add(key)
        net = target.add('Net', source.text('Name', ''))
        net.add('Enabled', True)
        net.add('Number', key)
        net.add('NetClass', position(source.integer('NetClass', -1), classes,
                                    label='net class', path=source.node.path))
        for name, field in NET.fields.items():
            if name in ('Name', 'Enabled', 'Number', 'NetClass') or field.getter is not None:
                continue
            if field.kind == 'boolean':
                net.add(name, source.boolean(name, field.default))
            elif field.kind == 'integer':
                net.add(name, enum_value(source.value(name, field.default), ROUTE_MODES)
                        if name == 'RouteMode' else source.integer(name, field.default))
            elif field.kind == 'number':
                value = source.number(name) if source.has(name) else None
                net.add(name, length(value, units) if value is not None else field.default)
        pads = net.add('Pads')
        for member in source.rows('Pads', 'Item'):
            component, pad = member.integer('Comp'), member.integer('Pad')
            pads.add('Item', component, pad_position(component, pad, placements))
            member.finish()
        traces, inputs = net.add('Traces'), []
        for ordinal, row in enumerate(source.rows('Traces', 'Trace')):
            data = read_trace(row, units=units, layers=layers, vias=vias, version=version, ordinal=ordinal)
            if (key, data.previous_number) in trace_points:
                raise PcbError(f'{row.node.path}: duplicate trace Id {data.previous_number}')
            trace_points[key, data.previous_number] = data.points
            inputs.append(data)
            traces.append(data.trace)
        read_teardrop_params(source.take('TeardropParams'), net)
        _teardrops(source, net, units=units, layers=layers)
        source.finish()
        prepared.append(NetInput(net, tuple(inputs)))

    for net in prepared:
        for data in net.traces:
            trace = data.trace
            resolve_pad_endpoints(trace, placements, allow_missing_components=True)
            for end in (1, 2):
                suffix = str(end)
                mode = trace['Connected'+suffix]
                obj, sub, number = (trace[name+suffix] for name in ('Object', 'SubObject', 'Point'))
                if mode == 1:
                    points = trace_points.get((obj, sub), ())
                    if not 0 <= number < len(points):
                        raise PcbError(f'{trace.path}: unresolved trace point ({obj}, {sub}, {number})')
    return tuple(prepared)
