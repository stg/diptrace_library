"""Atomic named field edits over schematic values and identity relationships."""
from dataclasses import dataclass

from ...common.field_edits import preview_slots, named_field
from ...common.references import UnresolvedReference
from ..model.reference_scope import ReferenceScope
from ..model.refs import _specifications, reference_collections


@dataclass
class FieldEdit:
    document: object
    additions: object
    derived: object
    issues: tuple
    parent: object = None

    def apply(self):
        graph = self.document.references
        graph._apply_additions(self.additions)
        self.document._apply_field_change(self.derived)
        for source, message, indices, collections, guards in self.issues:
            graph.note(source, message, *indices, collections=collections, guards=guards)
        if self.parent is not None:
            graph.finish_structure((self.parent,))


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
            if owner.kind == 'Pad' and field_name == 'Id' and owner.parent is not None:
                from ..model.pad_keys import public_pad_keys
                public_pad_keys(owner.parent.parent)
            constrained = (owner.kind == 'Part' and field_name == 'PartType' or
                           owner.kind in ('Shape', 'PadTerminal') and field_name == 'Type' or
                           owner.kind == 'Hole' and field_name == 'Enabled' or
                           owner.kind == 'Dimension' and field_name in ('Point1', 'Point2'))
            if constrained:
                document._validate_structural_references(graph._record_references(owner))
        additions = graph._prepare_additions(specifications, structure=base.projections)
        requested = {field._argument_owner(index): value for index, value in enumerate(values)}
        graph._validate_requested_values(requested, additions.projections, additions=additions.bindings)
        for source, message, indices, collections, guards in issues:
            graph._validate_reference_guards(UnresolvedReference(source, message, indices, collections, guards), {})
    return FieldEdit(document, additions, base.derived, tuple(issues), record if created else None)
