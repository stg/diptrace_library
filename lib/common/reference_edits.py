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


def assign_indexed_reference(source, target, *, role, field_name, offset=0, none_value=-1):
    """Select an identity or clear its scalar selector as one checked edit.

    The stored scalar is the sole serialization fact. While selected, the graph
    maintains it from the target's ordinal. A literal fallback becomes editable
    again only after all dependent values and guards accept the combined change.
    """
    from .field_edits import field_proposal
    from .model import Value
    from .references import Index, ReferenceError
    from .structural_edits import assembly
    document = source._owner()
    if document is None:
        raise ReferenceError('attach the record before selecting a relationship')
    graph = document.references
    links = graph.outgoing(source, role=role)
    if len(links) > 1:
        raise ReferenceError('indexed selection has multiple targets')
    if links and target is not None:
        if links[0].target is not target:
            graph.retarget(links[0], target)
        return
    issues = tuple(issue for issue in graph._source_issues(source) if issue.message.startswith(role+':'))
    value = target._ordinal()+offset if target is not None else none_value
    definition = source.schema.fields[field_name]
    definition.validate(value)
    values = (Value.of(value),)
    existing = source.child(field_name)
    # A new binding must see the previous scalar so its ordinal projection
    # schedules every dependent copy. Previewing the final value here would
    # hide that change from the dependency planner.
    proposal = existing.arguments if target is not None and existing is not None else values
    with field_proposal(source, field_name, proposal) as (field, created):
        structure = (graph.plan_collections({source: source._child_sequence()}, parents={field: source},
                                            excluded_issues=issues) if created else None)
        if target is not None:
            binding = graph._prepare_binding(source, target, (Index(field, offset=offset),), role=role,
                guards=(), preserve=False, structure=structure, excluded_issues=issues)
        else:
            changes = {link.uid: None for link in links}
            with preview_references(graph, changes):
                for link in links:
                    document._validate_reference_removal(link)
                plan = graph._plan_reference_changes(changes, structure=structure, excluded_issues=issues,
                                                     values={field._argument_owner(0): values[0]})
    if target is not None:
        if created:
            with assembly(document):
                source.append(field)
        graph._register_binding(*binding, preserve=False)
    else:
        for issue in issues:
            graph.discard_issue(issue)
        graph._discard_bindings(links)
        with assembly(document):
            if created:
                source.append(field)
            else:
                field.set_values(*values)
        graph.apply_value_change(plan)
    if created:
        graph.finish_structure((source,))


def assign_projected_reference(source, target, *, role, indices=(), clear_values):
    """Select a target or replace its stored projections in one checked edit.

    Unlike an ordinal choice, a named selection can project several facts, such
    as a declared key and its label. Existing fields retain their previous values
    during new binding, so the dependency planner sees every actual change.
    """
    from .field_edits import preview_values
    from .model import Value
    from .references import ReferenceError
    from .structural_edits import assembly
    document = source._owner()
    if document is None:
        raise ReferenceError('attach the record before selecting a relationship')
    graph = document.references
    links = graph.outgoing(source, role=role)
    if len(links) > 1:
        raise ReferenceError('selection has multiple targets')
    if links and target is not None:
        if links[0].target is not target:
            graph.retarget(links[0], target)
        return
    issues = tuple(issue for issue in graph._source_issues(source) if issue.message.startswith(role+':'))
    if target is not None:
        prepared = graph._prepare_binding(source, target, indices, role=role, guards=(), preserve=False,
                                           excluded_issues=issues)
        graph._register_binding(*prepared, preserve=False)
        return
    changes = []
    for name, value in clear_values.items():
        source.schema.fields[name].validate(value)
        changes.append((source.one(name), (Value.of(value),)))
    removals = {link.uid: None for link in links}
    overrides = {field._argument_owner(0): values[0] for field, values in changes}
    with preview_values(changes), preview_references(graph, removals):
        for link in links:
            document._validate_reference_removal(link)
        plan = graph._plan_reference_changes(removals, values=overrides, excluded_issues=issues)
    for issue in issues:
        graph.discard_issue(issue)
    graph._discard_bindings(links)
    with assembly(document):
        for field, values in changes:
            field.set_values(*values)
    graph.apply_value_change(plan)


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
