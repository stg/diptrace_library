"""Calculated copper-fill groups and their scoped primitive memberships.

An absent Regions collection means classification is unavailable. An available
collection may be empty, or contain groups alongside unassigned primitives.
The groups do not calculate or constrain copper geometry.
"""
from ...common.references import ReferenceError
from ...common.schema import Child, Field, Record
from .relationships import linked, reference_field


ROLE = 'pour-region'
REGION = Record('PcbPourRegion', {
    'Number': Field('Number', 'integer', required=True, default=0,
                    description='Nonnegative classification label, unique within this fill.'),
}, parameters=('Number',))
REGIONS = Record('PcbPourRegions', {},
    description='Available calculated classification; absence means unavailable, including when fill geometry exists.',
    children={'Region': Child('Region', REGION.name, maximum=None)})


def number(node):
    target = linked(node, ROLE)
    return target['Number'] if target is not None else -1


FIELDS = {
    'Region': reference_field('Region', ROLE),
    'RegionId': Field('RegionId', 'integer', getter=number,
        reference_dependencies=lambda node: ((node, ROLE, 'outgoing'),),
        value_dependencies=lambda node: ((target, 'Number'),)
            if (target := linked(node, ROLE)) is not None else (),
        description='Current group label, or -1 when unassigned; edit Region instead.'),
}


def _member(node):
    return node.schema is not None and node.schema.fields.get('Region') is FIELDS['Region']


def _fill(node):
    if node.schema is REGIONS:
        return node.parent
    parent = node.parent
    return parent.parent if parent is not None and (node.schema is REGION or _member(node)) else None


def _valid_fill(document, fill):
    pour = fill.parent if fill is not None else None
    return (fill is not None and fill.kind == 'Fill' and pour is not None
            and pour.kind == 'CopperPour' and pour.parent is document.one('/Board').child('CopperPours'))


def _check_number(region, collection):
    value = region['Number']
    REGION.fields['Number'].validate(value)
    if value < 0:
        raise ValueError('pour region Number must be nonnegative')
    if any(other is not region and other['Number'] == value for other in collection.children('Region')):
        raise ValueError(f'duplicate pour region Number {value}')


def validate_collection(collection):
    seen = set()
    for region in collection.children('Region'):
        value = region['Number']
        REGION.fields['Number'].validate(value)
        if value < 0 or value in seen:
            raise ValueError('pour region Numbers must be nonnegative and unique within their fill')
        seen.add(value)


def primitives(fill):
    if fill is not None:
        for name, kind in (('Lines', 'Line'), ('Polygons', 'Poly'), ('SpokeLine', 'Line')):
            collection = fill.child(name)
            if collection is not None:
                yield from collection.children(kind)


def validate_reference(document, reference, target):
    if reference.role != ROLE:
        return
    source = reference.source
    fill = _fill(source)
    if (not _member(source) or not _valid_fill(document, fill) or target.schema is not REGION
            or target._owner() is not document or target.parent is not fill.child('Regions')):
        raise ReferenceError('pour region membership requires a group in the same fill')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=ROLE)):
        raise ReferenceError('fill primitive already has a region group')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate(document):
    for collection in document.select('/Board/CopperPours/CopperPour/Fill/Regions'):
        validate_collection(collection)
    validate_references(document, document.references)


def validate_field(document, node, name):
    if node.schema is REGION and name == 'Number':
        _check_number(node, node.parent)


def validate_move(document, node, parent):
    if node.schema is REGION:
        if parent.schema is not REGIONS or not _valid_fill(document, parent.parent):
            raise ReferenceError('pour groups require their fill Regions collection')
        _check_number(node, parent)
    elif node.schema is REGIONS:
        if not _valid_fill(document, parent):
            raise ReferenceError('region classification requires a copper-pour fill')
        validate_collection(node)


def prepare_attachment(node):
    from . import graphic_records
    schema = graphic_records.definition(node)
    if schema not in (REGION, REGIONS, graphic_records.POUR, graphic_records.FILL,
                      graphic_records.FILL_LINE, graphic_records.FILL_SPOKE, graphic_records.FILL_POLYGON):
        return
    collections = []
    for child in node.walk(include_self=True):
        if (schema := graphic_records.definition(child)) is not None:
            if 'Region' in schema.fields and child.child('Region') is not None:
                raise TypeError('assign a fill Region identity after attaching the primitive')
            child.bind_schema(schema)
        if child.schema is REGIONS:
            collections.append(child)
    for collection in collections:
        validate_collection(collection)
