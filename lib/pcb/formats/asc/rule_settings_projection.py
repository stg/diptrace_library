"""Routing, current DRC and connectivity fields for the composed ASC settings.

The returned Settings contains this section's fields only. The document writer
must merge them with the separately projected display/sheet settings.
"""
from ....common.model import Element
from ...model import rule_records as rules
from ...model.routing_defaults import ROUTING
from ...model.settings_records import CONNECTIVITY
from .projection import check, fields, layer_rows, value
from .rule_settings import DRC_ALIASES, SIZE_FIELDS


_DRC_NAMES = {target: source for source, target in DRC_ALIASES.items()}


def _drc(source, output, layers):
    check(source, rules.DRC)
    fields(source, output, names={name: 'DRC_'+_DRC_NAMES.get(name, name) for name in source.schema.fields})
    uniform = value(source, 'AllLayers')
    clearances = output.add('DRC_LayClearances')
    for row in layer_rows(source, 'LayClearances', rules.COLLECTIONS['LayClearances'],
                          rules.DRC_CLEARANCE, layers, uniform=uniform):
        projected = clearances.add('DRC_LayClearance')
        fields(row, projected, names={name: 'DRC_'+name for name in row.schema.fields})
        details = row.child('ClearanceDetails')
        if details is not None:
            check(details, rules.DRC_DETAILS)
        for first in range(6):
            projected.add('pt', *(-1 if second < first or details is None else value(details,
                rules.CLEARANCE_KINDS[first]+'To'+rules.CLEARANCE_KINDS[second]) for second in range(7)))
    sizes = output.add('DRC_LaySizes')
    for row in layer_rows(source, 'LaySizes', rules.COLLECTIONS['LaySizes'],
                          rules.DRC_SIZE, layers, uniform=uniform):
        sizes.add('DRC_LaySize', *(value(row, name) for name in SIZE_FIELDS))


def project_rule_settings(board, layers):
    output = Element('Settings')
    settings = board.child('Settings')
    routing = settings.child('Routing') if settings is not None else None
    if routing is not None:
        check(routing, ROUTING)
        fields(routing, output)
        for name in ('TraceWidth', 'TraceClearance'):
            if (current := routing[name]) is not None:
                output.add(name, current)
    if (drc := board.child('DRC')) is not None:
        _drc(drc, output, layers)
    if (source := board.child('ConnectivityCheck')) is not None:
        check(source, CONNECTIVITY)
        fields(source, output, names={'Traces': 'Connectivity_Traces', 'Shapes': 'Connectivity_Shapes',
                                     'CopperPours': 'Connectivity_Pours'})
    return output
