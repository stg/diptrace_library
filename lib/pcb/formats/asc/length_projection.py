"""Current user/class length policies into detached ASC connection records."""
from ....common.model import Element
from ...model import length_matching as model
from ..errors import PcbError
from ..output_indices import OutputIndices, pad_endpoint
from .projection import check, collection, flag, value


def _connections(source, output):
    if source is None:
        return
    for connection in collection(source, 'Rules', model.CONNECTIONS, model.CONNECTION):
        output.add('pt', connection['NetId'], *pad_endpoint(connection, 1),
                   *pad_endpoint(connection, 2), value(connection, 'Length'),
                   flag(value(connection, 'Error')))


def _user(source, kind, *, indices):
    check(source, model.POLICY)
    error = flag(source['AnyError'])
    selected = source['Class'] if kind == 'MainLengthRule' else None
    output = Element(kind, value(source, 'Name'), value(source, 'FixedLength'),
                     value(source, 'Delta'), error, error, indices.class_number(selected), int(selected is not None))
    _connections(source, output)
    return output


def project_length_rules(board, *, indices=None):
    """Regenerate class policies from their class; keep user policy order separate."""
    output = Element('Board')
    indices = indices or OutputIndices(board)
    if (main := board.child('MainLengthRule')) is not None:
        output.append(_user(main, 'MainLengthRule', indices=indices))
    collection(board, 'LengthRules', model.POLICIES, model.POLICY)
    result = output.add('LengthRules')
    for owner in indices.length_policies:
        if owner.schema is model.POLICY:
            result.append(_user(owner, 'LengthRule', indices=indices))
            continue
        source = owner.child('LengthResults')
        if source is not None:
            check(source, model.RESULTS)
        error = flag(source['AnyError'] if source is not None else False)
        record = result.add('LengthRule', value(owner, 'Name'), value(owner, 'FixedLength'),
                            value(owner, 'LengthDelta'), error, error, indices.class_number(owner), 1)
        _connections(source, record)
    for owner in board.select('NetClasses/NetClass'):
        if owner.child('LengthResults') is not None and not value(owner, 'CheckLength'):
            raise PcbError(f'{owner.path}: inactive class length results require normalization')
    return output
