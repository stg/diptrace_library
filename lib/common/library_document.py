"""Typed, atomic record attachment for unplaced library document families."""
from .model import Document
from .structural_edits import assembly
from . import library_catalogue as catalogue
from .field_edits import (ReferenceValueEdit, prepare_reference_attachment, preview_slots)
from .references import UnresolvedReference


class LibraryDocument(Document):
    """Domains supply record definitions and their own relationship validators."""

    def _attachment_required(self, parent, node):
        field = parent.schema.fields.get(node.kind) if parent.schema else None
        if field is not None and field.getter is not None:
            raise ValueError('calculated/shared fields have no stored duplicate; use named assignment')
        return (self.representation in self._named_representations and parent.schema is not None
                and node.kind in parent.schema.children)

    def _validate_record(self, node):
        if node.schema and any(field.getter is not None and node.child(name) is not None
                               for name, field in node.schema.fields.items()):
            raise ValueError('calculated/shared fields must not have stored duplicates')
        super()._validate_record(node)

    def _plan_attachment(self, parent, root, structure):
        # Element.insert already supplies prospective ownership and restores the
        # detached proposal if any binding, type or graph preflight fails.
        with assembly(self):
            for node in root.walk(include_self=True):
                record = self._record_definition(node)
                if record is not None and node.schema is not record:
                    node.bind_schema(record)
                self._validate_record(node)
        base = self.references.plan_collections({parent: parent._child_sequence()}, parents={root: parent})
        with preview_slots(base.values):
            specifications, issues = self._attachment_reference_plans(root)
        return prepare_reference_attachment(self, base, specifications=specifications, issues=issues)

    def _attachment_reference_plans(self, root):
        return catalogue.plans(self, root._record_walk(include_self=True))

    def _apply_attachment(self, plan):
        if isinstance(plan, ReferenceValueEdit):
            plan.apply()
        else:
            self.references.apply_value_change(plan)

    def _prepare_reference_binding(self, reference):
        return catalogue.prepare_binding(super()._prepare_reference_binding(reference))

    def _prepare_value_edit(self, record, name, field, values, *, created):
        catalogue.check_resource_edit(self, record, name)
        return super()._prepare_value_edit(record, name, field, values, created=created)

    def _copy_specifications(self, root, specifications, issues):
        additions, unavailable = catalogue.plans(self, root._record_walk(include_self=True),
                                                 specifications=specifications, issues=issues)
        return [*specifications, *additions], (*issues, *(UnresolvedReference(*issue) for issue in unavailable))
