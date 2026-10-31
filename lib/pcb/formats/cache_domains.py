"""Select the physical pad domain named by a slot's current symbol assignments."""
from ..model.library_relations import PIN_PAD_ROLE
from ...common.conversion import info
from .errors import PcbError


def physical_domain(slot, definitions):
    patterns = tuple(definition.one('Pattern') for definition in definitions
                     if definition.child('Pattern') is not None)
    linked = set()
    document = slot._owner()
    for definition in definitions:
        part = definition.one('Part')
        for reference in document.references.outgoing(part, role=PIN_PAD_ROLE):
            linked.add(reference.target.parent.parent)
        for issue in document.references._source_issues(part):
            if not any(item.field.kind == 'Number' and item.field.parent is not None
                       and item.field.parent.parent is part.child('Pins') for item in issue.indices):
                continue
            scopes = {parent.parent for parent in issue.collections or ()
                      if parent.kind == 'Pads' and parent.parent in patterns}
            if len(scopes) != 1:
                raise PcbError(f'{part.path}: unresolved pin assignment needs one owned physical scope')
            linked.update(scopes)
    if len(linked) > 1:
        raise PcbError(f'{slot.path}: output cannot combine pin assignments to multiple physical definitions')
    selected = next(iter(linked)) if linked else patterns[0] if patterns else None
    if selected is None or selected not in patterns:
        raise PcbError(f'{slot.path}: cached symbols require an owned physical footprint')
    return selected


def prepare_primary_order(board, *, destination, report=None):
    """Place the assigned physical domain first on a detached output view.

    A binary slot uses its first definition's pads for all symbol assignments.
    Reordering complete definitions preserves their independent symbol/footprint
    ownership, while derived variant numbers and references follow the move.
    """
    for slot in board.select('CacheLib/Slots/Slot'):
        definitions = slot.children('Definition')
        if not definitions:
            continue
        selected = physical_domain(slot, definitions)
        if selected.parent is not definitions[0]:
            selected.parent.move_to(slot, 0)
            info(report, 'cached-footprint-order', destination,
                 'Placed the assigned physical definition first in its cached component slot', (slot,),
                 recoverability='all symbol and footprint data, ownership and pin assignments remain')
