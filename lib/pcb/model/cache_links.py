"""Active library selections reference slots, independently of capacity rows."""
from ...common.cache_refs import specifications, issue_collections
from ...common.field_edits import ReferenceValueEdit
from ...common.indexing import integer
from ...common.references import ReferenceError, OrdinalGuard, UnresolvedReference


ROLE = 'design-cache-slot'


def is_link(node, parent):
    return (node.kind == 'Link' and parent is not None and parent.kind == 'DesignCache_Links' and
            parent.parent is not None and parent.parent.kind == 'Board')


def validate_prefix(board):
    count, links = board.child('DesignCache_Count'), board.child('DesignCache_Links')
    if count is None and links is None:
        return
    if (count is None or len(count.arguments) != 1 or count.children() or
            (active := integer(count.values[0])) is None or active < -1 or
            active >= (len(links.children('Link')) if links is not None else 0)):
        raise ReferenceError('design cache prefix must be -1 or an available link position')
    if active >= 0:
        cache = board.child('CacheLib')
        if cache is None or cache.child('Slots') is None:
            raise ReferenceError('active design cache requires a library slot collection')


def validate_reference(document, reference, target):
    if reference.role != ROLE:
        return
    board = document.one('/Board')
    cache = board.child('CacheLib')
    slots = cache.child('Slots') if cache is not None else None
    link = reference.indices[0].field if len(reference.indices) == 1 else None
    count = board.child('DesignCache_Count')
    if (reference.source is not board or target.kind != 'Slot' or target.parent is not slots or
            link is None or not is_link(link, link.parent) or link.parent is not board.child('DesignCache_Links') or
            len(reference.guards) != 1 or not isinstance(reference.guards[0], OrdinalGuard) or
            reference.guards[0].field is not count or reference.guards[0].member is not link):
        raise ReferenceError('design cache link requires a slot in its own board library')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def _planned(document, board, *, only=None):
    specs, issues = [], []
    graph = document.references
    for specification in specifications(board):
        source, target, role, indices, guards = specification
        if only is not None and all(item.field is not only for item in indices):
            continue
        if any(graph.unresolved_slot(item.field, item.argument) for item in indices):
            continue
        if target is None:
            issues.append((source, role+': target index cannot be resolved', indices,
                           issue_collections(source, role), guards))
        else:
            specs.append(specification)
    return specs, issues


def edit_specifications(document, named):
    changed_count = any(record.kind == 'Board' and name == 'DesignCache_Count' for record, name in named)
    changed_links = {record for record, name in named
                     if name == 'SlotIndex' and record.parent is not None and is_link(record, record.parent)}
    if not changed_count and not changed_links:
        return [], []
    board = document.one('/Board')
    validate_prefix(board)
    if changed_count:
        return _planned(document, board)
    specifications, issues = [], []
    for link in changed_links:
        added, missing = _planned(document, board, only=link)
        specifications.extend(added)
        issues.extend(missing)
    return specifications, issues


def prepare_attachment(document, root, structure):
    board = document.one('/Board')
    validate_prefix(board)
    specs, issues = _planned(document, board, only=root)
    graph = document.references
    additions = graph._prepare_additions(specs, structure=structure)
    for source, message, indices, collections, guards in issues:
        graph._validate_reference_guards(UnresolvedReference(source, message, indices, collections, guards), {})
    return ReferenceValueEdit(document, additions, None, tuple(issues))
