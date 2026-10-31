"""Current ordinary and differential trace geometry in PCB XML."""
from ....common.conversion import info
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import numeric, point_attributes, field
from ...model import routing_records
from ..output_validation import check_tree, field_value
from ..routing_projection import peer_backlink, point_memberships
from ..routing_values import XML_UNAVAILABLE_PHASE


def _endpoint(trace, result, end, keys):
    suffix = str(end)
    kind = trace['Connected'+suffix]
    obj, sub, point = (trace[name+suffix] for name in ('Object', 'SubObject', 'Point'))
    if kind == 'Pad':
        obj, sub = keys.pad(trace['Target'+suffix])
    for name, value in (('Connected', kind), ('Object', obj), ('SubObject', sub), ('Point', point)):
        set_attribute(result, name+suffix, value)


def project_trace(trace, *, keys, units, display_metrics=True, report=None):
    separate = trace.kind in ('PosTrace', 'NegTrace')
    check_tree(trace, routing_records.SEPARATE_TRACE if separate else routing_records.TRACE, destination='DIPXML')
    result = Element(trace.kind if separate else 'Trace')
    set_attribute(result, 'Id', trace['Id'])
    for end in (1, 2):
        _endpoint(trace, result, end, keys)
    set_attribute(result, 'Selected', field_value(trace, 'Selected'))
    if trace['GroupId'] >= 0:
        set_attribute(result, 'Group', trace['GroupId'])
    set_attribute(result, 'TraceId' if separate else 'PairSeparateTrace',
                  trace['TraceId'] if separate else peer_backlink(trace))
    points = result.add('Points')
    members = ((-1, -1) for _ in trace.select('Points/Point')) if separate else point_memberships(trace)
    unavailable = []
    for source, (center, subpoint) in zip(trace.select('Points/Point'), members):
        row = points.add('Point')
        set_attribute(row, 'Id', source['Id'])
        point_attributes(row, field_value(source, 'X'), field_value(source, 'Y'), units)
        for name in ('Lay', 'ViaStyle', 'Jumper', 'Meander', 'ShieldGroup', 'MeanderAngle', 'Arc', 'Selected'):
            set_attribute(row, name, field_value(source, name))
        if field_value(source, 'Width') != -1:
            width = field_value(source, 'Width')
            set_attribute(row, 'Width', numeric(units.length(width)) if not separate or display_metrics else width)
        set_attribute(row, 'Necked' if separate else 'PairNecked', field_value(source, 'PairNecked'))
        if not separate:
            set_attribute(row, 'PairPoint', center)
            set_attribute(row, 'PairSubPoint', subpoint)
        for name in ('PhaseFwd', 'PhaseBack'):
            value = source.get(name)
            if separate:
                if value is not None:
                    unavailable.append(source)
            else:
                value = XML_UNAVAILABLE_PHASE if value is None else value
                set_attribute(row, name, numeric(units.length(value)) if display_metrics else value)
    if unavailable:
        info(report, 'separate-phase-calculation', 'dipxml', 'Separate traces omit calculated phase lengths', unavailable,
             recoverability='route geometry remains; a receiving editor can recalculate phase data')
    if not separate:
        selected = result.add('ConnectedTeardrops')
        for member in trace.select('ConnectedTeardrops/Item'):
            field(selected, 'Item', member['Index'])
    return result
