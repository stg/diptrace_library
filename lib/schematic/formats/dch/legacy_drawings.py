"""Convert old normalized footprint drawings into editable physical geometry.

The adapter owns only version-specific choices. Scaling and ellipse sampling use
ordinary geometry operations; no format scratch records or allocator are used.
"""
import math

from ...model.traversal import (footprints, symbols)
from ....common.footprint_geometry import expand_normalized_drawing
from ....common.symbol_geometry import expand_legacy_drawing
from .data import (stored_data)


def expand_symbol_drawings(version, schematic):
    """Give old symbol and schematic drawings their editable modern geometry."""
    if version >= 40:
        return
    owners = list(symbols(schematic)) + [schematic]
    for owner in owners:
        shapes = owner.child('Shapes')
        for shape in shapes.children('Shape') if shapes else ():
            expand_symbol_drawing(shape)
            if owner.parent is not None and owner.parent.kind == 'Components' and shape.scalar('MarkingGenerated'):
                clear_legacy_marking(shape)


def clear_legacy_marking(shape):
    """The old placed marking is regenerated later, from current label data."""
    for name, value in (('Enabled', False), ('Type', 0)):
        shape.set_field(name, value)
    for point in tuple(shape.child('Points_New').children('pt')):
        point.detach()
    lines = shape.child('TextLine')
    if lines is not None:
        for line in tuple(lines.children()):
            line.detach()
    shape.set_field('MarkingGenerated', False)


def expand_symbol_drawing(shape):
    """Resolve the DCH orientation input for shared symbol modernization."""
    stored = shape.child('StoredData')
    orientation = shape.scalar('Orientation', stored.scalar('Orientation', 0) if stored is not None else 0)
    expand_legacy_drawing(shape, orientation=orientation)


def expand_pattern_drawings(version, schematic):
    if version >= 40:
        return
    for pattern in footprints(schematic):
        scale = float(pattern.scalar('Width')), float(pattern.scalar('Height'))
        shapes = pattern.child('Shapes').children('Shape')
        for index, shape in enumerate(shapes):
            if (pattern.parent.kind == 'Part' and shape.scalar('Type') < 0
                    and index not in (0, len(shapes)-1)):
                shape.annotations['asc_omit'] = 'disabled interior footprint drawing'
            expand_drawing(shape, scale)


def expand_drawing(shape, scale):
    """Upgrade one drawing using the original footprint's coordinate scale."""
    kind = shape.scalar('Type')
    stored = stored_data(shape)
    raw = tuple(map(float, stored.child('CompatibilityGeometry').values))
    corners = tuple(zip(raw[::2], raw[1::2]))
    geometry = shape.child('Points_New')
    current_kind, physical = expand_normalized_drawing(kind, corners,
        [point.values for point in geometry.children('pt')], scale,
        text_orientation=stored.scalar('TextOrientation') if kind == 7 else 0)
    if current_kind != kind:
        shape.set_field('Type', current_kind)
    for point in tuple(geometry.children()):
        point.detach()
    for x, y in physical:
        geometry.add('pt', x, y)
    orientation = stored.scalar('TextOrientation') if kind == 7 else 0
    for name, value in (('TextAngle', orientation*math.pi/2),
                        ('TextHorz', -1 if kind == 7 else 0),
                        ('TextVert', -1 if kind == 7 else 0), ('TextAlign', -1),
                        ('LineSpacing', 1.2), ('AllLayers', False), ('Group', -1)):
        shape.add(name, value).annotations['derived_from'] = 'legacy drawing settings'
    for name in ('CompatibilityGeometry', 'CompatibilityPoints', 'TextOrientation', 'Type'):
        for field in stored.children(name):
            field.detach()
    if not stored.children() and not stored.arguments:
        stored.detach()
