"""Normalize explicit public pad styles into own default/individual geometry."""
from .import_library_values import (read_points)
from .import_values import (enum_value, length, point, replace_rows)
from .pads import (PAD_SHAPES, MASK_STATES, PASTE_STATES)
from ....common.model import (Element)
from ...model.new import (fields)


def _stack(record, owner, *, units, terminal=False):
    individual = owner.kind == 'Pad'
    label = record.value('Shape', 'Ellipse')
    kind = '' if label.value == '' else enum_value(label, PAD_SHAPES[:5] if terminal else PAD_SHAPES)
    own = 'Type' if terminal else 'PadShape_New' if individual else 'PadShape'
    owner.set_field(own, kind)
    for public, own in (('Width', 'ShapeWidth' if terminal else 'PadWidth_New' if individual else 'PadWidth'),
                        ('Height', 'ShapeHeight' if terminal else 'PadHeight_New' if individual else 'PadHeight')):
        owner.set_field(own, length(record.number(public, 0), units))
    owner.set_field('ShapeCorner' if terminal else 'PadCorner', record.number('Corner', 0))
    if not terminal:
        for own, value in zip(('PadShape_X', 'PadShape_Y'), point(record, units, ('XOff', 'YOff'), 0)):
            owner.set_field(own, value)
    container = 'ShapePoints' if terminal else 'PadPoints_New' if individual else 'PadPoints'
    replace_rows(owner, container, read_points(record, units=units))


def read_pad_style(record, owner, *, units):
    name = record.text('Name', '')
    kind = enum_value(record.value('Type', 'Through'), ('Surface', 'Through'))
    side = enum_value(record.value('Side', 'Top'), ('Top', 'Bottom'))
    if kind not in (0, 1) or side not in (0, 1):
        raise ValueError(f'{record.node.path}: unsupported pad type or side')
    owner.set_field('SurfacePad', kind == 0)
    sided = owner.set_field('Sided', side == 1)
    if owner.kind == 'Pattern' and not side:
        sided.annotations['asc_omit'] = 'XML default pad side; no binary pattern default-side field'
    owner.set_field('PadHoleType', enum_value(record.value('HoleType', 'Round'), ('Round', 'Obround')))
    owner.set_field('PadHole', length(record.number('Hole', 0), units))
    owner.set_field('PadHoleH', length(record.number('HoleH', 0), units))
    main = record.take('MainStack', required=True)
    _stack(main, owner, units=units)
    main.finish()
    for index, source in enumerate(record.rows('Terminals', 'Terminal')):
        terminal = owner.add('PadTerminal', index)
        fields(terminal, X=0, Y=0, Angle=source.number('Angle', 0))
        terminal.add('ShapePoints')
        for own, value in zip(('X', 'Y'), point(source, units, default=0)):
            terminal.set_field(own, value)
        _stack(source, terminal, units=units, terminal=True)
        source.finish()
    masks = record.take('MaskPaste')
    if masks is not None:
        for public, default, own, labels in (
                ('TopMask', 'TopMask_State', 'DisableTopMask', MASK_STATES),
                ('BotMask', 'BotMask_State', 'DisableBottomMask', MASK_STATES),
                ('TopPaste', 'TopPaste_State', 'DisableTopPaste', PASTE_STATES),
                ('BotPaste', 'BotPaste_State', 'DisableBottomPaste', PASTE_STATES)):
            state = enum_value(masks.value(public, 'Common'), labels)
            if owner.kind == 'Pad':
                owner.one(own).set_values(state)
            else:
                owner.set_field(default, state)
        for public, own, default in (('Segment_Percent', 'PadMask_Percent', 50),
                                    ('Segment_EdgeGap', 'PadMask_EdgeGap', 0),
                                    ('Segment_Gap', 'PadMask_SegmentGap', 0), ('Segment_Side', 'PadMask_SegmentSide', 0)):
            value = masks.number(public, default)
            owner.set_field(own, value if public == 'Segment_Percent' else length(value, units))
        for public, own in (('CustomSwell', 'CustomSwell_New'), ('CustomShrink', 'CustomShrink_New')):
            owner.set_field(own, length(masks.number(public), units) if masks.has(public) else -1000)
        for public, own in (('TopSegments', 'PadMask_TopSegments'), ('BotSegments', 'PadMask_BotSegments')):
            rows = []
            for source in masks.rows(public, 'Item'):
                rows.append(Element('pt', *point(source, units, ('X1', 'Y1')), *point(source, units, ('X2', 'Y2'))))
                source.finish()
            replace_rows(owner, own, rows)
        masks.finish()
    record.finish()
    return name
