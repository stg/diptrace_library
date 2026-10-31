"""User policies and class-owned length results in public PCB XML."""
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import field, numeric
from ...model import length_matching
from ..errors import PcbError
from ..output_validation import check_tree, field_value


def _policy(owner, *, kind, keys, units):
    by_class = owner.kind == 'NetClass'
    source = owner.child('LengthResults') if by_class else owner
    if source is not None:
        check_tree(source, length_matching.RESULTS if by_class else length_matching.POLICY, destination='DIPXML')
    result = Element(kind)
    field(result, 'Name', owner['Name'])
    fixed = field_value(owner, 'FixedLength')
    delta = field_value(owner, 'LengthDelta' if by_class else 'Delta')
    if fixed != -1:
        set_attribute(result, 'FixedLength', numeric(units.length(fixed)))
    set_attribute(result, 'Delta', numeric(units.length(delta)))
    selected = owner if by_class else owner['Class'] if kind == 'MainLengthRule' else None
    set_attribute(result, 'Type', 'By NetClass' if selected is not None else 'By User')
    set_attribute(result, 'NetClass', keys.net_class(selected) if selected is not None else -1)
    set_attribute(result, 'AnyError', source['AnyError'] if source is not None else False)
    rows = result.add('Rules')
    connections = source.select('Rules/Rule') if source is not None else ()
    for connection in connections:
        row = rows.add('Rule')
        set_attribute(row, 'NetId', connection['NetId'])
        for end in (1, 2):
            component, pad = keys.pad(connection['Pad'+str(end)])
            set_attribute(row, 'Comp'+str(end), component)
            set_attribute(row, 'Pad'+str(end), pad)
        set_attribute(row, 'Length', numeric(units.length(field_value(connection, 'Length'))))
        set_attribute(row, 'Error', field_value(connection, 'Error'))
    return result


def project_length_rules(board, *, keys, units):
    """Return detached board children; class records are generated from classes."""
    result = Element('Board')
    if (main := board.child('MainLengthRule')) is not None:
        result.append(_policy(main, kind='MainLengthRule', keys=keys, units=units))
    rows = result.add('LengthRules')
    for owner in keys.indices.length_policies:
        rows.append(_policy(owner, kind='LengthRule', keys=keys, units=units))
    for net_class in board.select('NetClasses/NetClass'):
        if not field_value(net_class, 'CheckLength') and net_class.child('LengthResults') is not None:
            raise PcbError(f'{net_class.path}: inactive class length results need output normalization')
    return result
