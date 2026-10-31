"""Public ASC geometry into the shared editable schematic representation.

Flat footprint drawing siblings become owned drawing records. Compatibility
coordinates remain typed facts; current physical points remain authoritative.
"""
from ....common.asc_footprints import unpack_model, unpack_terminals, unpack_pattern_shapes
from ....common.pad_masks import mask_state


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


from ...model.pads import (empty_pad)


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

