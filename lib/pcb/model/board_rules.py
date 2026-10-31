"""Copper layers, via spans and routing-rule identities for a PCB document."""
from dataclasses import replace

from ...common.references import ReferenceError
from ...common.schema import Child, Field, Record
from ...common.reference_edits import preview_references
from .relationships import linked, reference_field, index_field
from .length_matching import DEFAULT_FIXED_LENGTH, DEFAULT_DELTA


SPAN_ROLES = ('via-span-from', 'via-span-to')


def _layers(node):
    document = node._owner()
    collection = document.one('/Board').child('Layers') if document is not None else None
    return collection._child_sequence('Layer') if collection is not None else ()


def span(style):
    start, end = (linked(style, role) for role in SPAN_ROLES)
    if (start is None) != (end is None):
        raise ReferenceError('via span must specify both layers or use the full stack')
    return (start, end) if start is not None else None


def set_span(style, value):
    document = style._owner()
    if document is None:
        raise ReferenceError('attach the via style before assigning its layer span')
    start, end = value if value is not None else (None, None)
    document.references._replace_identity_roles(style, dict(zip(SPAN_ROLES, (start, end))))


def span_layer(style, end):
    bounds = span(style)
    layers = _layers(style)
    return bounds[end] if bounds is not None else (layers[0 if end == 0 else -1] if layers else None)


def _span_dependencies(style):
    return tuple((style, role, 'outgoing') for role in SPAN_ROLES)


def _span_collections(style):
    document = style._owner()
    collection = document.one('/Board').child('Layers') if document is not None else None
    return ((collection, 'Layer'),) if collection is not None else ()


def _span_ordinals(style):
    return span(style) or ()


def _span_fields(end):
    name = 'FromLayer' if end == 0 else 'ToLayer'
    dependencies = dict(reference_dependencies=_span_dependencies,
                        collection_dependencies=_span_collections, ordinal_dependencies=_span_ordinals)
    return {
        name: Field(name, 'reference', nullable=True, getter=lambda style: span_layer(style, end), **dependencies),
        'Lay'+str(end+1): Field('Lay'+str(end+1), 'integer',
            getter=lambda style: layer._ordinal() if (layer := span_layer(style, end)) is not None else -1,
            **dependencies),
    }


def _order(name='Id'):
    return Field(name, 'integer', getter=lambda node: node._ordinal(), ordinal_dependencies=lambda node: (node,))


LAYER = Record('PcbCopperLayer', {
    'Name': Field('Name', 'text', required=True, default=''),
    'Number': _order('Number'),
    'Enabled': Field('Enabled', 'boolean', default=True),
    'Color': Field('Color', 'integer', default=0),
    'Type': Field('Type', 'integer', default=0),
    'HoleType': Field('HoleType', 'integer', default=0),
    'HoleRing': Field('HoleRing', 'number', default=0, unit='shared length'),
    'Locked': Field('Locked', 'boolean', default=False),
    'Net': reference_field('Net', 'layer-net'), 'NetNumber': index_field('NetNumber', 'layer-net'),
}, parameters=('Name',))
VIA = Record('PcbViaStyle', {
    'Name': Field('Name', 'text', required=True, default=''), 'Id': _order(),
    'Size': Field('Size', 'number', required=True, default=0, unit='shared length'),
    'HoleSize': Field('HoleSize', 'number', required=True, default=0, unit='shared length'),
    'Span': Field('Span', 'tuple', nullable=True, length=2,
        members=(Field('From', 'reference'), Field('To', 'reference')),
        getter=span, setter=set_span, reference_dependencies=_span_dependencies,
        description='None spans the complete copper stack; a pair of layer identities defines a bounded span.'),
    'Through': Field('Through', 'boolean', getter=lambda style: span(style) is None,
                     reference_dependencies=_span_dependencies),
    **_span_fields(0), **_span_fields(1),
}, parameters=('Name',))
NET_CLASS = Record('PcbNetClass', {
    'Name': Field('Name', 'text', required=True, default=''), 'Id': _order(),
    **{name: Field(name, 'integer', default=0) for name in ('Type', 'HiddenID', 'PriorityValue', 'MaxViasValue')},
    **{name: Field(name, 'boolean', default=False) for name in
       ('AllLayers', 'CheckLength', 'AllVias', 'PerformDRC', 'RoutePriority', 'RouteMaxVias',
        'RouteMaxIncorrectWay', 'RouteAllLayers')},
    **{name: Field(name, 'number', default=0, unit='shared length') for name in
       ('MaxUncoupledLength', 'Tolerance', 'Phase', 'Phase_ErrorLength')},
    'LengthDelta': Field('LengthDelta', 'number', default=DEFAULT_DELTA, unit='shared length'),
    'FixedLength': Field('FixedLength', 'number', default=DEFAULT_FIXED_LENGTH, unit='shared length'),
    'MaxIncorrectWayValue': Field('MaxIncorrectWayValue', 'number', default=0,
        description='Autorouting limit scalar, independent of display length units.'),
}, parameters=('Name',), children={
    'LayProperties': Child('LayProperties', 'PcbClassLayerProperties'),
    'AllowedVias': Child('AllowedVias', 'PcbAllowedVias'),
    'RouteLayers': Child('RouteLayers', 'PcbRouteLayers'),
    'LengthResults': Child('LengthResults', 'PcbClassLengthResults'),
})
COLLECTIONS = {
    name: Record(record, {}, children={kind: Child(kind, schema.name, maximum=None)})
    for name, record, kind, schema in (
        ('Layers', 'PcbCopperLayers', 'Layer', LAYER),
        ('ViaStyles', 'PcbViaStyles', 'ViaStyle', VIA),
        ('NetClasses', 'PcbNetClasses', 'NetClass', NET_CLASS))
}
LAYER_FIELDS = {'Layer': reference_field('Layer', 'copper-layer'), 'Lay': index_field('Lay', 'copper-layer')}
VIA_FIELDS = {'Via': reference_field('Via', 'via-style'), 'ViaStyle': index_field('ViaStyle', 'via-style')}
CLASS_FIELDS = {'Class': reference_field('Class', 'net-class'), 'NetClass': index_field('NetClass', 'net-class')}


def material_layer(material):
    item = material.parent
    return linked(item, 'copper-layer') if item is not None and item.kind == 'LayerStackItem' else None


MATERIAL = Record('PcbLayerMaterial', {
    'Name': Field('Name', 'text', default=''),
    'Type': Field('Type', 'integer',
        getter=lambda material: layer.get('Type', 0) if (layer := material_layer(material)) is not None else 2,
        reference_dependencies=lambda material: ((material.parent, 'copper-layer', 'outgoing'),)
            if material.parent is not None else (),
        value_dependencies=lambda material: ((layer, 'Type'),)
            if (layer := material_layer(material)) is not None else (),
        description='Conductor/plane follows the copper layer; an item without a copper layer is dielectric.'),
    'VariableThickness': Field('VariableThickness', 'boolean', default=False),
    'Constant': Field('Constant', 'number', default=0),
    **{name: Field(name, 'number', default=0, unit='shared length') for name in ('Thickness', 'TraceWidth')},
})
STACK_ITEM = Record('PcbLayerStackItem', {'Id': _order(), **LAYER_FIELDS}, parameters=('Id',), children={
    'Material': Child('Material', MATERIAL.name, minimum=1),
})
COLLECTIONS['LayerStackItems'] = Record('PcbLayerStackItems', {}, children={
    'LayerStackItem': Child('LayerStackItem', STACK_ITEM.name, maximum=None),
})


def definition(node):
    from .rule_records import definition as rule_definition
    if (rule := rule_definition(node)) is not None:
        return rule
    parent = node.parent
    if parent is None:
        return None
    if parent.kind == 'Board':
        return COLLECTIONS.get(node.kind)
    if node.kind == 'LayerStackItem' and parent.kind == 'LayerStackItems':
        return STACK_ITEM
    if node.kind == 'Material' and parent.kind == 'LayerStackItem':
        return MATERIAL
    return {('Layers', 'Layer'): LAYER, ('ViaStyles', 'ViaStyle'): VIA,
            ('NetClasses', 'NetClass'): NET_CLASS}.get((parent.kind, node.kind))


def _target(document, target, collection, kind):
    if target.kind != kind or target.parent is not document.one('/Board').child(collection):
        raise ReferenceError(f'{kind} target is outside this PCB {collection} collection')
    if kind == 'Net' and target.get('Enabled', True) is False:
        raise ReferenceError(f'{kind} target must be enabled')


def validate_span(document, style):
    bounds = span(style)
    if bounds is not None:
        for layer in bounds:
            _target(document, layer, 'Layers', 'Layer')
        if bounds[0]._ordinal() >= bounds[1]._ordinal():
            raise ReferenceError('via span requires distinct layers in stack order')


def validate_reference(document, reference, target):
    role = reference.role
    if role == 'copper-layer' or role in SPAN_ROLES:
        _target(document, target, 'Layers', 'Layer')
    elif role == 'via-style':
        _target(document, target, 'ViaStyles', 'ViaStyle')
    elif role in ('net-class', 'net-class-1', 'net-class-2', 'default-net-class'):
        _target(document, target, 'NetClasses', 'NetClass')
    elif role == 'layer-net':
        _target(document, target, 'Nets', 'Net')
    else:
        return
    if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=role)):
        raise ReferenceError(f'{role}: source already has a target')
    if role == 'default-net-class' and reference.source is not document.one('/Board'):
        raise ReferenceError('the PCB board owns its default class identity')
    if role in ('copper-layer', 'via-style'):
        from . import rule_records
        scoped = (rule_records.LAYER_PROPERTY, rule_records.ROUTE_LAYER, rule_records.DRC_CLEARANCE,
                  rule_records.DRC_SIZE, rule_records.LAYER_CLEARANCE, rule_records.ALLOWED_VIA)
        if reference.source.schema in scoped:
            for candidate in document.references.incoming(target, role=role):
                if (candidate.source is not reference.source and
                        candidate.source.parent is reference.source.parent):
                    raise ReferenceError('rule table already has this target')
    if role in SPAN_ROLES:
        if reference.source.parent is not document.one('/Board').child('ViaStyles'):
            raise ReferenceError('via span requires a style in this PCB')
        if document._automatic_structure:
            with preview_references(document.references, {reference.uid: replace(reference, target=target)}):
                validate_span(document, reference.source)
    if role in ('net-class-1', 'net-class-2'):
        from .relationships import linked
        other_role = 'net-class-2' if role == 'net-class-1' else 'net-class-1'
        other = linked(reference.source, other_role)
        if other is not None:
            expected = frozenset((target, other))
            for incoming_role in ('net-class-1', 'net-class-2'):
                for candidate in document.references.incoming(target, role=incoming_role):
                    if candidate.source is reference.source:
                        continue
                    first = linked(candidate.source, 'net-class-1')
                    second = linked(candidate.source, 'net-class-2')
                    if first is not None and second is not None and frozenset((first, second)) == expected:
                        raise ReferenceError('class clearance already has this unordered class pair')


def validate_move(document, node, parent):
    collection = {LAYER.name: 'Layers', VIA.name: 'ViaStyles', NET_CLASS.name: 'NetClasses'}.get(
        node.schema.name if node.schema is not None else None)
    if collection is not None and parent is not document.one('/Board').child(collection):
        raise ReferenceError(f'{node.kind} must remain in its PCB {collection} collection')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate(document):
    validate_references(document, document.references)
