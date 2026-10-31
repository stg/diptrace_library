"""XML pad styles from shared physical geometry, terminals and mask data."""
from .xml_footprint_vocabulary import MASK_STATES, PASTE_STATES
from .xml_pad_shapes import shape_label
from .xml import set_attribute
from .xml_output import enum_text, numeric, point_attributes
from .model import Element
from .pad_masks import mask_state


def _stack(target, source, *, units, terminal=False):
    individual = source.kind == 'Pad'
    shape_name = 'Type' if terminal else 'PadShape_New' if individual else 'PadShape'
    width_name = 'ShapeWidth' if terminal else 'PadWidth_New' if individual else 'PadWidth'
    height_name = 'ShapeHeight' if terminal else 'PadHeight_New' if individual else 'PadHeight'
    shape = source.scalar(shape_name)
    label = shape_label(shape, terminal=terminal)
    set_attribute(target, 'Shape', label)
    for name, own in (('Width', width_name), ('Height', height_name)):
        set_attribute(target, name, numeric(units.length(source.one(own).arguments[0])))
    # A style can retain settings for another shape or pad type. Those remain
    # editable data even while the selected geometry does not use them.
    corner = source.one('ShapeCorner' if terminal else 'PadCorner').arguments[0]
    if shape == 2 or corner.value != 0:
        set_attribute(target, 'Corner', corner)
    if not terminal and (not source.scalar('SurfacePad') or
            any(source.scalar(name) != 0 for name in ('PadShape_X', 'PadShape_Y'))):
        point_attributes(target, source.one('PadShape_X').arguments[0], source.one('PadShape_Y').arguments[0],
                         units, names=('XOff', 'YOff'))
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
    # Hole settings remain valid optional data on surface styles and in round
    # mode. Emit both dimensions so an omitted height cannot inherit the width.
    set_attribute(result, 'HoleType', enum_text(source.scalar('PadHoleType'), ('Round', 'Obround')))
    for public, own in (('Hole', 'PadHole'), ('HoleH', 'PadHoleH')):
        set_attribute(result, public, numeric(units.length(source.one(own).arguments[0])))
    _stack(result.add('MainStack'), source, units=units)
    terminals = source.children('PadTerminal')
    if terminals:
        target = result.add('Terminals')
        for terminal in terminals:
            item = target.add('Terminal')
            point_attributes(item, terminal.one('X').arguments[0], terminal.one('Y').arguments[0], units)
            set_attribute(item, 'Angle', terminal.one('Angle').arguments[0])
            _stack(item, terminal, units=units, terminal=True)
    if (masks := project_mask_paste(source, units=units)) is not None:
        result.append(masks)
    return result


def project_mask_paste(source, *, units, complete=False):
    """Project mask/paste choices for a style or a placed-pad overlay.

    A complete overlay supplies even common modes and empty segment lists, so
    it cannot accidentally inherit different values from a physical template.
    """
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
    if complete or any(state for _, state, _ in states) or swell.value != -1000 or shrink.value != -1000:
        target = Element('MaskPaste')
        for public, state, labels in states:
            if complete or state > 0:
                set_attribute(target, public, enum_text(state, labels))
        if complete or any(state == 3 for _, state, _ in states[2:]):
            for public, own in (('Segment_Percent', 'PadMask_Percent'), ('Segment_EdgeGap', 'PadMask_EdgeGap'),
                                ('Segment_Gap', 'PadMask_SegmentGap'), ('Segment_Side', 'PadMask_SegmentSide')):
                value = source.one(own).arguments[0]
                set_attribute(target, public, value if public == 'Segment_Percent' else numeric(units.length(value)))
        for public, value in (('CustomSwell', swell), ('CustomShrink', shrink)):
            if value.value != -1000:
                set_attribute(target, public, numeric(units.length(value)))
        for public, own in (('TopSegments', 'PadMask_TopSegments'), ('BotSegments', 'PadMask_BotSegments')):
            segments = source.select(own+'/pt')
            if complete or segments:
                parent = target.add(public)
                for segment in segments:
                    if len(segment.arguments) != 4:
                        raise ValueError(f'{segment.path}: paste segment requires two points')
                    item = parent.add('Item')
                    for side in (0, 1):
                        point_attributes(item, *segment.arguments[side*2:side*2+2], units,
                                         names=('X'+str(side+1), 'Y'+str(side+1)))
        return target
    return None
