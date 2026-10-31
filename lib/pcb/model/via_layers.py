"""Style-owned copper exclusions, projected as ordinary pad layer records."""
from dataclasses import dataclass, replace

from ...common.model import Element
from ...common.references import ReferenceError
from ...common.reference_edits import pending_changes, preview_references
from ...common.structural_edits import (assembly, children_override, preview_structure,
                                        validate_child_change)
from . import board_rules, pad_records
from .static_via import controlled


def selected_style(component):
    return component['Via'] if controlled(component) else None


def excluded_layers(component):
    style = selected_style(component)
    if style is None:
        return None
    bounds = style['Span']
    layers = component._owner().one('/Board/Layers').children('Layer')
    if bounds is None:
        return ()
    first, last = (layer._ordinal() for layer in bounds)
    return tuple(layer for layer in layers if not first <= layer._ordinal() <= last)


def layer_targets(pad):
    return tuple(row['Layer'] for row in pad.select('BlindLayer/Item'))


def collections(component):
    pads = component.one('Pattern/Pads')
    yield pads, 'Pad'
    yield component._owner().one('/Board/Layers'), 'Layer'
    for pad in pads.children('Pad'):
        yield pad, 'BlindLayer'
        if (collection := pad.child('BlindLayer')) is not None:
            yield collection, 'Item'


def validate_layers(component):
    expected = excluded_layers(component)
    if expected is not None and layer_targets(component.one('Pattern/Pads/Pad')) != expected:
        raise ReferenceError('static-via layer exclusions are controlled by its style span; remove Via before editing them independently')


def validate_structure(component):
    pad = component.one('Pattern/Pads/Pad')
    collection = pad.child('BlindLayer')
    # Stack edits may change derived rows; direct edits must already agree.
    if (children_override(pad, 'BlindLayer') is not None or
            collection is not None and children_override(collection, 'Item') is not None):
        validate_layers(component)


def validate_layer_reference(document, reference, target):
    if not document._automatic_structure or reference.role != 'copper-layer':
        return
    row = reference.source
    collection = row.parent
    if row.kind != 'Item' or collection is None or collection.kind != 'BlindLayer':
        return
    pad = collection.parent
    pattern = pad.parent.parent if pad is not None and pad.parent is not None else None
    component = pattern.parent if pattern is not None else None
    if component is None or component.kind != 'Component' or selected_style(component) is None:
        return
    replacement = replace(reference, target=target) if target is not None else None
    with preview_references(document.references, {reference.uid: replacement}):
        validate_layers(component)


@dataclass
class _LayerProjection:
    document: object
    component: Element
    pad: Element
    collection: Element
    rows: tuple
    removed: tuple
    links: tuple
    additions: object

    def apply(self):
        graph = self.document.references
        graph._discard_bindings(self.links)
        with assembly(self.document):
            if self.collection.parent is None:
                self.pad.append(self.collection)
            for row in self.removed:
                row.detach()
            for index, row in enumerate(self.rows):
                if row.parent is None:
                    self.collection.insert(row, index)
                elif row._stored_ordinal() != index:
                    row.move_to(self.collection, index)
        graph._apply_additions(self.additions)
        graph.refresh_structure((self.component,))
        graph.finish_structure((self.pad, self.collection), removed=self.removed)


def _prepare(document, component):
    expected = excluded_layers(component)
    if expected is None:
        return None  # Releasing the style leaves its last current rows editable.
    pad = component.one('Pattern/Pads/Pad')
    if layer_targets(pad) == expected:
        return None
    graph = document.references
    collection = pad.child('BlindLayer')
    current = collection.children('Item') if collection is not None else ()
    if collection is None:
        collection = Element('BlindLayer').bind_schema(pad_records.COLLECTIONS['BlindLayer'])
    by_layer = {row['Layer']: row for row in current}
    rows, specifications = [], []
    for layer in expected:
        row = by_layer.get(layer)
        if row is None:
            row = Element('Item').bind_schema(pad_records.LAYER_MEMBER)
            specifications.append((row, layer, 'copper-layer', (), ()))
        rows.append(row)
    rows = tuple(rows)
    removed = tuple(row for row in current if row not in rows)
    links = tuple(link for row in removed for link in graph.outgoing(row, role='copper-layer'))
    removals = dict.fromkeys(link.uid for link in links)
    # Their scalar projections are already owned by the enclosing graph plan.
    # Re-evaluating an old binding here would ignore its proposed replacement.
    excluded = set(removals) | set(pending_changes(graph) or ())
    children = {collection: rows}
    parents = {row: None for row in removed}
    parents.update((row, collection) for row in rows)
    if collection.parent is None:
        children[pad] = (*pad._child_sequence(), collection)
        parents[collection] = pad
    ordinals = {}
    for parent, members in children.items():
        counts = {}
        for row in members:
            ordinals[row] = counts.get(row.kind, 0)
            counts[row.kind] = ordinals[row] + 1
        validate_child_change(parent, members, 'Item' if parent is collection else 'BlindLayer')
    # Compose the derived rows with the proposed graph/stack. Suppress recursive
    # scheduling while checking the derived projection itself.
    with assembly(document), preview_references(graph, removals), preview_structure(children, parents, ordinals):
        for row in removed:
            graph.check_removal(row, excluding=removals, projected=True)
        structure = graph.plan_collections(children, parents=parents, excluded=excluded)
        additions = graph._prepare_additions(specifications, structure=structure)
    return _LayerProjection(document, component, pad, collection, rows, removed, links, additions)


def plan_outputs(document, references):
    components = set()
    for reference in references:
        if reference.role == 'via-style' and reference.source.kind == 'Component':
            components.add(reference.source)
        elif reference.role in board_rules.SPAN_ROLES:
            components.update(link.source for link in document.references.incoming(reference.source, role='via-style')
                              if link.source.kind == 'Component')
    for component in components:
        if component._owner() is document and (plan := _prepare(document, component)) is not None:
            yield component, plan
