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
    pattern = reader.add(component, 'Pattern')
    _fields(reader, component, 'boolean', 'Enabled Selected')
    _fields(reader, pattern, 'integer', 'Type Number1 Number2')
    orientation = reader.integer()
    reader.add_into(component, 'Angle', orientation*math.pi/2)
    _fields(reader, component, 'integer', 'Group Number')
    reader.field_into(pattern, 'PadShape', 'integer')
    reader.field_into(pattern, 'SurfacePad', 'boolean')
    markings = tuple(reader.integer() for _ in range(4))
    positions = tuple(reader.number() for _ in range(4))
    reader.field_into(component, 'BottomSide', 'boolean')
    reader.field_into(component, 'ConnectedLayer', 'integer')
    reader.field_into(component, 'Flipped', 'boolean')
    reader.field_into(component, 'HiddenId', 'integer')
    _fields(reader, pattern, 'number', 'OriginX OriginY')
    origin = reader.argument('boolean')
    reader.add_into(pattern, 'OriginCommon', Value(0 if origin.value else 1, 'number', source=origin.source))
    reader.field_into(component, 'HorizontalFlip', 'boolean')
    fields = reader.add(component, 'UserFields')
    for _ in range(reader.count('component user fields')):
        reader.record(fields, 'UserField', 'text', 'text', 'integer')
    field_bindings = (reader.integer(), reader.integer(), reader.number())
    reader.field_into(component, 'Locked', 'boolean')
    reader.field_into(component, 'LibPath', 'text')
    reader.field_into(component, 'GsType', 'integer')
    points = reader.add(pattern, 'PadPoints')
    reader.points(points, reader.count('default pad contour points'))
    _fields(reader, pattern, 'boolean', 'VariableParameter1 VariableParameter2 VariableParameter3 VariableParameter4')
    _fields(reader, component, 'number', 'X Y')
    _fields(reader, pattern, 'number', 'Spacing1 Spacing2')
    reader.field_into(pattern, 'VariableParameter5', 'boolean')
    reader.field_into(pattern, 'Spacing3', 'number')
    reader.field_into(pattern, 'LockProperties', 'boolean')
    reader.field_into(component, 'PanelExclude', 'boolean')
    reader.field_into(pattern, 'PatternOrientation', 'integer')
    reader.field_into(component, 'ViaStyle', 'integer')
    pattern.set_values(reader.argument('text'))
    width, height = reader.argument('number'), reader.argument('number')
    if orientation % 2:
        width, height = height, width
    reader.add_into(pattern, 'Width', width)
    reader.add_into(pattern, 'Height', height)
    _fields(reader, pattern, 'number', 'PadWidth PadHeight PadHole PadHoleH')
    reader.field_into(pattern, 'PadHoleType', 'integer')
    hierarchy = reader.add(component, 'HierarchyPath')
    if reader.header.version > 31:
        for _ in range(reader.count('component hierarchy path')):
            reader.record(hierarchy, 'Item', 'integer')
    _fields(reader, component, 'text', 'Name RefDes Value BaseName')
    normalize_legacy_linkage(component, reader.header.version)
    return pattern, reader.count('component pads'), markings, positions, field_bindings


def read_pads(reader, pattern, count):
    pads = reader.add(pattern, 'Pads')
    for index in range(count):
        start = reader.pos
        inverted = reader.argument('boolean')
        number, net = reader.argument('integer'), reader.argument('integer')
        x, y = reader.argument('number'), reader.argument('number')
        label, name = reader.argument('text'), reader.argument('text')
        pad = reader.add(pads, 'Pad', index, label, name, x, y)
        reader.add_into(pad, 'Number_New', number)
        reader.add_into(pad, 'NetNumber', net)
        reader.add_into(pad, 'PadAngle', Value(Decimal(str(math.pi/2)) if inverted.value else Decimal(0),
                                 'number', source=inverted.source))
        read_pad_geometry(reader, pad)
        reader.boolean()  # Obsolete pad selection slot; current output writes false.
        for name in ('HideLayer', 'BlindLayer'):
            layers = reader.add(pad, name)
            for _ in range(reader.count(name)):
                reader.record(layers, 'Item', 'integer')
        spokes = reader.add(pad, 'CustomSpokes')
        for _ in range(reader.count('custom thermal settings')):
            reader.record(spokes, 'CustomSpoke', 'integer', 'integer', 'integer', 'number')
        reader.field_into(pad, 'Locked', 'boolean')
        read_pad_mask_states(reader, pad)
        _fields(reader, pad, 'number', 'CustomSwell_New CustomShrink_New')
        reader.field_into(pad, 'Sided', 'boolean')
        pad.source = SourceSpan('dip', start, reader.pos, reader.source)
    return pads


def _graphics(reader, pattern, *, text_markers=True):
    shapes = reader.add(pattern, 'Shapes')
    upgrades = []
    for index in range(reader.count('footprint drawings')):
        start = reader.pos
        shape = reader.add(shapes, 'Shape', index)
        kind = reader.integer()
        marker = text_markers and kind == 700
        reader.add_into(shape, 'Type', 7 if marker else kind)
        geometry = tuple(reader.number() for _ in range(6))
        reader.field_into(shape, 'Locked', 'boolean')
        reader.field_into(shape, 'Layer', 'integer')
        reader.add_into(reader.add(shape, 'TextLine'), 'pt', reader.argument('text'))
        reader.field_into(shape, 'FontName', 'text')
        reader.field_into(shape, 'VectorFont', 'boolean')
        reader.field_into(shape, 'FontSize', 'integer')
        _fields(reader, shape, 'number', 'FontScale FontWidth')
        orientation = reader.integer()
        reader.field_into(shape, 'TextShow', 'integer')
        reader.field_into(shape, 'Width', 'number')
        points = reader.add(shape, 'Points_New')
        reader.points(points, reader.count('footprint drawing points'))
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
    components = reader.add(board, 'Components')
    upgrades = []
    for _ in range(count):
        start = reader.pos
        component = reader.add(components, 'Component')
        pattern, pad_count, markings, positions, user = _component_head(reader, component)
        read_pads(reader, pattern, pad_count)
        drawings = _graphics(reader, pattern)
        read_model(reader, pattern)
        component.source = SourceSpan('dip', start, reader.pos, reader.source)
        upgrades.append(ComponentUpgrade(component, markings, positions, user, drawings))
    return tuple(upgrades)
