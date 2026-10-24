"""Import the public schema-46 schematic ASC view into the shared data model.

ASC is a projection: it lacks title grids, supplier quotes and several earlier
wire facts. This adapter declares its empty/default choices in ordinary editable
elements. It cannot recover an original binary that was not supplied.
"""
from ...model.document import (Document)
from ....common.model import (Element)
from ..dch.data import (stored_data)
from .import_graphics import (unpack_pattern, unpack_symbol_shape)
from .import_cache import (unpack_cache)
from .model_body import (unpack_model_body)
from ...model.cell_text import (unpack_asc_cell_text)


BOOLEAN_FIELDS = set('''Enabled Selected Connected Locked Inverted SurfacePad
Standard Sided VectorFont DefVectorFont FOrientation HideBorder OriginEnabled
OriginCross OriginCircle RecoveryCode_Generator RecoveryCode_Model AllLayers
LockProperties AllowParts FConnect ShowName Hidden NoConnect HorzFlip VertFlip
ShowOrigin ShowUnits CustomMarkingFont MarkingFontAll ShowPart MarkingGenerated Mirror
NoSearch KeepPins UniteByName ConnectPinByName Global CustomColor CanUnhide
HidePower PartFontVector ProjectLibs_Sorted MainSupplier Picture_Proportions
GridEnabled GridSnap DisplayTitles DisplaySheet BusConNetName BusConNetNumber
ShowPinNumbers HidePinNumbers BusConAbove BusConBelow UnitsMM UnitsMIL UnitsINCH
ERC_PinType ERC_NotConnected ERC_SinglePin ERC_Short ERC_PinSuperimpose
UsePartFontColor ZoneBorder Zones VariableParameter1 VariableParameter2
VariableParameter3 VariableParameter4 VariableParameter5 signal_plotted
signal_visible'''.split())
MASK_FIELDS = ('DisableTopMask', 'DisableBottomMask', 'DisableTopPaste', 'DisableBottomPaste')


def _boolean(node, index):
    value = node.values[index]
    if isinstance(value, bool):
        return
    if value not in ('Y', 'N'):
        raise ValueError(f'{node.path}: expected boolean Y or N at argument {index}')
    node.set_argument(index, value == 'Y')


def _booleans(root):
    for node in root.walk():
        name = node.kind.removeprefix('cl_')
        parent = node.parent.kind.removeprefix('cl_') if node.parent else ''
        if name in BOOLEAN_FIELDS and len(node.arguments) == 1:
            _boolean(node, 0)
        if name in MASK_FIELDS:
            _boolean(node, 0)
        if name in ('Verification', 'Edges'):
            for index in range(len(node.arguments)):
                _boolean(node, index)
        if name == 'Hole':
            _boolean(node, 0)
            _boolean(node, 1)
        if name == 'DifferentialPair':
            _boolean(node, 1)
            _boolean(node, 5)
        if name == 'pt' and parent in ('Groups', 'Pattern_Groups'):
            _boolean(node, 0)
        if name == 'pt' and parent == 'Model3D':
            for index in (9, 10, 17):
                _boolean(node, index)
        if name == 'Shape' and len(node.arguments) == 18:
            _boolean(node, 1)
            _boolean(node, 11)


def _default(parent, name, *values, omit=False):
    node = parent.add(name, *values)
    node.annotations['generated_default'] = 'not present in public schematic ASC'
    if omit:
        node.annotations['asc_omit'] = 'not present in public schematic ASC'
    return node


def _pages(schematic):
    pages = schematic.one('Pages')
    for page in pages.children('Page'):
        _default(page, 'FontLineWidth', -2, omit=True)
        titles = _default(page, 'TitleBlocks', omit=True)
        for index in range(6):
            grid = titles.add('TitleBlock', index, '')
            grid.add('Width', 0)
            grid.add('Height', 0)
            for name in ('ColWidths', 'RowHeights', 'Cells', 'Contents'):
                grid.add(name)


def _paths(schematic):
    for name, kind in (('ProjectLibs_Folders', 'Folder'), ('ProjectLibs_Libs', 'Lib')):
        container = schematic.one(name)
        records = container.children()
        if len(records) % 2:
            raise ValueError(f'{container.path}: expected actual/variable path pairs')
        for actual, variable in zip(records[::2], records[1::2]):
            if actual.kind != kind or variable.kind != kind+'_Variable':
                raise ValueError(f'{container.path}: expected {kind}/{kind}_Variable siblings')
            variable.kind = 'VariablePath'
            variable.move_to(actual)


def _tables(schematic):
    for table in schematic.select('Tables/Table'):
        columns = len(table.select('ColWidths/pt'))
        rows = len(table.select('RowHeights/pt'))
        cells = table.select('Cells/Cell')
        if len(cells) != columns*rows:
            raise ValueError(f'{table.path}: cells do not form the declared rectangle')
        for index, cell in enumerate(cells):
            if cell.values[:3] != (rows, index//rows, index % rows) or len(cell.arguments) != 7:
                raise ValueError(f'{cell.path}: invalid ASC cell coordinates/placement')
            cell.set_values(*cell.arguments[3:])
            unpack_asc_cell_text(cell)


def import_schematic(document):
    """Return detached owned data, explicitly filling ASC's omitted fields.

    Supports the public schematic-46 dialect only. Unknown fields are retained;
    projection validation rejects unsupported public content before encoding.
    The returned metadata never claims that a binary file was decoded.
    """
    if document.representation != 'asc':
        raise ValueError('ASC schematic input is required')
    if document.one('/Source').values != ('DipTrace-Schematic', 46):
        raise ValueError('semantic ASC input supports DipTrace-Schematic version 46')
    document.rebuild(force=False)
    view = Document(document.root.clone(), representation='schematic')
    view._automatic_structure = False
    _booleans(view.root)
    units = view.one('/Units')
    if len(units.arguments) != 1 or units.values[0] not in ('mm', 'mil', 'in'):
        raise ValueError('ASC display units must be mm, mil or in')
    units.detach()
    schematic = view.one('/Schematic')
    _pages(schematic)
    _paths(schematic)
    _tables(schematic)
    for part in schematic.select('Components/Part'):
        unpack_model_body(part.one('ModelBody'))
        for shape in part.select('Shapes/Shape'):
            unpack_symbol_shape(shape)
        unpack_pattern(part.one('Pattern'))
        supplier = part.one('Suppliers')
        _default(supplier, 'SourceLocator', '', omit=True)
        _default(supplier, 'Prices', omit=True)
    for index, shape in enumerate(schematic.select('Shapes/Shape')):
        shape.set_values(index)
        unpack_symbol_shape(shape)
        orientation = shape.child('Orientation')
        if orientation is not None:
            orientation.move_to(stored_data(shape))
    for index, node in enumerate(schematic.select('Nets/Net')):
        field = _default(node, 'HiddenId', index, omit=True)
    unpack_cache(schematic)
    from ..dch.labels import (discard_legacy_label_slots)
    discard_legacy_label_slots(schematic)
    from ...model.drawing_data import (normalize_drawings)
    normalize_drawings(schematic)
    from ...model.fonts import (complete_fonts)
    from ...model.simulation import (complete_options, modernize_arguments)
    complete_fonts(schematic)
    complete_options(schematic.one('ssimulator'))
    modernize_arguments(schematic)
    from ...model.schema import (validate_public_content)
    validate_public_content(view)
    view.metadata.update(source_format='schematic', imported_from='asc',
                         source_version=46,
                         missing_data_policy='declared defaults',
                         binary_consumed=False)
    from ...model.refs import (bind_schematic_references)
    from ...model.user_fields import (modernize_user_field_names)
    modernize_user_field_names(schematic)
    from ...model.cell_text import (modernize_cell_text)
    modernize_cell_text(schematic)
    bind_schematic_references(view)
    from ...model.symbol_text import (refresh_symbol_text)
    refresh_symbol_text(view)
    view.rebuild(force=False)
    from ...editing.route_normalization import (normalize_imported_routes)
    normalize_imported_routes(view)
    for node in view.root.walk(include_self=True):
        if node.kind in ('', 'Part', 'Pattern', 'Shape', 'Model3D', 'Definition', 'CacheLib', 'Pad'):
            node.annotations['requires_asc_projection'] = True
        node._syntax = None
        node._dirty = False
        node._reordered = False
    view._automatic_structure = True
    return view

