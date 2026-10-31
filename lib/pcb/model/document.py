"""PCB data operations over the shared tree and reference graph."""
from ...common.model import Document as BaseDocument
from ...common.conversion import import_diagnostics
from ...common.field_edits import preview_slots, named_field, prepare_reference_edit
from ...common.refdes import RefDesFamily
from ...common import supplier_records
from ...common.references import ReferenceError
from . import membership, routing, pair_routing, pair_membership, board_rules, graphic_relations, pad_records
from . import internal_connections, length_matching, ratlines, drc_results, teardrops
from . import assembly_variants
from . import connection_policies, hierarchy
from . import library_relations, library_records, local_groups, dimensions, cache_links
from . import non_signal_layers
from . import pour_regions
from . import label_text, table_relations, table_records, title_relations, title_records, pair_ranges
from .refdes import components, validate_name, validate_edit


class Document(BaseDocument):
    _representations = (*BaseDocument._representations, 'pcb', 'dipxml')
    _named_representations = ('pcb',)

    def __init__(self, root=None, *, representation='pcb'):
        super().__init__(root, representation=representation)
        if representation == 'pcb':
            self._reference_validator = self._validate_relationships

    @import_diagnostics()
    def as_pcb(self, *, context=None, report=None, label=None):
        """Import an inspected text tree, or clone an existing PCB model."""
        if self.representation == 'pcb':
            return self.clone()
        if self.representation == 'asc':
            from ...common.asc import dumps
            data = dumps(self, preserve=False)
        elif self.representation == 'dipxml':
            from ..formats.dipxml.syntax import dumps
            data = dumps(self)
        else:
            raise TypeError('PCB import requires PCB ASC or DIPXML source syntax')
        from ..formats.io import parse
        return parse(data, format=self.representation, context=context)

    def as_asc(self, *, context=None, version=None, report=None, label=None, encoding=None):
        """Project an owned ASC tree without changing this design."""
        from ..formats.io import project
        return project(self, format='asc', context=context, version=version,
                       report=report, label=label, encoding=encoding)

    def as_dipxml(self, *, context=None, version=None, report=None, label=None):
        """Project an owned PCB XML tree without changing this design."""
        from ..formats.io import project
        return project(self, format='dipxml', context=context, version=version, report=report, label=label)

    def to_asc_bytes(self, *, context=None, version=None, report=None, label=None, encoding=None):
        from ..formats.io import serialize
        return serialize(self, format='asc', context=context, version=version,
                         report=report, label=label, encoding=encoding)

    def to_dip_bytes(self, *, context=None, version=None, report=None, label=None):
        from ..formats.io import serialize
        return serialize(self, format='dip', context=context, version=version, report=report, label=label)

    def to_dipxml_bytes(self, *, context=None, version=None, report=None, label=None):
        from ..formats.io import serialize
        return serialize(self, format='dipxml', context=context, version=version, report=report, label=label)

    def save_asc(self, path, *, context=None, version=None, report=None, label=None, encoding=None):
        from ..formats.io import write
        return write(self, path, format='asc', context=context, version=version,
                     report=report, label=label, encoding=encoding)

    def save_dip(self, path, *, context=None, version=None, report=None, label=None):
        from ..formats.io import write
        return write(self, path, format='dip', context=context, version=version, report=report, label=label)

    def save_dipxml(self, path, *, context=None, version=None, report=None, label=None):
        from ..formats.io import write
        return write(self, path, format='dipxml', context=context, version=version, report=report, label=label)

    def _validate_relationships(self, document):
        membership.validate(document)
        routing.validate(document)
        pair_routing.validate_references(document, document.references)
        pair_membership.validate_references(document, document.references)
        board_rules.validate(document)
        graphic_relations.validate(document)
        pour_regions.validate(document)
        non_signal_layers.validate_references(document, document.references)
        pad_records.validate_references(document, document.references)
        internal_connections.validate_references(document, document.references)
        connection_policies.validate_references(document, document.references)
        hierarchy.validate_references(document, document.references)
        library_relations.validate_references(document, document.references)
        cache_links.validate_prefix(document.one('/Board'))
        cache_links.validate_references(document, document.references)
        local_groups.validate_references(document, document.references)
        dimensions.validate_references(document, document.references)
        label_text.validate_references(document, document.references)
        table_relations.validate_references(document, document.references)
        title_relations.validate_references(document, document.references)
        length_matching.validate_references(document, document.references)
        ratlines.validate_references(document, document.references)
        drc_results.validate_references(document, document.references)
        teardrops.validate_references(document, document.references)
        assembly_variants.validate_references(document, document.references)
        from .via_layers import validate_layers
        for reference in document.references:
            if reference.role == 'via-style' and reference.source.kind == 'Component':
                validate_layers(reference.source)

    def refdes(self, prefix):
        if self.representation != 'pcb':
            raise TypeError('RefDes helpers require the PCB model')
        return RefDesFamily(prefix, lambda: components(self),
                            get_refdes=lambda component: component['RefDes'])

    def _calculation_outputs(self, slot):
        if self.representation != 'pcb' or not self._automatic_structure:
            return ()
        return tuple(label_text.calculation_outputs(label_text.dependent_shapes(self, slot)))

    def _plan_calculations(self, slot):
        if self.representation != 'pcb' or not self._automatic_structure:
            return ()
        shapes = label_text.dependent_shapes(self, slot, include_outputs=True)
        return tuple((plan[0], plan, tuple(label_text.plan_values((plan,))))
                     for plan in label_text.plan_text(self, shapes)) if shapes else ()

    def _structural_calculation_slots(self, nodes):
        if self.representation == 'pcb' and self._automatic_structure:
            for node in nodes:
                if (node._owner() is self and node.kind == 'Shape'
                        and label_text.is_bound_label(node)):
                    yield node.one('TextShow')._argument_owner(0)

    def _apply_calculations(self, plans):
        from ...common.structural_edits import assembly
        from .definitions import establish_records
        with assembly(self):
            label_text.apply_text(plans)
            for shape, *_ in plans:
                establish_records(shape)

    def _prepare_value_edit(self, record, name, field, values, *, created):
        if self.representation == 'pcb' and self._automatic_structure and name == 'Text':
            shape = record.parent.parent if record.parent is not None and record.parent.kind == 'TextLine' else None
            if shape is not None and label_text.is_bound_label(shape):
                raise TypeError('Text is calculated for a field-bound label; edit its source field or use literal text')
        base = super()._prepare_value_edit(record, name, field, values, created=created)
        if self.representation != 'pcb' or not self._automatic_structure:
            return base
        named = {(record, name)} | {found for node, argument in base.projections.values
                                    if (found := named_field(node, argument)) is not None}
        from . import static_via
        with preview_slots(base.projections.values):
            replacements = static_via.edit_references(self, named)
        if replacements:
            base.projections = self.references._prepare_reprojections(replacements, structure=base.projections)
            named.update(found for node, argument in base.projections.values
                         if (found := named_field(node, argument)) is not None)
        with preview_slots(base.projections.values):
            static_via.validate_fields(self, named)
            for owner, field_name in named:
                graphic_relations.validate_field(self, owner, field_name)
                pour_regions.validate_field(self, owner, field_name)
                hierarchy.validate_field(self, owner, field_name)
                dimensions.validate_field(self, owner, field_name)
                drc_results.validate_field(self, owner, field_name)
                teardrops.validate_field(self, owner, field_name)
                table_relations.validate_field(self, owner, field_name)
                pair_membership.validate_field(self, owner, field_name)
                if owner.kind == 'Component' and field_name in ('RefDes', 'Enabled'):
                    validate_edit(self, owner, field_name)
                if field_name == 'Enabled' and not owner['Enabled']:
                    if owner.kind == 'Component' and any(membership.get_net(pad) is not None
                            for pad in owner.select('Pattern/Pads/Pad')):
                        raise ReferenceError('disconnect assigned pads before disabling their component')
                    if owner.kind == 'Net' and (owner.one('Pads').children() or
                            self.references.incoming(owner, role='pad-net') or
                            owner.one('Traces').children() or
                            self.references.incoming(owner, role='pair-positive') or
                            self.references.incoming(owner, role='pair-negative')):
                        raise ReferenceError('disconnect assigned pads, traces and pairs before disabling their net')
                    if owner.kind == 'DifferentialPair' and any(self.references.outgoing(owner, role=role)
                            for role in routing.PAIR_NETS):
                        raise ReferenceError('disconnect pair net assignments before disabling their pair')
                if field_name == 'Enabled':
                    for reference in self.references.incoming(owner):
                        self._validate_reference_change(reference, reference.target)
            affected = {membership.component_of(owner) for owner, field_name in named
                        if owner.kind == 'Pad' and field_name in ('StringNumber', 'PadShape_New')}
            for component in affected:
                if component is not None:
                    connection_policies.validate_component(self, component)
            specifications, issues = label_text.edit_specifications(self, named)
            cache_specs, cache_issues = cache_links.edit_specifications(self, named)
            specifications.extend(cache_specs)
            issues.extend(cache_issues)
            if specifications or issues:
                return prepare_reference_edit(self, record, field, values, created=created, base=base,
                                              specifications=specifications, issues=issues)
        return base

    def _prepare_copied_content(self, root):
        if self.representation == 'pcb':
            if root.kind == 'Component':
                validate_name(self, root)
            hierarchy.validate_move(self, root, root.parent)
            table_relations.validate_move(self, root, root.parent)
            title_relations.validate_move(self, root, root.parent)
            length_matching.validate_move(self, root, root.parent)
            ratlines.validate_move(self, root, root.parent)
            drc_results.validate_move(self, root, root.parent)
            teardrops.validate_move(self, root, root.parent)
            assembly_variants.validate_move(self, root, root.parent)
            pour_regions.validate_move(self, root, root.parent)
            label_text.refresh_new_text(self, root)

    def _attachment_required(self, parent, node):
        return (self.representation == 'pcb' and (
            supplier_records.requires_attachment(parent, node) or
            assembly_variants.requires_attachment(parent, node) or
            length_matching.requires_attachment(parent, node) or
            ratlines.requires_attachment(parent, node) or
            drc_results.requires_attachment(parent, node) or
            teardrops.requires_attachment(parent, node) or
            cache_links.is_link(node, parent) or
            parent.schema is not None and node.kind in parent.schema.children or
            parent.kind == 'NonSignals' and parent.parent is not None and parent.parent.kind == 'Board'
            and node.kind == 'NonSignal' or
            node.kind == 'CacheLib' and parent.kind == 'Board' or
            node.kind == 'Slots' and parent.kind == 'CacheLib' or
            node.kind == 'Slot' and parent.kind == 'Slots' and parent.parent is not None
            and parent.parent.kind == 'CacheLib' or
            node.schema in (title_records.CELL, title_records.CONTENT, title_records.BLOCK,
                title_records.BLOCKS, title_records.CELLS, title_records.CONTENTS) or
            node.kind == 'TitleBlocks' and parent is self.one('/Board').child('SheetSettings') or
            (parent.schema, node.kind) in ((title_records.CELLS, 'Cell'),
                (title_records.CONTENTS, 'Content'), (title_records.BLOCKS, 'TitleBlock'),
                (title_records.BLOCK, 'Cells'), (title_records.BLOCK, 'Contents')) or
            node.schema in (table_records.MEMBER, table_records.ROW, table_records.ROWS, table_records.TABLE) or
            (parent.schema, node.kind) in ((table_records.ROW, 'Item'), (table_records.ROWS, 'Row'),
                (table_records.TABLE, 'RowComponents')) or
            parent.kind == 'Tables' and node.kind == 'Table' or
            node.kind == 'Shape' and parent.kind == 'Shapes' and parent.parent is not None
            and parent.parent.kind == 'Pattern' and parent.parent.parent is not None
            and parent.parent.parent.kind == 'Component' or
            parent.schema is local_groups.GROUPS and node.kind == 'pt' or
            node.schema is not None and node.kind in (
                'Component', 'Trace', 'PosTrace', 'NegTrace', 'DifferentialPair', 'RemovedDifferentialPair',
                'Layer', 'ViaStyle', 'NetClass', 'Group', 'NonSignal', 'HSheet', 'UId')))

    def _plan_attachment(self, parent, node, structure):
        supplier_records.prepare_attachment(node)
        assembly_variants.prepare_attachment(node)
        pour_regions.prepare_attachment(node)
        teardrops.prepare_attachment(node)
        drc_results.prepare_attachment(node)
        ratlines.prepare_attachment(node)
        length_matching.prepare_attachment(node)
        table_relations.prepare_attachment(node)
        title_relations.prepare_attachment(node)
        if parent.schema is local_groups.GROUPS:
            from ...common.structural_edits import assembly
            with assembly(self):
                node.bind_schema(local_groups.GROUP)
                if (field := node.child('Id')) is not None:
                    field.detach()
        if node.kind == 'Component':
            validate_name(self, node)
        else:
            routing.validate_move(self, node, parent)
            board_rules.validate_move(self, node, parent)
            graphic_relations.validate_move(self, node, parent)
            hierarchy.validate_move(self, node, parent)
            table_relations.validate_move(self, node, parent)
        title_relations.validate_move(self, node, parent)
        length_matching.validate_move(self, node, parent)
        ratlines.validate_move(self, node, parent)
        drc_results.validate_move(self, node, parent)
        teardrops.validate_move(self, node, parent)
        assembly_variants.validate_move(self, node, parent)
        pour_regions.validate_move(self, node, parent)
        label_text.refresh_new_text(self, node)
        table_relations.validate_move(self, node, parent)
        title_relations.validate_move(self, node, parent)
        structure = self.references.plan_collections({parent: parent._child_sequence()}, parents={node: parent})
        if cache_links.is_link(node, parent):
            return cache_links.prepare_attachment(self, node, structure)
        return label_text.prepare_attachment(self, node, structure)

    def _apply_attachment(self, plan):
        plan.apply()

    def _validate_reference_change(self, reference, target):
        if self.representation == 'pcb':
            membership.validate_retarget(self, reference, target)
            routing.validate_retarget(self, reference, target)
            pair_routing.validate_reference(self, reference, target)
            pair_membership.validate_reference(self, reference, target)
            board_rules.validate_reference(self, reference, target)
            from . import static_via
            static_via.validate_reference(reference)
            graphic_relations.validate_reference(self, reference, target)
            pour_regions.validate_reference(self, reference, target)
            non_signal_layers.validate_reference(self, reference, target)
            pad_records.validate_reference(self, reference, target)
            from .via_layers import validate_layer_reference
            validate_layer_reference(self, reference, target)
            internal_connections.validate_reference(self, reference, target)
            connection_policies.validate_reference(self, reference, target)
            hierarchy.validate_reference(self, reference, target)
            library_relations.validate_reference(self, reference, target)
            cache_links.validate_reference(self, reference, target)
            local_groups.validate_reference(self, reference, target)
            dimensions.validate_reference(self, reference, target)
            label_text.validate_reference(self, reference, target)
            table_relations.validate_reference(self, reference, target)
            title_relations.validate_reference(self, reference, target)
            length_matching.validate_reference(self, reference, target)
            ratlines.validate_reference(self, reference, target)
            drc_results.validate_reference(self, reference, target)
            teardrops.validate_reference(self, reference, target)
            assembly_variants.validate_reference(self, reference, target)

    def _prepare_reference_binding(self, reference):
        if self.representation == 'pcb' and reference.role == 'via-style':
            from .static_via import reference_projection
            return reference_projection(reference)
        return reference

    def _plan_reference_outputs(self, references):
        if self.representation == 'pcb' and self._automatic_structure:
            from .via_layers import plan_outputs
            return tuple(plan_outputs(self, references))
        return ()

    def _validate_reference_removal(self, reference):
        if self.representation == 'pcb':
            from .via_layers import validate_layer_reference
            validate_layer_reference(self, reference, None)
            membership.validate_removal(self, reference)
            connection_policies.validate_removal(self, reference)
            pair_routing.validate_removal(self, reference)
            pair_membership.validate_removal(self, reference)
            length_matching.validate_removal(self, reference)
            if reference.role in board_rules.SPAN_ROLES:
                from ...common.reference_edits import preview_references
                with preview_references(self.references, {reference.uid: None}):
                    board_rules.validate_span(self, reference.source)
            if reference.role in routing.PAIR_NETS:
                # Check the same prospective state as replacing a pair's net.
                from ...common.reference_edits import preview_references
                with preview_references(self.references, {reference.uid: None}):
                    routing.validate_references(self,
                        self.references._content_references(reference.source.walk(include_self=True)))

    def _unresolved_reference_fields(self, issue):
        if self.representation != 'pcb':
            return ()
        from .local_groups import issue_fields
        return (*pair_ranges.issue_fields(issue), *issue_fields(issue))

    def _validate_unresolved_reference(self, issue):
        if self.representation == 'pcb':
            pair_ranges.validate_issue(self, issue)
            from .local_groups import validate_issue
            validate_issue(self, issue)

    def _validate_structural_references(self, references):
        if self.representation == 'pcb' and self._automatic_structure:
            routing.validate_references(self, references)
            pair_routing.validate_references(self, references)
            pair_membership.validate_references(self, references)
            board_rules.validate_references(self, references)
            from .static_via import validate_reference
            for reference in references:
                validate_reference(reference)
            graphic_relations.validate_references(self, references)
            pour_regions.validate_references(self, references)
            non_signal_layers.validate_references(self, references)
            pad_records.validate_references(self, references)
            internal_connections.validate_references(self, references)
            connection_policies.validate_references(self, references)
            hierarchy.validate_references(self, references)
            library_relations.validate_references(self, references)
            cache_links.validate_references(self, references)
            local_groups.validate_references(self, references)
            dimensions.validate_references(self, references)
            label_text.validate_references(self, references)
            table_relations.validate_references(self, references)
            title_relations.validate_references(self, references)
            length_matching.validate_references(self, references)
            ratlines.validate_references(self, references)
            drc_results.validate_references(self, references)
            teardrops.validate_references(self, references)
            assembly_variants.validate_references(self, references)

    def _validate_move(self, node, parent):
        if self.representation == 'pcb':
            membership.validate_move(self, node, parent)
            routing.validate_move(self, node, parent)
            pair_routing.validate_move(self, node, parent)
            board_rules.validate_move(self, node, parent)
            graphic_relations.validate_move(self, node, parent)
            pour_regions.validate_move(self, node, parent)
            hierarchy.validate_move(self, node, parent)
            table_relations.validate_move(self, node, parent)
            title_relations.validate_move(self, node, parent)
            length_matching.validate_move(self, node, parent)
            ratlines.validate_move(self, node, parent)
            drc_results.validate_move(self, node, parent)
            teardrops.validate_move(self, node, parent)
            assembly_variants.validate_move(self, node, parent)
            if node.kind in ('Component', 'Net'):
                destination = parent._owner()
                collection = 'Components' if node.kind == 'Component' else 'Nets'
                if (destination is None or destination.representation != 'pcb' or
                        parent is not destination.one('/Board/'+collection)):
                    raise ReferenceError(f'{node.kind} must remain in a PCB {collection} collection')
                if node.kind == 'Component':
                    validate_name(destination, node, parent=parent)

    def _structural_dependents(self, nodes):
        return membership.structural_dependents(self, nodes) if self.representation == 'pcb' else ()

    def _reference_collection_dependencies(self, reference):
        if self.representation == 'pcb' and reference.role == 'via-style' and reference.source.kind == 'Component':
            from .static_via import controlled
            if controlled(reference.source):
                from .via_layers import collections
                return tuple(collections(reference.source))
        if self.representation == 'pcb' and reference.role == connection_policies.ROLE:
            return connection_policies.collections(reference.source)
        if self.representation == 'pcb' and reference.role in board_rules.SPAN_ROLES:
            return ((reference.target.parent, reference.target.kind),)
        return ()
