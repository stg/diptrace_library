"""Public standalone ASC records into the owned pattern-library model."""
from ....common import footprint_objects, footprint_records as physical
from ....common.asc_footprints import unpack_model, unpack_pattern_shapes
from ....common.asc_library import loads_library, loads_library_bytes, unpack_categories, rows
from ....common.asc_library_import import (_boolean, _flags, _count, _rename, _terminals,
    _pad, _layers, _default_pad_geometry)
from ....common.errors import UnsupportedFileError
from ....common.conversion import import_diagnostics
from ....common.model import Element
from ....common.structural_edits import assembly
from ...model import new_library
from ...model.schema import establish_records
from ..import_patterns import fill_defaults, normalize, finish, active_pad_indices
from ..revisions import ASCII_READ_VERSIONS


def _pattern(pattern):
    if len(pattern.values) != 2:
        raise ValueError(f'{pattern.path}: expected name and default RefDes')
    name, refdes = pattern.arguments
    pattern.set_values(name)
    pattern.add('RefDes', refdes)
    for old, new in (('Manufacturer', 'Pattern_Manufacturer'), ('CategoryName', 'Pattern_CategoryName'),
                     ('CategoryIndex', 'Pattern_CategoryIndex'), ('CategoryTypes', 'Pattern_CategoryTypes')):
        _rename(pattern, old, new)
    for row in pattern.one('Pattern_CategoryTypes').children():
        if row.kind == 'CategoryTypeType':
            row.kind = 'CategoryType'
        elif row.kind != 'CategoryType':
            raise ValueError(f'{row.path}: expected CategoryType')
    _default_pad_geometry(pattern)
    _terminals(pattern)
    _layers(pattern)
    pads = pattern.one('Pads')
    public_pads = rows(pads, 'Pad')
    for index, pad in enumerate(public_pads, 1):
        if pad.values[0] != index:
            raise ValueError(f'{pad.path}: expected consecutive pad indices starting at one')
        _pad(pad)
    first, last = Element('Pad', 0), Element('Pad', len(public_pads)+1)
    first.add('Number_New', -1)
    last.add('Number_New', -1)
    pads.insert(first, 0)
    pads.append(last)
    unpack_pattern_shapes(pattern.one('Shapes'), text_lines_counted=True, empty_nontext_lines=True,
                          header_fields=(('Layer', 2), ('TextAngle', 15)))
    for shape in pattern.select('Shapes/Shape'):
        if shape.child('FontMono') is None:
            shape.add('FontMono', False)
        _flags(shape, physical.PATTERN_SHAPE)
    for hole in rows(pattern.one('Holes'), 'Hole'):
        if len(hole.values) != 7 or hole.children():
            raise ValueError(f'{hole.path}: expected seven hole values')
        hole.set_values(_boolean(hole.values[0], hole.path), _boolean(hole.values[1], hole.path), *hole.arguments[2:])
    for dimension in rows(pattern.one('Dimensions'), 'Dimension'):
        if dimension.child('FontMono') is None:
            dimension.add('FontMono', False)
        _flags(dimension, physical.DIMENSION)
    for group in rows(pattern.one('Pattern_Groups'), 'pt'):
        if len(group.values) != 4 or group.children():
            raise ValueError(f'{group.path}: expected four group values')
        group.set_values(_boolean(group.values[0], group.path), *group.arguments[1:])
    verification = pattern.one('Verification')
    if len(verification.values) != 4 or verification.children():
        raise ValueError(f'{verification.path}: expected four verification flags')
    verification.set_values(*(_boolean(value, verification.path) for value in verification.values))
    model = pattern.one('Model3D')
    unpack_model(model)
    _flags(model, physical.MODEL3D)
    _flags(pattern, physical.PATTERN)
    pattern.bind_schema(physical.PATTERN)


def _audit(root):
    """Every accepted ASC item must have a declared current model meaning."""
    for record in root._record_walk(include_self=True):
        schema = record.schema
        if schema is None:
            raise NotImplementedError(f'{record.path}: unimplemented ASC record')
        for child in record.children():
            if child.kind not in schema.fields and child.kind not in schema.children:
                raise NotImplementedError(f'{child.path}: unimplemented ASC field')


@import_diagnostics('asc')
def parse(data, *, source=None, encoding=None):
    syntax = (loads_library(data, source=source, retain_source=False) if isinstance(data, str) else
              loads_library_bytes(data, source=source, encoding=encoding, retain_source=False))
    if [row.kind for row in syntax.root.children()] != ['Source', 'Library']:
        raise ValueError('expected one Source declaration followed by one Library')
    declaration = syntax.one('/Source').values
    if len(declaration) != 2 or declaration[0] != 'DipTrace-ComLibrary':
        raise UnsupportedFileError(format='asc', family='pattern', reason='format')
    if declaration[1] not in ASCII_READ_VERSIONS:
        raise UnsupportedFileError(format='asc', family='pattern', version=declaration[1], reason='version')
    incoming = syntax.one('/Library')
    if incoming.values or any(row.kind not in ('Size', 'Name', 'Hint', 'Categories', 'Patterns')
                              for row in incoming.children()):
        raise NotImplementedError('unsupported ASC library metadata')
    patterns = rows(incoming.one('Patterns'), 'Pattern')
    _count(incoming.one('Size'), len(patterns))
    categories = incoming.one('Categories')
    unpack_categories(categories)
    document = new_library(incoming.scalar('Name'), hint=incoming.scalar('Hint'))
    library = document.one('/Library')
    with assembly(document):
        library.one('Categories').detach()
        library.append(categories.detach())
    pattern_defaults, pad_defaults = footprint_objects.new_pattern(), footprint_objects.new_pad()
    inputs = []
    for pattern in patterns:
        pattern.detach()
        _pattern(pattern)
        fill_defaults(pattern, pattern_defaults=pattern_defaults, pad_defaults=pad_defaults)
        imported = normalize(pattern,
            pad_indices=active_pad_indices(pattern),
            shape_indices=[index for index, shape in enumerate(pattern.select('Shapes/Shape')) if shape['Type'] > 0],
            hole_indices=[index for index, hole in enumerate(pattern.select('Holes/Hole')) if hole.values[0]])
        with assembly(document):
            library.one('Patterns').append(pattern)
        inputs.append(imported)
    establish_records(document.root)
    _audit(document.root)
    return finish(document, inputs)
