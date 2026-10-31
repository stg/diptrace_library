"""Prospective relationship queries for atomic graph mutation planning."""
from contextlib import contextmanager
from contextvars import ContextVar


_pending = ContextVar('design_prospective_references', default=None)


def pending_changes(graph):
    state = _pending.get()
    return state[1] if state is not None and state[0] is graph else None


@contextmanager
def preview_references(graph, changes):
    combined = dict(pending_changes(graph) or ())
    combined.update(changes)
    token = _pending.set((graph, combined))
    try:
        yield
    finally:
        _pending.reset(token)


def resolve_unavailable_reference(source, target, *, role, missing):
    """Replace an explicit unavailable selector and its scope guard atomically.

    This operates on an index-free identity role. The owning model supplies its
    target constraints and the field that represents the unavailable selection.
    """
    from .structural_edits import assembly, preview_structure
    document = source._owner()
    if document is None or missing.parent is not source:
        raise ValueError('unavailable reference must belong to an attached source')
    graph = document.references
    issues = tuple(issue for issue in graph._source_issues(source)
                   if issue.message.startswith(role+':'))
    children = tuple(child for child in source._child_sequence() if child is not missing)
    structure = graph.plan_collections({source: children}, parents={missing: None}, excluded_issues=issues)
    specifications = ((source, target, role, (), ()),) if target is not None else ()
    with preview_structure({source: children}, {missing: None}, {}):
        graph.check_removal(missing, excluding=issues, projected=True)
        additions = graph._prepare_additions(specifications, structure=structure, excluded_issues=issues)
    for issue in issues:
        graph.discard_issue(issue)
    with assembly(document):
        missing.detach()
    graph._apply_additions(additions)
    graph.finish_structure((source,), removed=(missing,))
