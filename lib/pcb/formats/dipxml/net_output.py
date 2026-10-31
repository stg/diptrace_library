"""PCB XML nets, ordered members, current traces and supplied teardrop polygons."""
from ....common.conversion import info, warn
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import enum_text, field, numeric, point_attributes
from ...model import definitions
from ...model.pad_records import TEARDROP
from ..errors import PcbError
from ..output_validation import check_tree, field_value
from .route_output import project_trace
from .routing import ROUTE_MODES


def _teardrops(net, result, units):
    polygons = result.add('Teardrops')
    for source in net.select('Teardrops/Teardrop'):
        row = polygons.add('Teardrop')
        for name in ('Id', 'Lay'):
            set_attribute(row, name, source[name])
        point_attributes(row, field_value(source, 'DrawX'), field_value(source, 'DrawY'), units, names=('DrawX', 'DrawY'))
        points = row.add('Points')
        for index, vertex in enumerate(source.select('Points/pt')):
            point = points.add('Point')
            set_attribute(point, 'Id', index)
            point_attributes(point, vertex['X'], vertex['Y'], units)
    if (source := net.child('TeardropParams')) is not None:
        target = result.add('TeardropParams')
        for name in TEARDROP.fields:
            set_attribute(target, name, field_value(source, name))


def project_nets(board, *, keys, units, display_metrics=True, report=None):
    result = Element('Nets')
    for net in board.select('Nets/Net'):
        check_tree(net, definitions.NET, destination='DIPXML')
        if not field_value(net, 'Enabled'):
            raise PcbError(f'{net.path}: inactive net needs output normalization')
        row = result.add('Net')
        for name, value in (('Id', net['Number']), ('HiddenId', field_value(net, 'HiddenId')),
                            ('NetClass', keys.net_class(net['Class'])),
                            ('RouteMode', enum_text(field_value(net, 'RouteMode'), ROUTE_MODES)),
                            ('TraceColor', field_value(net, 'TraceColor'))):
            set_attribute(row, name, value)
        for name in ('Locked', 'HideRatlines', 'ShowLength', 'Highlighted', 'AllowLoops', 'CustomColor'):
            set_attribute(row, name, field_value(net, name))
        if field_value(net, 'MeanderGap') != -1:
            set_attribute(row, 'MeanderGap', numeric(units.length(field_value(net, 'MeanderGap'))))
        field(row, 'Name', net['Name'])
        members = row.add('Pads')
        for member in net.select('Pads/Item'):
            component, pad = keys.pad(member['Pad'])
            item = members.add('Item')
            set_attribute(item, 'Comp', component)
            set_attribute(item, 'Pad', pad)
        traces = row.add('Traces')
        for trace in net.select('Traces/Trace'):
            traces.append(project_trace(trace, keys=keys, units=units, display_metrics=display_metrics, report=report))
        _teardrops(net, row, units)
        for name in ('Width', 'Clearance'):
            if field_value(net, name) != -1:
                warn(report, 'net-route-preferences', 'dipxml', 'XML omits the net routing '+name+' preference', (net,),
                     recoverability='class rules and existing trace geometry remain; the independent preference is omitted')
        if field_value(net, 'ActiveLine') != -1 or field_value(net, 'ActivePoint') != -1:
            info(report, 'active-route-selection', 'dipxml', 'XML omits the active routing UI selection', (net,))
    return result
