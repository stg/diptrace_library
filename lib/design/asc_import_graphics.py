"""Public ASC geometry into the shared editable schematic representation.

Flat footprint drawing siblings become owned drawing records. Compatibility
coordinates remain typed facts; current physical points remain authoritative.
"""
from .model import Element
from .pad_data import mask_state


def unpack_terminals(parent):
    count = parent.one('PadTerminalCount')
    terminals = count.children('PadTerminal')
    if count.values != (len(terminals),):
        raise ValueError(f'{count.path}: terminal count does not match records')
    for index, terminal in enumerate(terminals):
        terminal.set_values(index)
        terminal.move_to(parent)


def unpack_model(model):
    values = model.one('pt').arguments
    if len(values) != 18:
        raise ValueError(f'{model.path}: expected 18 model placement values')
    model.one('pt').detach()
    for index, name in enumerate(('Rotate', 'Offset', 'Zoom')):
        vector = model.add(name)
        for axis, value in zip(('X', 'Y', 'Z'), values[index*3:index*3+3]):
            vector.add(axis, value)
    for name, value in zip(('Mirror', 'NoSearch', 'Units', 'IPC_XOff', 'IPC_YOff',
                           'AutoHeight', 'AutoColor', 'Type', 'KeepPins'), values[9:]):
        model.add(name, value)


def unpack_pattern_shapes(container):
    records, current = [], None
    for record in list(container.children()):
        if record.kind == 'Shape':
            if len(record.arguments) != 18:
                raise ValueError(f'{record.path}: expected 18 footprint drawing values')
            current = record
            records.append((record, []))
        elif current is None:
            raise ValueError(f'{record.path}: footprint field precedes its Shape')
        else:
            records[-1][1].append(record)
    for index, (shape, siblings) in enumerate(records):
        header = shape.arguments
        shape.set_values(index)
        shape.add('Type', header[0])
        shape.add('Locked', header[1])
        shape.add('FontName', header[10])
        shape.add('VectorFont', header[11])
        shape.add('FontSize', header[12])
        shape.add('FontScale', header[13])
        shape.add('FontWidth', header[14])
        shape.add('TextShow', header[17])
        for sibling in siblings:
            sibling.move_to(shape)
        # The named pen setting replaces the header's older occurrence. If
        # absent, the header supplies the current width, not a second choice.
        if shape.child('Width') is None:
            shape.add('Width', header[16])
        points = shape.child('Points')
        if points is not None:
            points.detach()
        if shape.child('Points_New') is None:
            shape.add('Points_New')
        if shape.child('TextLine') is None:
            shape.add('TextLine').add('pt', header[9])
        shape.add('PadId', -1).annotations['asc_omit'] = 'not present in ASC'


def unpack_symbol_shape(shape):
    """Keep current text and physical points; discard superseded point views."""
    for name in ('Points',):
        field = shape.child(name)
        if field is not None:
            field.detach()
    if shape.child('Points_New') is None:
        shape.add('Points_New')
    if shape.child('TextLine') is None:
        lines = shape.add('TextLine')
        if shape.scalar('Name', ''):
            lines.add('pt', shape.scalar('Name'))


def empty_pad(index):
    """An explicit empty boundary slot, absent from placed-footprint ASC."""
    pad = Element('Pad', index, '', '', 0, 0)
    zero = '''Number_New PadAngle PadWidth_New PadHeight_New PadHole PadHoleH
PadHoleType PadShape_New PadCorner PadShape_X PadShape_Y PadTerminalCount'''.split()
    for name in zero:
        pad.add(name, 0)
    for name in ('SurfacePad', 'Standard', 'Locked', 'Sided'):
        pad.add(name, False)
    pad.add('Group', -1)
    pad.add('PadPoints_New')
    for name in ('DisableTopMask', 'DisableBottomMask', 'DisableTopPaste', 'DisableBottomPaste'):
        pad.add(name, 0)
    for name in ('CustomSwell_New', 'CustomShrink_New'):
        pad.add(name, -1000)
    for name, value in (('PadMask_Percent', 50), ('PadMask_EdgeGap', .9),
                        ('PadMask_SegmentGap', .6), ('PadMask_SegmentSide', 3)):
        pad.add(name, value)
    for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
        pad.add(name, 0)
    pad.annotations.update(reserved=True, asc_omit='empty boundary pad',
                           generated_default='boundary pad omitted from ASC')
    return pad


def unpack_pad(pad):
    orientation=pad.child('Inverted')
    if orientation is not None:
        orientation.detach()
    for name in ('DisableTopMask', 'DisableBottomMask', 'DisableTopPaste', 'DisableBottomPaste'):
        field=pad.one(name)
        if len(field.arguments) not in (2,3):
            raise ValueError(f'{field.path}: expected an ASC mask-state tuple')
        field.set_values(field.arguments[-1])
        field.set_values(mask_state(pad,name))
    if pad.child('PadPoints_New') is None:
        current = pad.add('PadPoints_New')
        legacy = pad.child('Points')
        if legacy is not None:
            for point in legacy.children('pt'):
                current.append(point.clone())
    for name in ('Number','PadWidth','PadHeight','PadShape','Points','CustomSwell','CustomShrink'):
        for field in pad.children(name):
            field.detach()
    unpack_terminals(pad)


def unpack_pattern(pattern, *, cached=False):
    unpack_model(pattern.one('Model3D'))
    unpack_terminals(pattern)
    pads = pattern.one('Pads')
    if not cached:
        # Public pad headers use the physical array positions, starting at one.
        for index, pad in enumerate(pads.children('Pad'), 1):
            if pad.values[0] != index:
                raise ValueError(f'{pad.path}: noncontiguous placed pad indices')
        pads.insert(empty_pad(0), 0)
        pads.append(empty_pad(len(pads.children('Pad'))))
    for pad in pads.children('Pad'):
        if not pad.annotations.get('reserved'):
            unpack_pad(pad)
    unpack_pattern_shapes(pattern.one('Shapes'))
    for index, dimension in enumerate(pattern.select('Dimensions/Dimension')):
        dimension.set_values(index)

