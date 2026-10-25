"""Schematic document operations over the shared editable tree."""
from ...common.model import (Document as BaseDocument, Element, Value, SourceSpan, IncompleteDocumentError)
from ...common.conversion import (export_diagnostics, import_diagnostics)
from ..formats.capabilities import ASC, DCH, DCHXML


class Document(BaseDocument):
    _representations = (*BaseDocument._representations, 'schematic', 'dchxml')
    _named_representations = ('schematic',)

    def refdes(self, prefix):
        """Return a live numbered-family view of enabled physical components.

        All sheets participate. Cached definitions and disabled records do not
        occupy names. Matching returns records; numbering methods return names.
        """
        from ...common.refdes import RefDesFamily
        from .refdes import components
        if self.representation != 'schematic':
            raise TypeError('RefDes helpers require the shared schematic model; use read() or as_schematic()')
        return RefDesFamily(prefix, lambda: components(self),
            get_refdes=lambda part: part['RefDes'])

    def _copy_specifications(self, root, specifications, issues):
        if self.representation != 'schematic' or self._reference_validator is None:
            return specifications, issues
        from ...common.references import ReferenceError, UnresolvedReference
        from .reference_scope import ReferenceScope
        from .refs import _specifications, reference_collections
        graph = self.references
        reserved = {item.field._argument_owner(item.argument): role
                    for _, _, role, indices, _ in specifications for item in indices}
        missing = {item.field._argument_owner(item.argument) for issue in issues for item in issue.indices}
        selected, unresolved = list(specifications), list(issues)
        for source, target, role, indices, guards in _specifications(self, scope=ReferenceScope(root)):
            if any(item is None or graph.unresolved_slot(item.field, item.argument) for item in indices):
                continue
            slots = {item.field._argument_owner(item.argument) for item in indices}
            if slots.intersection(missing):
                continue
            if slots and slots.issubset(reserved):
                if any(reserved[slot] != role for slot in slots):
                    raise ReferenceError('copied field already belongs to a different relationship')
                continue
            if target is None:
                unresolved.append(UnresolvedReference(source, f'{role}: target index cannot be resolved', indices,
                    reference_collections(self, source, role, authoring=True), guards))
            else:
                selected.append((source, target, role, indices, guards))
        return selected, tuple(unresolved)

    def _prepare_copied_content(self, root):
        if self.representation == 'schematic':
            from .refdes import validate_name
            validate_name(self, root)
            from .activation import refresh_new_text
            refresh_new_text(self, root)
            if root.kind == 'Pad' and root.parent is not None and root.parent.kind == 'Pads':
                from .pad_keys import public_pad_keys
                public_pad_keys(root.parent.parent)

    def _calculation_outputs(self, slot):
        if not self._automatic_structure or self.representation != 'schematic':
            return ()
        from .symbol_text import dependent_shapes, calculation_outputs
        return tuple(calculation_outputs(dependent_shapes(self, slot)))

    def _plan_calculations(self, slot):
        if not self._automatic_structure or self.representation != 'schematic':
            return ()
        from .symbol_text import dependent_shapes, plan_symbol_text
        shapes = dependent_shapes(self, slot, include_outputs=True)
        if not shapes:
            return ()
        parts = tuple(dict.fromkeys(shape.parent.parent for shape in shapes))
        return tuple((plan[0], plan, tuple(self._field_plan_values((plan,))))
                     for plan in plan_symbol_text(self, parts=parts, shapes=shapes))

    def _structural_calculation_slots(self, nodes):
        if self.representation == 'schematic' and self._automatic_structure:
            from .symbol_text import is_bound_label
            for node in nodes:
                if node._owner() is self and node.kind == 'Shape' and is_bound_label(node):
                    yield node.one('FontType')._argument_owner(0)

    def _apply_calculations(self, plans):
        from ...common.structural_edits import assembly
        from .definitions import establish_records
        with assembly(self):
            self._apply_field_change(plans)
            for shape, *_ in plans:
                establish_records(shape)

    def _prepare_value_edit(self, record, name, field, values, *, created):
        active = self._automatic_structure and self.representation == 'schematic' and self._reference_validator is not None
        if active:
            from .symbol_text import is_bound_label
            shape = (record.parent.parent if record.parent is not None and record.parent.kind == 'TextLine'
                     else record if record.kind == 'Shape' else None)
            if shape is not None and is_bound_label(shape) and (name == 'Text' or
                    name == 'ShowPart' and shape.scalar('FontType') in (1, 2)):
                raise TypeError(f'{name} is calculated for a field-bound label; edit its source field or use literal text')
        if active and created and self._attachment_required(record, field):
            from ...common.structural_edits import assembly
            from .definitions import establish_records
            with assembly(self):
                establish_records(field)
        base = super()._prepare_value_edit(record, name, field, values, created=created)
        if not active:
            return base
        from ..editing.fields import prepare_field_edit
        return prepare_field_edit(self, record, name, field, values, created=created, base=base)

    def _attachment_required(self, parent, node):
        if self.representation != 'schematic' or self._reference_validator is None:
            return False
        ancestor = parent
        while ancestor is not None and ancestor.kind != 'Schematic':
            ancestor = ancestor.parent
        return ancestor is self.root.child('Schematic')

    def _plan_attachment(self, parent, node, structure):
        from .activation import prepare_attachment
        return prepare_attachment(self, parent, node, structure)

    def _apply_attachment(self, plan):
        plan.apply()

    def _validate_reference_change(self, reference, target):
        from .membership import validate_retarget
        validate_retarget(self, reference, target)
        if self._automatic_structure and (reference.role != 'net-member' or reference.indices):
            from dataclasses import replace
            self._validate_structural_references((replace(reference, target=target),))

    def _validate_move(self, node, parent):
        from .membership import validate_move
        validate_move(self, node, parent)
        destination = parent._owner()
        if destination is not None and destination is not self and destination.representation == 'schematic':
            from .refdes import validate_name
            validate_name(destination, node, parent=parent)

    def _validate_reference_removal(self, reference):
        from .membership import validate_removal
        validate_removal(self, reference)

    def _validate_structural_references(self, references):
        if self.representation != 'schematic':
            return
        from .refs import connectivity_mismatches, raise_connectivity_mismatch
        mismatches = connectivity_mismatches(self, references=references)
        if mismatches:
            raise_connectivity_mismatch(*mismatches[0])

    def _structural_dependents(self, nodes):
        from .membership import MEMBER
        graph = self.references
        result = {}
        for node in nodes:
            if node.schema is not MEMBER:
                continue
            for member in graph.outgoing(node, role='net-member'):
                for reference in graph.incoming(member.target):
                    result[reference.uid] = reference
                for reference in graph.property_consumers(member.target, 'NetNumber'):
                    result[reference.uid] = reference
        return tuple(result.values())

    def _plan_field_change(self, record, name, values):
        if self.representation != 'schematic':
            return None
        from .symbol_text import plan_symbol_text
        named = ('ShowName', 'ShowRefDes')
        if record.kind == 'Schematic' and name in tuple(item+'_Global' for item in named):
            return plan_symbol_text(self, overrides={(record, name): values})
        if (record.kind in tuple(item+'_Global' for item in named) and record.parent is not None
                and record.parent.kind == 'Schematic'):
            replacement = list(record.arguments)
            replacement[record.schema.parameters.index(name)] = values[0]
            return plan_symbol_text(self, overrides={(record.parent, record.kind): tuple(replacement)})
        source = record
        while source.parent is not None and source.kind != 'Part':
            source = source.parent
        if source.kind != 'Part' or source.parent is None or source.parent.kind != 'Components':
            return None
        if record.parent is source and record.kind in named:
            replacement = list(record.arguments)
            replacement[record.schema.parameters.index(name)] = values[0]
            return plan_symbol_text(self, parts=(source,), overrides={(source, record.kind): tuple(replacement)})
        if ((record is source and name in ('Name', 'RefDes', 'Value', 'Manufacturer', 'Datasheet',
                'PartName', 'PartDescriptor', 'AllowParts', 'ShowName', 'ShowRefDes')) or
                (record.kind == 'UserField' and name == 'Value')):
            return plan_symbol_text(self, parts=(source,), overrides={(record, name): values})
        return None

    def _apply_field_change(self, plan):
        if plan:
            from .symbol_text import apply_symbol_text
            apply_symbol_text(plan)

    def _field_plan_values(self, plan):
        for shape, _, rows, text, show_part in plan or ():
            if rows:
                yield rows[0], (Value.of(text),)
            if show_part is not None and shape.child('ShowPart') is not None:
                yield shape.one('ShowPart'), (Value.of(show_part),)

    @export_diagnostics('asc')
    def as_asc(self, *, context=None, version=ASC.default_write_version, report=None, label=None) -> "Document":
        """Create an owned ASC-format document from the current shared design."""
        ASC.output_version(version)
        from ..formats.asc.write import (project_document)
        return project_document(self,context=context,report=report)

    @import_diagnostics()
    def as_schematic(self, *, report=None, label=None) -> "Document":
        """Normalize public ASC or DCHXML into editable shared schematic data.

        Missing binary-only facts receive declared defaults. DCH input already
        has this representation and returns an independent clone.
        """
        if self.representation == 'schematic':
            return self.clone()
        if self.representation == 'dchxml':
            from ..formats.dchxml.read import (import_schematic)
            return import_schematic(self)
        from ..formats.asc.read import (import_schematic)
        return import_schematic(self)

    @export_diagnostics('asc')
    def to_asc(self, *, preserve=True, allow_partial=False, context=None,
               version=ASC.default_write_version, report=None, label=None) -> str:
        version = ASC.output_version(version)
        if self.representation == 'dchxml':
            raise ValueError('normalize XML with as_schematic() before ASC semantic projection')
        if context is not None or not allow_partial and self.representation == 'schematic':
            return self.as_asc(context=context,version=version,report=report).to_asc(preserve=preserve,version=version)
        if not allow_partial and (self.representation == 'schematic' or
                any(node.annotations.get('requires_asc_projection') for node in self.root.walk(include_self=True))):
            raise IncompleteDocumentError('shared schematic data requires an ASC export context')
        from ..formats.asc.syntax import (dumps)
        if not allow_partial:
            gaps = self.unresolved()
            if not self.complete or gaps:
                raise IncompleteDocumentError("document is incomplete: " + "; ".join(gaps))
            self.rebuild(force=False)
        return dumps(self, preserve=preserve)

    @export_diagnostics('asc')
    def to_asc_bytes(self, *, preserve=True, allow_partial=False, encoding: str | None = None,
                     context=None, version=ASC.default_write_version, report=None, label=None) -> bytes:
        version = ASC.output_version(version)
        if context is not None or not allow_partial and self.representation == 'schematic':
            if encoding is not None:
                from dataclasses import replace
                from ..formats.export_context import resolve_export_context
                context = replace(resolve_export_context(context, 'asc'), encoding=encoding)
            return self.as_asc(context=context,version=version,report=report).to_asc_bytes(preserve=preserve,encoding=encoding,version=version)
        text = self.to_asc(preserve=preserve, allow_partial=allow_partial,version=version)
        if preserve and not self.root._dirty and self._source_bytes is not None and encoding is None:
            return self._source_bytes
        selected=encoding or self._source_encoding
        import codecs
        if codecs.lookup(selected).name=='cp1252':
            from ...common.text.windows_1252 import (encode)
            return encode(text,best_fit=False)
        return text.encode(selected)

    @export_diagnostics('asc')
    def save_asc(self, path, *, context=None, report=None, label=None, **options):
        from pathlib import Path
        data = self.to_asc_bytes(context=context, report=report, **options)
        Path(path).write_bytes(data)

    @export_diagnostics('dch')
    def to_dch_bytes(self, *, version=DCH.default_write_version, context=None, report=None, label=None) -> bytes:
        """Serialize current data to the supported binary output schema."""
        from ..formats.dch.write import (encode)
        return encode(self,version=version,context=context,report=report)

    @export_diagnostics('dch')
    def save_dch(self,path,*,version=DCH.default_write_version,context=None,report=None,label=None):
        from pathlib import Path
        data=self.to_dch_bytes(version=version,context=context,report=report)
        Path(path).write_bytes(data)

    @export_diagnostics('dchxml')
    def as_dchxml(self, *, context=None, version=DCHXML.default_write_version, report=None, label=None) -> "Document":
        """Project shared schematic data to an independent public XML document."""
        from ..formats.dchxml.write import (project_document)
        return project_document(self, context=context, version=version, report=report)

    @export_diagnostics('dchxml')
    def to_dchxml(self, *, newline='\n', context=None, version=DCHXML.default_write_version, report=None, label=None) -> str:
        if context is not None or self.representation == 'schematic':
            return self.as_dchxml(context=context, version=version, report=report).to_dchxml(newline=newline)
        from ..formats.dchxml.syntax import (dumps)
        return dumps(self, newline=newline)

    @export_diagnostics('dchxml')
    def to_dchxml_bytes(self, *, newline='\n', context=None, version=DCHXML.default_write_version, report=None, label=None) -> bytes:
        return self.to_dchxml(newline=newline, context=context, version=version, report=report).encode('utf-8')

    @export_diagnostics('dchxml')
    def save_dchxml(self, path, *, newline='\n', context=None, version=DCHXML.default_write_version, report=None, label=None):
        from pathlib import Path
        data = self.to_dchxml_bytes(newline=newline, context=context, version=version, report=report)
        Path(path).write_bytes(data)
