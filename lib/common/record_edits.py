"""Scoped copy and removal plans over owned records and their relationships."""
from dataclasses import replace

from .references import OrdinalGuard, ReferenceError, Segment
from .reference_edits import preview_references
from .structural_edits import assembly, preview_structure, validate_child_change


def _owned(reference, nodes):
    fields = tuple(item.field for item in reference.indices)
    selected = reference.source in nodes or any(field in nodes for field in fields)
    if selected and any(field not in nodes for field in fields):
        raise ReferenceError('relationship fields cross the record boundary; edit that relationship explicitly')
    return selected


def _require_owned(document, node):
    if node is document.root or node.parent is None or node._owner() is not document:
        raise ValueError('operation requires an attached non-root record in this document')
    if node.parent.schema is not None and node.kind in node.parent.schema.fields:
        raise TypeError('use named assignment or deletion for fields; this operation edits owned records')


def _guards(guards, mapped):
    for guard in guards:
        values = {'field': mapped(guard.field)}
        if isinstance(guard, OrdinalGuard):
            values['member'] = mapped(guard.member)
        yield replace(guard, **values)


def copy_record(document, node, *, parent=None, index=None, fields=None):
    """Copy outgoing/owned links, remapping internal targets and keeping external ones."""
    _require_owned(document, node)
    parent = node.parent if parent is None else parent
    if parent._owner() is not document:
        raise ValueError('copy destination must belong to this document')
    if index is not None and not 0 <= index <= len(parent._child_sequence()):
        raise IndexError(index)
    graph = document.references
    nodes = tuple(node.walk(include_self=True))
    owned = set(nodes)
    references = tuple(link for link in graph._content_references(nodes) if _owned(link, owned))
    issues = tuple(issue for issue in graph._content_issues(nodes) if _owned(issue, owned))
    copied = node.clone()
    mapping = dict(zip(nodes, copied.walk(include_self=True)))
    mapped = lambda original: mapping.get(original, original)
    requested = {}
    for name, value in (fields or {}).items():
        copied[name] = value
        field = copied.one(name)
        requested.update((field._argument_owner(index), argument) for index, argument in enumerate(field.arguments))
    children = list(parent._child_sequence())
    children.insert(len(children) if index is None else index, copied)
    validate_child_change(parent, children, copied.kind)
    counts, ordinals = {}, {}
    for child in children:
        ordinals[child] = counts.get(child.kind, 0)
        counts[child.kind] = ordinals[child] + 1
    with preview_structure({parent: tuple(children)}, {copied: parent}, ordinals):
        document._prepare_copied_content(copied)
        structure = graph.plan_collections({parent: tuple(children)}, parents={copied: parent})
        specifications = []
        for link in references:
            target = (Segment(mapped(link.target.start), mapped(link.target.end)) if isinstance(link.target, Segment)
                      else mapped(link.target))
            specifications.append((mapped(link.source), target, link.role,
                tuple(replace(item, field=mapped(item.field)) for item in link.indices),
                tuple(_guards(link.guards, mapped))))
        copied_issues = tuple(replace(issue, source=mapped(issue.source),
            indices=tuple(replace(item, field=mapped(item.field)) for item in issue.indices),
            collections=None if issue.collections is None else tuple(mapped(owner) for owner in issue.collections),
            guards=tuple(_guards(issue.guards, mapped))) for issue in issues)
        specifications, copied_issues = document._copy_specifications(copied, specifications, copied_issues)
        additions = graph._prepare_additions(specifications, structure=structure)
        graph._validate_requested_values(requested, additions.projections, additions=additions.bindings)
        with preview_references(graph, {binding.reference.uid: binding.reference for binding in additions.bindings}):
            for issue in copied_issues:
                graph._validate_reference_guards(issue, additions.projections.values)
    with assembly(document):
        parent.insert(copied, index)
        graph._apply_additions(additions)
        for issue in copied_issues:
            graph.note(issue.source, issue.message, *issue.indices, collections=issue.collections,
                       guards=issue.guards, severity=issue.severity)
    graph.finish_structure((parent,))
    return copied


def remove_record(document, node):
    """Discard owned links and detach atomically, preserving all external users."""
    _require_owned(document, node)
    graph, parent = document.references, node.parent
    nodes = set(node.walk(include_self=True))
    references = tuple(link for link in graph._content_references(nodes) if _owned(link, nodes))
    issues = tuple(issue for issue in graph._content_issues(nodes) if _owned(issue, nodes))
    excluded = {link.uid for link in references}
    children = tuple(child for child in parent._child_sequence() if child is not node)
    validate_child_change(parent, children, node.kind)
    changes = dict.fromkeys(excluded)
    with preview_references(graph, changes):
        for link in references:
            document._validate_reference_removal(link)
        structure = graph.plan_collections({parent: children}, parents={node: None}, excluded=excluded, excluded_issues=issues)
        with preview_structure({parent: children}, {node: None}, {}):
            removed = graph.check_removal(node, excluding=excluded | set(issues), projected=True)
            plan = graph._plan_reference_changes(changes, structure=structure, excluded_issues=issues)
    with assembly(document):
        graph._discard_bindings(references)
        for issue in issues:
            graph.discard_issue(issue)
        node.detach()
        graph.apply_value_change(plan)
    graph.finish_structure((parent,), removed=removed)
    return node
