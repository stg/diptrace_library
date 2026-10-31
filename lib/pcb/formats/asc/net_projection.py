"""Detached ASC nets and ordinary/separate trace geometry from current data."""
from ....common.conversion import warn
from ....common.model import Element
from ...model import definitions, membership, routing_records as routing, teardrops
from ..connection_types import CONNECTION_CODES
from ..output_indices import OutputIndices, pad_number
from ..routing_projection import peer_backlink, point_memberships, point_directions, via_geometry
from ..routing_values import ASC_UNAVAILABLE_PHASE
from . import routing_columns as columns
from .footprint_projection import points as project_points, project_parameters
from .projection import check, collection, fields, flag, rows, value


def warn_shield_group(point, report):
    if value(point, 'ShieldGroup') != point.schema.fields['ShieldGroup'].default:
        warn(report, 'trace-shield-group', 'asc',
             'PCB ASC point rows cannot represent shield-group membership', (point,))


def project_trace(trace, *, separate=False, report=None):
    """Write endpoint identities using the appropriate historical ASC spelling."""
    check(trace, routing.SEPARATE_TRACE if separate else routing.TRACE)
    output = Element('Line_'+trace.kind[:3] if separate else 'Line')
    for end in (1, 2):
        suffix = str(end)
        output.add('Connect'+suffix, trace['Object'+suffix])
        labels = ('ConnectL'+suffix, 'ConnectP'+suffix)
        if end == 2 and not separate:
            labels = labels[::-1]
        output.add(labels[0], trace['SubObject'+suffix])
        output.add(labels[1], trace['Point'+suffix])
        output.add('ConnectMode'+suffix, CONNECTION_CODES[trace['Connected'+suffix]])
        if not separate:
            output.add('ConnectedToLine'+suffix, flag(trace['Connected'+suffix] == 'Trace'))
            output.add('FreeEnd1' if end == 1 else 'FreeEnd21', flag(trace['Connected'+suffix] == 'Free'))
    fields(trace, output)
    output.add('Group', trace['GroupId'])
    output.add('OldNumber', trace['Id'])
    output.add('NetLine_Link' if separate else 'PairLine_Link',
               trace['TraceId'] if separate else peer_backlink(trace))
    actual = rows(trace.one('Points'), routing.COLLECTIONS['Points'], routing.POINT)
    projected = output.add('Points')
    members = ((-1, -1) for _ in actual) if separate else point_memberships(trace)
    names = columns.SEPARATE_POINT if separate else columns.POINT
    for point, direction, (center, subpoint) in zip(actual, point_directions(actual), members):
        warn_shield_group(point, report)
        data = {name: value(point, name) for name in names
                if name not in columns.COMPATIBILITY and name not in ('PairPoint', 'PairSubPoint')}
        data.update(via_geometry(point['Via']), Direction=direction, PairPoint=center, PairSubPoint=subpoint)
        for name in ('PhaseFwd', 'PhaseBack'):
            if data.get(name) is None:
                data[name] = ASC_UNAVAILABLE_PHASE
        projected.add('Point' if separate else 'pt',
                      *(flag(data[name]) if name in columns.FLAGS else data[name] for name in names))
    if not separate:
        selected = output.add('Teardrops_Connected')
        for item in collection(trace, 'ConnectedTeardrops', teardrops.MEMBERS, teardrops.MEMBER):
            selected.add('pt', item['Index'])
    return output


def project_nets(board, *, indices=None, report=None):
    indices = indices or OutputIndices(board)
    output = Element('Nets')
    styles = board.select('ViaStyles/ViaStyle')
    compatibility = via_geometry(styles[0] if styles else None)
    for net in rows(board.one('Nets'), definitions.COLLECTIONS['Nets'], definitions.NET):
        node = output.add('Net', net['Name'])
        fields(net, node, exclude=('Name', 'HiddenId', 'AllowLoops'), names={'HideRatlines': 'HideConnections'})
        node.add('Number', net['Number'])
        node.add('NetClass', indices.class_number(net['Class']))
        for name in ('ViaSize', 'ViaRing', 'ThroughVia'):
            node.add(name, flag(compatibility[name]) if name == 'ThroughVia' else compatibility[name])
        for name, rule in (('HiddenId', 'net-update-key'), ('AllowLoops', 'net-loop-setting')):
            if value(net, name) != net.schema.fields[name].default:
                warn(report, rule, 'asc', f'PCB ASC cannot represent net {name}', (net,))
        members = node.add('Component')
        for member in rows(net.one('Pads'), definitions.COLLECTIONS['NetPads'], membership.MEMBER):
            members.add('pt', member['ComponentIndex'], pad_number(member['Pad']))
        project_parameters(net, node)
        polygons = node.add('Teardrops')
        for polygon in collection(net, 'Teardrops', teardrops.TEARDROPS, teardrops.TEARDROP):
            target = polygons.add('Teardrop')
            fields(polygon, target)
            target.add('Layer', polygon['Lay'])
            source = polygon.child('Points')
            if source is not None:
                target.append(project_points(source, row_kind='Point'))
        traces = node.add('Lines')
        for trace in collection(net, 'Traces', routing.COLLECTIONS['Traces'], routing.TRACE):
            traces.append(project_trace(trace, report=report))
    return output
