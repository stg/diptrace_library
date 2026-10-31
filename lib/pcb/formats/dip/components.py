"""Initial PCB component and footprint records, before revision extensions."""
from dataclasses import dataclass
from decimal import Decimal
import math

from ....common.model import Element, Value, SourceSpan
from ....common.footprint_codec import read_holes, read_model, read_pad_geometry, read_pad_mask_states
from ....common.dimension_codec import read_dimensions
from ....common.conversion import import_notice
from .preamble import _fields


@dataclass(frozen=True)
class DrawingUpgrade:
    shape: Element
    geometry: tuple
    orientation: int
    text_marker: bool


@dataclass(frozen=True)
class ComponentUpgrade:
    component: Element
    legacy_markings: tuple
    legacy_text_positions: tuple
    legacy_field_bindings: tuple
    drawings: tuple


def normalize_legacy_linkage(component, version):
    """Resolve early standalone marker identifiers before object classification."""
    if version >= 35 or component['HiddenId'] < 20000:
        return
    kind = component.one('Pattern')['Type']
    pad_marker = (kind == 14 and component['Name'].lower() == 'pad'
                  and component['RefDes'].rstrip('0123456789 ').lower() == 'pad')
    if kind == 15 or pad_marker:
        component.one('HiddenId').set_values(-1)
        import_notice('info', 'legacy-component-linkage',
                      'Cleared an obsolete standalone schematic-link identifier.', (component,),
                      recoverability='physical objects and connections retain their identities')


def _component_head(reader, component):
    pattern = component.add('Pattern')
    _fields(reader, component, 'boolean', 'Enabled Selected')
    _fields(reader, pattern, 'integer', 'Type Number1 Number2')
    orientation = reader.integer()
    component.add('Angle', orientation*math.pi/2)
    _fields(reader, component, 'integer', 'Group Number')
    reader.field(pattern, 'PadShape', 'integer')
    reader.field(pattern, 'SurfacePad', 'boolean')
    markings = tuple(reader.integer() for _ in range(4))
    positions = tuple(reader.number() for _ in range(4))
    reader.field(component, 'BottomSide', 'boolean')
    reader.field(component, 'ConnectedLayer', 'integer')
    reader.field(component, 'Flipped', 'boolean')
    reader.field(component, 'HiddenId', 'integer')
    _fields(reader, pattern, 'number', 'OriginX OriginY')
    origin = reader.argument('boolean')
    pattern.add('OriginCommon', Value(0 if origin.value else 1, 'number', source=origin.source))
    reader.field(component, 'HorizontalFlip', 'boolean')
    fields = component.add('UserFields')
    for _ in range(reader.count('component user fields')):
        reader.record(fields, 'UserField', 'text', 'text', 'integer')
    field_bindings = (reader.integer(), reader.integer(), reader.number())
    reader.field(component, 'Locked', 'boolean')
    reader.field(component, 'LibPath', 'text')
    reader.field(component, 'GsType', 'integer')
    points = pattern.add('PadPoints')
    for _ in range(reader.count('default pad contour points')):
        reader.record(points, 'pt', 'number', 'number')
    _fields(reader, pattern, 'boolean', 'VariableParameter1 VariableParameter2 VariableParameter3 VariableParameter4')
    _fields(reader, component, 'number', 'X Y')
    _fields(reader, pattern, 'number', 'Spacing1 Spacing2')
    reader.field(pattern, 'VariableParameter5', 'boolean')
    reader.field(pattern, 'Spacing3', 'number')
    reader.field(pattern, 'LockProperties', 'boolean')
    reader.field(component, 'PanelExclude', 'boolean')
    reader.field(pattern, 'PatternOrientation', 'integer')
    reader.field(component, 'ViaStyle', 'integer')
    pattern.set_values(reader.argument('text'))
    width, height = reader.argument('number'), reader.argument('number')
    if orientation % 2:
        width, height = height, width
    pattern.add('Width', width)
    pattern.add('Height', height)
    _fields(reader, pattern, 'number', 'PadWidth PadHeight PadHole PadHoleH')
    reader.field(pattern, 'PadHoleType', 'integer')
    hierarchy = component.add('HierarchyPath')
    if reader.header.version > 31:
        for _ in range(reader.count('component hierarchy path')):
            reader.record(hierarchy, 'Item', 'integer')
    _fields(reader, component, 'text', 'Name RefDes Value BaseName')
    normalize_legacy_linkage(component, reader.header.version)
    return pattern, reader.count('component pads'), markings, positions, field_bindings


def read_pads(reader, pattern, count):
    pads = pattern.add('Pads')
    for index in range(count):
        start = reader.pos
        inverted = reader.argument('boolean')
        number, net = reader.argument('integer'), reader.argument('integer')
        x, y = reader.argument('number'), reader.argument('number')
        label, name = reader.argument('text'), reader.argument('text')
        pad = pads.add('Pad', index, label, name, x, y)
        pad.add('Number_New', number)
        pad.add('NetNumber', net)
        pad.add('PadAngle', Value(Decimal(str(math.pi/2)) if inverted.value else Decimal(0),
                                 'number', source=inverted.source))
        read_pad_geometry(reader, pad)
        reader.boolean()  # Obsolete pad selection slot; current output writes false.
        for name in ('HideLayer', 'BlindLayer'):
            layers = pad.add(name)
            for _ in range(reader.count(name)):
                reader.record(layers, 'Item', 'integer')
        spokes = pad.add('CustomSpokes')
        for _ in range(reader.count('custom thermal settings')):
            reader.record(spokes, 'CustomSpoke', 'integer', 'integer', 'integer', 'number')
        reader.field(pad, 'Locked', 'boolean')
        read_pad_mask_states(reader, pad)
        _fields(reader, pad, 'number', 'CustomSwell_New CustomShrink_New')
        reader.field(pad, 'Sided', 'boolean')
        pad.source = SourceSpan('dip', start, reader.pos, reader.source)
    return pads


def _graphics(reader, pattern, *, text_markers=True):
    shapes = pattern.add('Shapes')
    upgrades = []
    for index in range(reader.count('footprint drawings')):
        start = reader.pos
        shape = shapes.add('Shape', index)
        kind = reader.integer()
        marker = text_markers and kind == 700
        shape.add('Type', 7 if marker else kind)
        geometry = tuple(reader.number() for _ in range(6))
        reader.field(shape, 'Locked', 'boolean')
        reader.field(shape, 'Layer', 'integer')
        shape.add('TextLine').add('pt', reader.argument('text'))
        reader.field(shape, 'FontName', 'text')
        reader.field(shape, 'VectorFont', 'boolean')
        reader.field(shape, 'FontSize', 'integer')
        _fields(reader, shape, 'number', 'FontScale FontWidth')
        orientation = reader.integer()
        reader.field(shape, 'TextShow', 'integer')
        reader.field(shape, 'Width', 'number')
        points = shape.add('Points_New')
        for _ in range(reader.count('footprint drawing points')):
            reader.record(points, 'pt', 'number', 'number')
        shape.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(DrawingUpgrade(shape, geometry, orientation, marker))
    read_holes(reader, pattern)
    read_dimensions(reader, pattern)
    return tuple(upgrades)


def read_base_components(reader, board, count):
    """Decode the initial component section; return transient upgrade inputs.

    Revision extensions and compatibility upgrades must run before this boundary
    data can become a complete editable PCB document.
    """
    components = board.add('Components')
    upgrades = []
    for _ in range(count):
        start = reader.pos
        component = components.add('Component')
        pattern, pad_count, markings, positions, user = _component_head(reader, component)
        read_pads(reader, pattern, pad_count)
        drawings = _graphics(reader, pattern)
        read_model(reader, pattern)
        component.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(ComponentUpgrade(component, markings, positions, user, drawings))
    return tuple(upgrades)
