"""Local text refresh operations shared by document-specific label policies."""
from .references import ReferenceError


def check_refresh(document, changes):
    """Preflight single-line replacements without removing referenced rows."""
    changes = [(owner, lines, rows) for owner, lines, rows in changes if len(rows) != 1]
    graph = document.references
    graph._check_collection_changes(lines if lines is not None else owner
                                    for owner, lines, _ in changes)
    removed = {node for _, _, rows in changes for row in rows[1:]
               for node in row.walk(include_self=True)}
    if any(graph.incoming(node) or graph.outgoing(node) or
            graph.guard_consumers(node) or graph.unresolved_guard_consumers(node) or any(
            graph.manages(node, index) or graph.unresolved_slot(node, index) or
            graph.value_consumers(node, index) or graph.guard_consumers(node, index) or
            graph.unresolved_guard_consumers(node, index)
            for index in range(len(node.arguments))) for node in removed):
        raise ReferenceError('text refresh would remove a referenced text row')


def replace_line(owner, lines, rows, text):
    """Apply one preflighted replacement, keeping the first row's identity."""
    if lines is None:
        lines = owner.add('TextLine')
    if rows:
        rows[0].set_values(text)
        for row in rows[1:]:
            row.detach()
    else:
        lines.add('pt', text)
