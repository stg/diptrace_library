"""Import standalone component ASC into the same owned model as ELI."""
from ....common import footprint_records as physical, symbol_records
from ....common.asc_footprints import unpack_model, unpack_pattern_shapes
from ....common.asc_library import loads_library, loads_library_bytes, rows, unpack_categories
from ....common.asc_library_import import (_boolean, _flags, _rename, _terminals,
    _pad, _layers, _default_pad_geometry)
from ....common.asc_model_body import unpack_model_body
from ....common.asc_symbols import unpack_symbol_shape
from ....common.conversion import import_diagnostics
from ....common.errors import UnsupportedFileError
from ..import_components import construct_library
from ..revisions import ASCII_READ_VERSIONS


def _known(owner, fields, children=()):
    for child in owner.children():
        if child.kind not in fields and child.kind not in children:
            raise NotImplementedError(f'{child.path}: unimplemented component ASC field')


def _categories(owner, prefix):
    for name in ('Name', 'Index', 'Types'):
        _rename(owner, 'Category'+name, prefix+'_Category'+name)
    for row in rows(owner.one(prefix+'_CategoryTypes'), 'CategoryType'):
        if row.children() or len(row.values) != 4:
            raise ValueError(f'{row.path}: expected four classification values')


def _groups(owner, name):
    for group in rows(owner.one(name), 'pt'):
        if len(group.values) != 4 or group.children():
            raise ValueError(f'{group.path}: expected four group values')
        group.set_values(_boolean(group.values[0], group.path), *group.arguments[1:])


def _part(part):
    if len(part.values) != 2 or any(not isinstance(value, str) for value in part.values):
        raise ValueError(f'{part.path}: expected component name and RefDes')
    for old, new in (('OriginX', 'Origin_X'), ('OriginY', 'Origin_Y')):
        _rename(part, old, new)
    _categories(part, 'Component')
    _layers(part, members=('Pins', 'Shapes'))
    unpack_model_body(part.one('ModelBody'))
    flags = part.one('Verification')
    if len(flags.values) != 7 or flags.children():
        raise ValueError(f'{flags.path}: expected seven verification flags')
    flags.set_values(*(_boolean(value, flags.path) for value in flags.values))
    _flags(part, symbol_records.SYMBOL)
    _groups(part, 'Groups')
    for index, pin in enumerate(rows(part.one('Pins'), 'Pin')):
        if len(pin.values) != 3 or pin.values[0] != index:
            raise ValueError(f'{pin.path}: expected consecutive pin index and XY position')
        _rename(pin, 'PinNamexShift', 'PinNameXShift')
        if pin.child('NameFontMono') is None:
            pin.add('NameFontMono', False)
        _flags(pin, symbol_records.PIN)
        _known(pin, symbol_records.PIN.fields, symbol_records.PIN.children)
        pin.bind_schema(symbol_records.PIN)
    for index, shape in enumerate(rows(part.one('Shapes'), 'Shape')):
        if shape.values != (index,):
            raise ValueError(f'{shape.path}: expected a consecutive drawing index')
        _rename(shape, 'Width', 'PenWidth')
        unpack_symbol_shape(shape)
        # ASC's first line and orientation repeat current text and angle data.
        for name in ('Name', 'Orientation'):
            if (field := shape.child(name)) is not None:
                field.detach()
        if shape.child('FontMono') is None:
            shape.add('FontMono', False)
        _flags(shape, symbol_records.DRAWING)
        _known(shape, symbol_records.DRAWING.fields, symbol_records.DRAWING.children)
        shape.bind_schema(symbol_records.DRAWING)
    _known(part, symbol_records.SYMBOL.fields, symbol_records.SYMBOL.children)
    part.bind_schema(symbol_records.SYMBOL)


def _pattern(pattern):
    if len(pattern.values) != 1 or not isinstance(pattern.values[0], str):
        raise ValueError(f'{pattern.path}: expected a footprint name')
    _categories(pattern, 'Pattern')
    _rename(pattern, 'Manufacturer', 'Pattern_Manufacturer')
    for suffix in ('Cross', 'Circle', 'Common', 'Courtyard'):
        _rename(pattern, 'Origin_'+suffix, 'Origin'+suffix)
    _default_pad_geometry(pattern)
    _terminals(pattern)
    _layers(pattern)
    pads = rows(pattern.one('Pads'), 'Pad')
    for index, pad in enumerate(pads):
        if not pad.values or pad.values[0] != index:
            raise ValueError(f'{pad.path}: expected consecutive pad slot indices')
        _rename(pad, 'Point', 'Points')
        _pad(pad)
    shapes = pattern.one('Shapes')
    for row in shapes.children('Point'):
        row.kind = 'Points'
    unpack_pattern_shapes(shapes, text_lines_counted=True,
                          header_fields=(('Layer', 2), ('TextAngle', 15)))
    for shape in shapes.children('Shape'):
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
    _groups(pattern, 'Pattern_Groups')
    unpack_model(pattern.one('Model3D'))
    _flags(pattern.one('Model3D'), physical.MODEL3D)
    _flags(pattern, physical.PATTERN)
    _known(pattern, physical.PATTERN.fields, physical.PATTERN.children)
    pattern.bind_schema(physical.PATTERN)


@import_diagnostics('asc')
def parse(data, *, source=None, encoding=None):
    syntax = (loads_library(data, source=source, retain_source=False) if isinstance(data, str) else
              loads_library_bytes(data, source=source, encoding=encoding, retain_source=False))
    if [node.kind for node in syntax.root.children()] != ['Source', 'Library']:
        raise ValueError('expected one Source declaration followed by one Library')
    declaration = syntax.one('/Source').values
    if len(declaration) != 2 or declaration[0] != 'DipTrace-ElementLibrary':
        raise UnsupportedFileError(format='asc', family='component', reason='format')
    if declaration[1] not in ASCII_READ_VERSIONS:
        raise UnsupportedFileError(format='asc', family='component', version=declaration[1], reason='version')
    library = syntax.one('/Library')
    _known(library, (), ('Name', 'Hint', 'Subfolders', 'Categories', 'Components'))
    unpack_categories(library.one('Categories'))
    for folder in rows(library.one('Subfolders'), 'Subfolder'):
        if len(folder.values) != 1 or folder.children() or not isinstance(folder.values[0], str):
            raise ValueError(f'{folder.path}: expected one folder name')
        folder.kind = 'Folder'
    for component in rows(library.one('Components'), 'Component'):
        _known(component, (), ('Part', 'Pattern'))
        parts = component.children('Part')
        pattern = component.one('Pattern')
        if not parts:
            raise ValueError('component library entry has no parts')
        _pattern(pattern)
        pattern.detach()
        collection = component.add('Parts')
        for index, part in enumerate(parts):
            _part(part)
            part.move_to(collection)
            if index == 0:
                part.append(pattern)
    name, hint = library.scalar('Name'), library.scalar('Hint')
    return construct_library(library.detach(), name=name, hint=hint)
