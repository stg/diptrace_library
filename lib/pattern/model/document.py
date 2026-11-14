"""Pattern-library data editing over the shared model and reference graph."""
from ...common.library_document import LibraryDocument as BaseDocument
from ...common.references import ReferenceError
from ...common.field_edits import preview_slots
from ...common import unplaced_footprint_links as physical_links
from ...common import library_catalogue as catalogue
from . import records


class Document(BaseDocument):
    _representations = (*BaseDocument._representations, 'pattern', 'libxml')
    _named_representations = ('pattern',)

    def __init__(self, root=None, *, representation='pattern'):
        super().__init__(root, representation=representation)
        if representation == 'pattern':
            self._reference_validator = self._validate_relationships

    def _record_definition(self, node):
        from .schema import definition
        return definition(node)

    def _validate_relationship(self, reference, target):
        if reference.role in catalogue.ROLES:
            catalogue.validate_relationship(self, reference, target)
            return
        physical_links.validate_relationship(self, reference, target)

    def _prepare_value_edit(self, record, name, field, values, *, created):
        if (record.schema is records.GROUP and name == 'Enabled' and values[0].value is False
                and self.references.incoming(record, role=records.GROUP_ROLE)):
            raise ReferenceError('remove group membership before disabling the group')
        plan = super()._prepare_value_edit(record, name, field, values, created=created)
        if self._automatic_structure and ((record.kind in ('Shape', 'PadTerminal', 'Hole')
                and name in ('Type', 'Enabled')) or record.schema is records.DIMENSION
                and name in ('Enabled', 'Type', 'Connected1', 'Connected2', 'Point1', 'Point2')):
            with preview_slots(plan.projections.values):
                for reference in self.references._content_references(record.walk(include_self=True)):
                    self._validate_relationship(reference, reference.target)
        return plan

    def _unresolved_reference_fields(self, issue):
        if issue.message.partition(':')[0] in catalogue.ROLES:
            return catalogue.unresolved_fields(issue)
        return physical_links.unresolved_fields(issue)

    def _validate_unresolved_reference(self, issue):
        if issue.message.partition(':')[0] in catalogue.ROLES:
            catalogue.validate_unresolved(issue)
            return
        physical_links.validate_unresolved(issue)

    def _validate_reference_change(self, reference, target):
        if reference.role in catalogue.ROLES:
            catalogue.validate_change(self, reference, target)
            return
        self._validate_relationship(reference, target)

    def _validate_structural_references(self, references):
        for reference in references:
            self._validate_relationship(reference, reference.target)

    def _validate_relationships(self, document):
        for reference in document.references:
            document._validate_relationship(reference, reference.target)
        catalogue.validate_complete(document)
