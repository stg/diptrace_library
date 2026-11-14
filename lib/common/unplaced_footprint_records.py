"""Editable footprint definitions with local identity-based relationships.

Standalone pattern libraries and component attachments share these physical
facts. Their container metadata and document-level rules belong to each family.
"""
from dataclasses import replace

from . import footprint_records as physical, group_records
from .footprint_text import TEXT_FIELDS
from .schema import Child, Field, Record, MISSING
from .relationship_fields import optional_reference_fields
from .library_group_bounds import (coordinates as _group_coordinates,
    value_dependencies as _group_values, collection_dependencies as _group_collections)


GROUP_ROLE = 'pattern-group'
PAD_ROLE = 'pattern-shape-pad'
DIMENSION_ROLES = ('pattern-dimension-1', 'pattern-dimension-2')
CONNECTION_ROLES = ('pattern-internal-pad-1', 'pattern-internal-pad-2')


def grouped(record, *, name=None, role=GROUP_ROLE):
    return replace(record, name=name or record.name, fields={
        **{key: field for key, field in record.fields.items() if key != 'Group'},
        **optional_reference_fields('Group', 'GroupId', role)},
        parameters=tuple(key for key in record.parameters if key != 'Group'))


GROUP = replace(group_records.LOCAL_GROUP, name='PatternLocalGroup', fields={
    **group_records.LOCAL_GROUP.fields,
    'Id': Field('Id', 'integer', getter=lambda node: node._ordinal(),
                ordinal_dependencies=lambda node: (node,), description='Current local group position.'),
    **{name: Field(name, 'number', getter=lambda node, axis=axis: _group_coordinates(node)[axis],
        unit='shared length', value_dependencies=lambda node: _group_values(node),
        collection_dependencies=lambda node: _group_collections(node),
        reference_dependencies=lambda node: ((node, '', 'incoming'),),
        description='Calculated centre of the current member-selection envelope.')
       for axis, name in enumerate(('X', 'Y'))}})
GROUPS = Record('PatternLocalGroups', {}, children={'pt': Child('pt', GROUP.name, maximum=None)})
PAD = grouped(replace(physical.PAD, fields={
    **{key: field for key, field in physical.PAD.fields.items() if key != 'Number_New'},
    'Id': Field('Id', 'integer', getter=lambda node: node._ordinal()+1,
                ordinal_dependencies=lambda node: (node,),
                description='Current one-based public pad key; references use object identity.')
}), name='LibraryPad')
DRAWING = grouped(replace(physical.PATTERN_SHAPE, fields={
    **{key: replace(field, required=False, default=MISSING) if key in TEXT_FIELDS else field
       for key, field in physical.PATTERN_SHAPE.fields.items() if key != 'PadId'},
    'Width': replace(physical.PATTERN_SHAPE.fields['Width'], required=False, default=MISSING,
        description='Geometric drawing stroke; text uses FontWidth and has no Width.'),
    **optional_reference_fields('Pad', 'PadId', PAD_ROLE, offset=1)}), name='LibraryPatternDrawing')
HOLE = grouped(physical.HOLE, name='LibraryHole')
DIMENSION = grouped(physical.DIMENSION, name='LibraryDimension')
PADS = Record('LibraryPads', {}, children={'Pad': Child('Pad', PAD.name, maximum=None)})
DRAWINGS = Record('LibraryPatternDrawings', {}, children={'Shape': Child('Shape', DRAWING.name, maximum=None)})
HOLES = Record('LibraryHoles', {}, children={'Hole': Child('Hole', HOLE.name, maximum=None)})
DIMENSIONS = Record('LibraryDimensions', {}, children={'Dimension': Child('Dimension', DIMENSION.name, maximum=None)})
PAIR = Record('PatternInternalConnection', {
    **optional_reference_fields('Pad1', 'X', CONNECTION_ROLES[0], offset=1),
    **optional_reference_fields('Pad2', 'Y', CONNECTION_ROLES[1], offset=1),
}, ('X', 'Y'))
CONNECTIONS = Record('InternalConnections', {}, children={'IntCon': Child('IntCon', PAIR.name, maximum=None)})
PATTERN = replace(physical.PATTERN, fields={**physical.PATTERN.fields,
    'Sided': replace(physical.PATTERN.fields['Sided'], default=False)}, children={
        **physical.PATTERN.children,
        **{name: Child(name, record.name) for name, record in (
            ('Pads', PADS), ('Shapes', DRAWINGS), ('Holes', HOLES),
            ('Dimensions', DIMENSIONS), ('Pattern_Groups', GROUPS))}})
