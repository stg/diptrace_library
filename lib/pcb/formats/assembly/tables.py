"""Consume documentation row positions without retaining resolved indices."""
from ....common.conversion import import_notice
from ....common.references import Index
from ...model import table_relations as model
from ..errors import PcbError


def prepare_rows(board, components):
    by_position = dict(enumerate(components))
    prepared = []
    for table in board.select('Tables/Table'):
        if not table.get('Enabled', True):
            continue
        for member in table.select('RowComponents/Row/Item'):
            if len(member.values) != 1:
                raise PcbError('table row component requires one component position')
            number = member.values[0]
            if isinstance(number, bool) or not isinstance(number, int):
                raise PcbError('table row component requires an integer component position')
            target = by_position.get(number)
            member.set_values()
            if number >= 0 and target is None:
                member.add(model.MISSING, number)
            prepared.append((member, target))
    return prepared


def bind_rows(document, prepared):
    unresolved = []
    for member, target in prepared:
        if target is not None:
            document.references.bind(member, target, role=model.ROLE, preserve=True)
        elif (missing := member.child(model.MISSING)) is not None:
            document.references.note(member, model.ROLE+': component position cannot be resolved',
                Index(missing), collections=(document.one('/Board/Components'),))
            unresolved.append(member)
    if unresolved:
        import_notice('warning', 'unresolved-table-component',
            'Table rows refer to unavailable components', unresolved,
            recoverability='the unresolved positions remain explicit until replaced or disconnected')
