"""Activate only newly attached schematic data and its declared relationships."""
from dataclasses import dataclass

from ...common.model import Element
from ...common.references import ReferenceError
from ...common.structural_edits import assembly, preview_structure, validate_child_change
from .definitions import establish_records
from .nested_records import modernize_classifications
from .membership import MEMBER, NET_NUMBER, get_net, _calculated_number, establish_member
from .reference_scope import ReferenceScope, OrdinalLookup
from .refs import _specifications, _integer, reference_collections, REFERENCE_COLLECTIONS


@dataclass
class Attachment:
    document: object
    additions: object
    members: tuple
    issues: tuple
    watched: tuple

    def apply(self):
        graph = self.document.references
        parents = set()
        for parent, member in self.members:
            parent._items.append(member)
            member._parent = parent
            parent._touch(reordered=True)
            parents.add(parent)
        graph._apply_additions(self.additions)
        for source, message, indices, collections, guards in self.issues:
            graph.note(source, message, *indices, collections=collections, guards=guards)
        for node in self.watched:
            graph.watch(node)
        graph.finish_structure(parents)


def _placed_pin(pin, components):
    return (pin.kind == 'Pin' and pin.parent is not None and pin.parent.kind == 'Pins' and
            pin.parent.parent is not None and pin.parent.parent.parent is components)


def _membership(document, root):
    """Return identity memberships and normalize new pins' numeric views."""
    schematic = document.one('/Schematic')
    components, nets = schematic.one('Components'), schematic.one('Nets')
    parts = OrdinalLookup(components._child_sequence('Part'))
    net_choices = OrdinalLookup(nets._child_sequence('Net'))
    assigned, specifications, generated = {}, [], []

    def assign(member, pin, net):
        if pin is None:
            return False
        if pin in assigned or get_net(pin) is not None:
            raise ReferenceError('pin already has a net membership')
        assigned[pin] = member, net
        establish_member(member)
        specifications.append((member, pin, 'net-member', (), ()))
        return True

    for member in tuple(root.walk(include_self=True)):
        owner = member.parent
        if (member.kind != 'pt' or owner is None or owner.kind != 'Parts' or owner.parent is None or
                owner.parent.parent is not nets):
            continue
        if member.schema is MEMBER:
            raise ReferenceError('a copied net member needs its pin identity; copy linked records through their document')
        if len(member.values) != 2:
            raise ValueError('a net member requires component and pin indices')
        part_number, pin_number = map(_integer, member.values)
        if part_number is None or pin_number is None:
            raise TypeError('net member indices require integers')
        part = parts.get(part_number)
        pins = part.child('Pins') if part is not None else None
        pin = OrdinalLookup(pins.children('Pin')).get(pin_number) if pins is not None else None
        assign(member, pin, owner.parent)

    for pin in tuple(root.walk(include_self=True)):
        if not _placed_pin(pin, components):
            continue
        field = pin.child('NetNumber')
        if field is None or field.schema is NET_NUMBER:
            continue
        number = _integer(field.scalar('Value') if field.schema is not None else field.values[0])
        if number is None:
            raise TypeError('NetNumber requires an integer')
        net = net_choices.get(number) if number >= 0 else None
        if number >= 0 and net is None:
            continue  # The unresolved numeric identity remains explicit.
        if pin in assigned:
            if net is not None and assigned[pin][1] is not net:
                raise ReferenceError('pin has contradictory net memberships')
        elif net is not None:
            members = net.child('Parts')
            if members is None:
                raise ReferenceError('net is missing its member collection')
            member = Element('pt')
            assign(member, pin, net)
            generated.append((members, member))
        _calculated_number(pin)
    return specifications, generated


def refresh_new_text(document, root):
    """Initialize only copied/new label content from its current field source."""
    fresh_shapes = [node for node in root.walk(include_self=True) if node.kind == 'Shape' and
                    node.parent is not None and node.parent.kind == 'Shapes' and
                    node.parent.parent is not None and node.parent.parent.parent is document.one('/Schematic/Components')]
    if not fresh_shapes:
        return False
    from .symbol_text import plan_symbol_text, apply_symbol_text
    parts = tuple(dict.fromkeys(shape.parent.parent for shape in fresh_shapes))
    text = plan_symbol_text(document, parts=parts, shapes=fresh_shapes)
    if text:
        with assembly(document):
            apply_symbol_text(text)
            establish_records(root)
    return bool(text)


def prepare_attachment(document, parent, root, structure):
    definition = parent.schema.fields.get(root.kind) if parent.schema is not None else None
    if definition is not None and definition.getter is not None:
        raise TypeError(f'{root.kind} is calculated; edit its owning relationship or collection')
    with assembly(document):
        modernize_classifications(root)
        establish_records(root)
        memberships, generated = _membership(document, root)
    from .refdes import validate_name
    validate_name(document, root)
    scope = ReferenceScope(root)
    children = {parent: parent._child_sequence()}
    parents = {root: parent}
    for owner, member in generated:
        children[owner] = (*children.get(owner, owner._child_sequence()), member)
        parents[member] = owner
    ordinals = {}
    for owner, records in children.items():
        counts = {}
        for record in records:
            ordinals[record] = counts.get(record.kind, 0)
            counts[record.kind] = ordinals[record] + 1
        if owner is not parent:
            validate_child_change(owner, records, 'pt')
    with preview_structure(children, parents, ordinals):
        validate_child_change(parent, children[parent], root.kind)
        structure = document.references.plan_collections(children, parents=parents)
        specifications, issues = list(memberships), []
        for source, target, role, indices, guards in _specifications(document, scope=scope):
            if any(item is None for item in indices):
                continue
            if target is None:
                collections = reference_collections(document, source, role, authoring=True)
                issues.append((source, f'{role}: target index cannot be resolved', indices, collections, guards))
            else:
                specifications.append((source, target, role, indices, guards))
        additions = document.references._prepare_additions(specifications, structure=structure)
        if refresh_new_text(document, root):
            additions = document.references._prepare_additions(specifications, structure=structure)
        from ...common.references import UnresolvedReference
        for source, message, indices, collections, guards in issues:
            document.references._validate_reference_guards(
                UnresolvedReference(source, message, indices, collections, guards), {})
    return Attachment(document, additions, tuple(generated), tuple(issues),
                      tuple(node for node in scope.nodes if node.kind in REFERENCE_COLLECTIONS))
