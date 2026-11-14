"""Standalone component data editing over the common tree infrastructure."""
from ...common.library_document import LibraryDocument as BaseDocument
from ...common.references import Index, ReferenceError, UnresolvedReference
from ...common.field_edits import preview_slots
from ...common.user_fields import USER_FIELD
from ...common import unplaced_footprint_links as physical_links
from ...common import unplaced_footprint_records as physical
from ...common.library_metadata import SUBFOLDER
from ...common import library_catalogue as catalogue
from . import records
from . import symbols
from . import text_fields
from .metadata import component_of, FOLDER_ROLE


class Document(BaseDocument):
    _representations = (*BaseDocument._representations, 'component', 'elixml')
    _named_representations = ('component',)

    def __init__(self, root=None, *, representation='component'):
        super().__init__(root, representation=representation)
        if representation == 'component':
            self._reference_validator = self._validate_relationships

    def _record_definition(self, node):
        from .schema import definition
        return definition(node)

    def _validate_relationship(self, reference, target):
        if reference.role in catalogue.ROLES:
            catalogue.validate_relationship(self, reference, target)
            return
        if reference.role in physical_links.ROLES:
            physical_links.validate_relationship(self, reference, target)
            return
        source = reference.source
        part = symbols.part_of(source)
        component = component_of(source)
        if reference.role == FOLDER_ROLE:
            library = self.root.child('Library')
            valid = (library is not None and source.schema is records.COMPONENT
                     and source.parent is library.child('Components')
                     and target.schema is SUBFOLDER and target.parent is library.child('Subfolders'))
        elif reference.role == symbols.GROUP_ROLE:
            valid = (source.schema in (symbols.PIN, symbols.DRAWING) and part is not None
                     and target.schema is physical.GROUP and target.parent is part.child('Groups')
                     and target['Enabled'])
        elif reference.role == symbols.PAD_ROLE:
            pattern = component.child('Pattern') if component is not None else None
            valid = (source.schema is symbols.PIN and pattern is not None
                     and target.schema is physical.PAD and target.parent is pattern.child('Pads'))
        elif reference.role == text_fields.ROLE:
            valid = (source.schema is symbols.DRAWING and source['Type'] == 10 and component is not None
                     and target.schema is USER_FIELD and target.parent is component.child('UserFields'))
        else:
            raise ReferenceError('unknown component relationship role: '+reference.role)
        if not valid or target._owner() is not self:
            raise ReferenceError('relationship target must belong to the same component and local scope')
        if any(link.uid != reference.uid for link in self.references.outgoing(source, role=reference.role)):
            raise ReferenceError('relationship already has a target')

    def _prepare_value_edit(self, record, name, field, values, *, created):
        if (record.schema is physical.GROUP and name == 'Enabled' and values[0].value is False
                and any(self.references.incoming(record, role=role)
                        for role in (physical.GROUP_ROLE, symbols.GROUP_ROLE))):
            raise ReferenceError('remove group membership before disabling the group')
        plan = super()._prepare_value_edit(record, name, field, values, created=created)
        if self._automatic_structure and ((record.kind in ('Shape', 'PadTerminal', 'Hole')
                and name in ('Type', 'Enabled')) or record.schema is physical.DIMENSION
                and name in ('Enabled', 'Type', 'Connected1', 'Connected2', 'Point1', 'Point2')):
            with preview_slots(plan.projections.values):
                for reference in self.references._content_references(record.walk(include_self=True)):
                    self._validate_relationship(reference, reference.target)
                for issue in self.references._content_issues(record.walk(include_self=True)):
                    self._validate_unresolved_reference(issue)
        if self._automatic_structure and record.schema is symbols.DRAWING and name in ('FontType', 'Type'):
            return text_fields.prepare_edit(self, record, field, values, created=created, base=plan)
        return plan

    def _prepare_reference_binding(self, reference):
        if reference.role == text_fields.ROLE:
            from dataclasses import replace
            field = reference.source.child('FontType')
            expected = (Index(field, offset=20),) if field is not None else ()
            if not expected or reference.indices and reference.indices != expected:
                raise ReferenceError('user-field selection requires its FontType projection')
            return replace(reference, indices=expected)
        return super()._prepare_reference_binding(reference)

    def _attachment_reference_plans(self, root):
        specifications, issues = super()._attachment_reference_plans(root)
        text, unavailable = text_fields.plans(self, root._record_walk(include_self=True))
        return [*specifications, *text], [*issues, *unavailable]

    def _copy_specifications(self, root, specifications, issues):
        specifications, issues = super()._copy_specifications(root, specifications, issues)
        claimed = {source for source, _, role, _, _ in specifications if role == text_fields.ROLE}
        claimed.update(issue.source for issue in issues if issue.message.startswith(text_fields.ROLE+':'))
        additions, unavailable = text_fields.plans(self,
            (node for node in root._record_walk(include_self=True) if node not in claimed))
        return [*specifications, *additions], (*issues, *(UnresolvedReference(*issue) for issue in unavailable))

    def _unresolved_reference_fields(self, issue):
        if issue.message.partition(':')[0] in catalogue.ROLES:
            return catalogue.unresolved_fields(issue)
        if issue.message.startswith(text_fields.ROLE+':'):
            return ((issue.source, issue.source.schema.fields['UserField']),)
        if issue.message.startswith(FOLDER_ROLE+':'):
            return ((issue.source, issue.source.schema.fields['Folder']),)
        for role, name in ((symbols.GROUP_ROLE, 'Group'), (symbols.PAD_ROLE, 'Pad')):
            if issue.message.startswith(role+':'):
                return ((issue.source, issue.source.schema.fields[name]),)
        return physical_links.unresolved_fields(issue)

    def _validate_unresolved_reference(self, issue):
        if issue.message.partition(':')[0] in catalogue.ROLES:
            catalogue.validate_unresolved(issue)
            return
        if issue.message.startswith(text_fields.ROLE+':'):
            source = issue.source
            component = component_of(source)
            if (source.schema is not symbols.DRAWING or source['Type'] != 10
                    or source.get('FontType', 0) < 20 or component is None
                    or any(collection is not component.child('UserFields') for collection in issue.collections)):
                raise ReferenceError('resolve or clear the unavailable user field before changing its scope')
            return
        if issue.message.startswith(FOLDER_ROLE+':'):
            library = self.root.child('Library')
            if (library is None or issue.source.schema is not records.COMPONENT
                    or issue.source.parent is not library.child('Components')
                    or issue.source.child('UnresolvedSubfolderIndex') is None
                    or any(scope is not library.child('Subfolders') for scope in issue.collections)):
                raise ReferenceError('resolve or clear the unavailable folder before changing its library scope')
            return
        for role, field, scope in ((symbols.GROUP_ROLE, 'UnresolvedGroupId', symbols.part_of),
                                   (symbols.PAD_ROLE, 'UnresolvedPadId', component_of)):
            if issue.message.startswith(role+':'):
                owner = scope(issue.source)
                if (owner is None or issue.source.child(field) is None
                        or any(scope(collection) is not owner for collection in issue.collections)):
                    raise ReferenceError('resolve or clear the unavailable selection before changing its scope')
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
        for source in document.root._record_walk(include_self=True):
            if source.schema is symbols.DRAWING and source['Type'] == 10 and source.get('FontType', 0) >= 20:
                if not document.references.outgoing(source, role=text_fields.ROLE) and not any(
                        issue.message.startswith(text_fields.ROLE+':')
                        for issue in document.references._source_issues(source)):
                    raise ReferenceError('unbound user-field selector; use named field or relationship editing')
