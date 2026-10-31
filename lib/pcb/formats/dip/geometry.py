"""Resolve supported footprint geometry and origin settings during import."""
import math

from ....common.footprint_geometry import expand_normalized_drawing
from ....common.symbol_geometry import expand_legacy_drawing
from ....common.conversion import import_notice


def modernize_drawings(decoded, *, text_layout=None):
    """Run the format's geometry upgrade once, before current-model binding."""
    from .board_drawings import modernize_board_drawings
    modernize_board_drawings(decoded)
    modernize_pattern_origins(decoded)
    expand_pattern_drawings(decoded)
    if decoded.header.version < 47:
        for item in decoded.upgrades.components:
            _legacy_placement_defaults(item.component)
        from ....common.text.layout import default_layout
        from .legacy_labels_import import modernize_markings
        modernize_markings(decoded, layout=text_layout or default_layout())
        from .legacy_geometry import rebase_components
        rebase_components(decoded)
        for item in decoded.upgrades.cached_definitions:
            _legacy_defaults(item.definition.one('Pattern'))
            for shape in item.definition.select('Part/Shapes/Shape'):
                expand_legacy_drawing(shape, orientation=shape['Orientation'])
                shape.add('Group', -1)


def modernize_pattern_origins(decoded):
    """Resolve supported earlier origin choices into current display settings."""
    changed = []
    for item in decoded.upgrades.components:
        pattern = item.component.one('Pattern')
        values = (dict(OriginCross=True, OriginCircle=True, OriginCommon=1, OriginCourtyard=0)
                  if decoded.header.version < 47 else
                  {'OriginCommon': 1} if pattern.scalar('OriginCommon') == 2 else {})
        if any(pattern.scalar(name) != value for name, value in values.items()):
            changed.append(pattern)
        for name, value in values.items():
            pattern.set_field(name, value)
    if changed:
        import_notice('info', 'pattern-origin-normalization',
                      'Modernized footprint origin display settings.', changed)


def expand_pattern_drawings(decoded):
    """Expand placed and cached patterns before schema 47, in adapter state."""
    if decoded.header.version >= 47:
        return
    cleared = []
    patterns = [(item.component.one('Pattern'), item.drawings, item.component['BottomSide'])
                for item in decoded.upgrades.components]
    patterns.extend((item.definition.one('Pattern'), item.pattern_inputs, False)
                    for item in decoded.upgrades.cached_definitions)
    for pattern, drawings, bottom_side in patterns:
        size = pattern['Width'], pattern['Height']
        for item in drawings:
            shape = item.shape
            kind = shape['Type']
            geometry = shape.one('Points_New')
            controls = tuple(zip(item.geometry[::2], item.geometry[1::2]))
            current_kind, points = expand_normalized_drawing(kind, controls,
                [point.values for point in geometry.children('pt')], size,
                text_orientation=item.orientation, text_mirrored=bottom_side)
            if current_kind != kind:
                shape.one('Type').set_values(current_kind)
            for point in tuple(geometry.children()):
                point.detach()
            for point in points:
                geometry.add('pt', *point)
            for name, value in (
                    ('TextAngle', item.orientation*math.pi/2 if kind == 7 else 0),
                    ('TextHorz', -1 if kind == 7 else 0),
                    ('TextVert', -1 if kind == 7 else 0),
                    ('TextAlign', -1), ('LineSpacing', 1.2),
                    ('AllLayers', False), ('Group', -1)):
                field = shape.child(name)
                if field is None:
                    shape.add(name, value)
                else:
                    field.set_values(value)
            if item.text_marker:
                # The older tag denotes calculated label geometry, not an
                # independently authored text drawing. Current marking
                # settings reconstruct it after the inactive slot is removed.
                shape.one('Type').set_values(0)
                cleared.append(shape)
    if cleared:
        import_notice('info', 'legacy-generated-marking',
                      'Removed older calculated marking placeholders.', cleared,
                      recoverability='current component marking settings reconstruct the labels')


def _defaults(owner, values):
    for name, value in values.items():
        if owner.child(name) is None:
            owner.add(name, value)


def _legacy_placement_defaults(component):
    _legacy_defaults(component.one('Pattern'), placed=True)
    _defaults(component, dict(CustomMarkingFont=False, MarkingFontSize=5, MarkingFontAll=False))


def _legacy_defaults(pattern, *, placed=False):
    """Supply current physical settings absent from pre-47 footprint records."""
    values = dict(OriginCross=True, OriginCircle=True, OriginCommon=1,
        OriginCourtyard=0, Name_Description='', Name_Unique='', RecoveryCode='',
        RecoveryCode_Generator=True, RecoveryCode_Model=True,
        PadCorner=0, PadShape_X=0, PadShape_Y=0, TopMask_State=0, BotMask_State=0,
        TopPaste_State=0, BotPaste_State=0, CustomSwell_New=-1000, CustomShrink_New=-1000,
        PadMask_Percent=50, PadMask_EdgeGap=.9, PadMask_SegmentGap=.6, PadMask_SegmentSide=3)
    if not placed:
        values['Pattern_Manufacturer'] = ''
    _defaults(pattern, values)
    for pad in pattern.select('Pads/Pad'):
        _defaults(pad, dict(Group=-1, PadCorner=0, PadShape_X=0, PadShape_Y=0,
            PadMask_Percent=50, PadMask_EdgeGap=.9, PadMask_SegmentGap=.6, PadMask_SegmentSide=3))
    for dimension in pattern.select('Dimensions/Dimension'):
        _defaults(dimension, {'Group': -1})
