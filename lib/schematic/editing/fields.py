"""Atomic named field edits over schematic values and identity relationships."""
from ...common.field_edits import preview_slots, named_field, prepare_reference_edit
from ..model.reference_scope import ReferenceScope
from ..model.refs import _specifications, reference_collections


def prepare_field_edit(document, record, name, field, values, *, created, base):
    graph = document.references
    roots = tuple(dict.fromkeys((field, *(owner for owner, _ in base.projections.values))))
    with preview_slots(base.projections.values):
        scope = ReferenceScope(roots[0], additional=roots[1:])
        specifications, issues = [], []
        for source, target, role, indices, guards in _specifications(document, scope=scope):
            if any(item is None for item in indices):
                continue
            if any(graph.unresolved_slot(item.field, item.argument) for item in indices):
                continue
            if target is None:
                collections = reference_collections(document, source, role, authoring=True)
                issues.append((source, f'{role}: target index cannot be resolved', indices, collections, guards))
            else:
                specifications.append((source, target, role, indices, guards))
        named = {(record, name)} | {found for (node, argument) in base.projections.values
                                   if (found := named_field(node, argument)) is not None}
        for owner, field_name in named:
            if owner.kind == 'Part' and field_name in ('RefDes', 'Enabled', 'PartType'):
                from ..model.refdes import validate_edit
                validate_edit(document, owner, field_name)
            if owner.kind == 'Pad' and field_name == 'Id' and owner.parent is not None:
                from ..model.pad_keys import public_pad_keys
                public_pad_keys(owner.parent.parent)
            constrained = (owner.kind == 'Part' and field_name == 'PartType' or
                           owner.kind in ('Shape', 'PadTerminal') and field_name == 'Type' or
                           owner.kind == 'Hole' and field_name == 'Enabled' or
                           owner.kind == 'Dimension' and field_name in ('Point1', 'Point2'))
            if constrained:
                document._validate_structural_references(graph._record_references(owner))
        return prepare_reference_edit(document, record, field, values, created=created, base=base,
                                      specifications=specifications, issues=issues)
