"""XML pad styles from named default-pad and individual-pad geometry."""
from .dchxml import set_attribute
from .dchxml_settings import enum_text, numeric
from .dchxml_symbols import point_attributes
from .model import Element
from .pad_data import mask_state


PAD_SHAPES = ('Ellipse', 'Obround', 'Rectangle', 'Polygon', 'D-shape', 'Fiducial')
MASK_STATES = ('Common', 'Open', 'Tented', 'By Paste')
PASTE_STATES = ('Common', 'Solder', 'No Solder', 'Segments')
PAD_STYLE_FIELDS = '''SurfacePad Sided PadHoleType PadHole PadHoleH PadShape
PadWidth PadHeight PadCorner PadShape_X PadShape_Y PadPoints PadTerminalCount
PadTerminal TopMask_State BotMask_State TopPaste_State BotPaste_State
CustomSwell_New CustomShrink_New PadMask_Percent PadMask_EdgeGap
PadMask_SegmentGap PadMask_SegmentSide PadMask_TopSegments PadMask_BotSegments'''.split()


def _stack(target, source, *, units, terminal=False):
    individual = source.kind == 'Pad'
    shape_name = 'Type' if terminal else 'PadShape_New' if individual else 'PadShape'
    width_name = 'ShapeWidth' if terminal else 'PadWidth_New' if individual else 'PadWidth'
    height_name = 'ShapeHeight' if terminal else 'PadHeight_New' if individual else 'PadHeight'
    shape = source.scalar(shape_name)
    label = '' if shape == '' else enum_text(shape, PAD_SHAPES[:5] if terminal else PAD_SHAPES)
    set_attribute(target, 'Shape', label)
    for name, own in (('Width', width_name), ('Height', height_name)):
        set_attribute(target, name, numeric(units.length(source.one(own).arguments[0])))
    if shape == 2:
        set_attribute(target, 'Corner', source.one('ShapeCorner' if terminal else 'PadCorner').arguments[0])
    if not terminal and not source.scalar('SurfacePad'):
        point_attributes(target, source.one('PadShape_X').arguments[0], source.one('PadShape_Y').arguments[0],
                         units, names=('XOff', 'YOff'))
    if shape == 3:
        container = 'ShapePoints' if terminal else 'PadPoints_New' if individual else 'PadPoints'
        points = source.select(container+'/pt')
        if points:
            result = target.add('Points')
            for point in points:
                point_attributes(result.add('Item'), *point.arguments, units)


def project_pad_style(source, *, name, units):
    result = Element('PadStyle')
    set_attribute(result, 'Name', name)
    surface = source.scalar('SurfacePad')
    set_attribute(result, 'Type', 'Surface' if surface else 'Through')
    set_attribute(result, 'Side', 'Bottom' if source.scalar('Sided', False) else 'Top')
    if not surface:
        hole_type = source.scalar('PadHoleType')
        set_attribute(result, 'HoleType', enum_text(hole_type, ('Round', 'Obround')))
        set_attribute(result, 'Hole', numeric(units.length(source.one('PadHole').arguments[0])))
        if hole_type:
            set_attribute(result, 'HoleH', numeric(units.length(source.one('PadHoleH').arguments[0])))
    _stack(result.add('MainStack'), source, units=units)
    terminals = source.children('PadTerminal')
    if terminals:
        target = result.add('Terminals')
        for terminal in terminals:
            item = target.add('Terminal')
            point_attributes(item, terminal.one('X').arguments[0], terminal.one('Y').arguments[0], units)
            set_attribute(item, 'Angle', terminal.one('Angle').arguments[0])
            _stack(item, terminal, units=units, terminal=True)
    individual = source.kind == 'Pad'
    states = []
    for public, default, own, labels in (
            ('TopMask', 'TopMask_State', 'DisableTopMask', MASK_STATES),
            ('BotMask', 'BotMask_State', 'DisableBottomMask', MASK_STATES),
            ('TopPaste', 'TopPaste_State', 'DisableTopPaste', PASTE_STATES),
            ('BotPaste', 'BotPaste_State', 'DisableBottomPaste', PASTE_STATES)):
        state = mask_state(source,own) if individual else source.scalar(default)
        states.append((public, state, labels))
    swell, shrink = (source.one(name).arguments[0] for name in ('CustomSwell_New', 'CustomShrink_New'))
    if any(state for _, state, _ in states) or swell.value != -1000 or shrink.value != -1000:
        target = result.add('MaskPaste')
        for public, state, labels in states:
            if state > 0:
                set_attribute(target, public, enum_text(state, labels))
        if any(state == 3 for _, state, _ in states[2:]):
            for public, own in (('Segment_Percent', 'PadMask_Percent'), ('Segment_EdgeGap', 'PadMask_EdgeGap'),
                                ('Segment_Gap', 'PadMask_SegmentGap'), ('Segment_Side', 'PadMask_SegmentSide')):
                value = source.one(own).arguments[0]
                set_attribute(target, public, value if public == 'Segment_Percent' else numeric(units.length(value)))
        for public, value in (('CustomSwell', swell), ('CustomShrink', shrink)):
            if value.value != -1000:
                set_attribute(target, public, numeric(units.length(value)))
        for public, own in (('TopSegments', 'PadMask_TopSegments'), ('BotSegments', 'PadMask_BotSegments')):
            segments = source.select(own+'/pt')
            if segments:
                parent = target.add(public)
                for segment in segments:
                    if len(segment.arguments) != 4:
                        raise ValueError(f'{segment.path}: paste segment requires two points')
                    item = parent.add('Item')
                    for side in (0, 1):
                        point_attributes(item, *segment.arguments[side*2:side*2+2], units,
                                         names=('X'+str(side+1), 'Y'+str(side+1)))
    return result
