"""Shared standalone ASC scalars, pad records and generated layer views."""
from . import footprint_records as physical
from .asc_footprints import unpack_terminals
from .asc_library import rows
from .pad_masks import MASK_FIELDS, mask_state


def _boolean(value, path):
    if type(value) is bool:
        return value
    if value not in ('Y', 'N'):
        raise ValueError(f'{path}: expected boolean Y or N')
    return value == 'Y'


def _flags(owner, schema):
    for name, field in schema.fields.items():
        node = owner.child(name)
        if node is None:
            continue
        if field.kind == 'boolean':
            if len(node.values) != 1 or node.children():
                raise ValueError(f'{node.path}: expected one boolean')
            node.set_values(_boolean(node.values[0], node.path))


def _count(container, expected=None):
    expected = len(container.children()) if expected is None else expected
    if len(container.values) != 1 or type(container.values[0]) is not int or container.values[0] != expected:
        raise ValueError(f'{container.path}: count does not match rows')
    container.set_values()


def _rename(owner, old, new):
    node = owner.one(old)
    if owner.child(new) is not None:
        raise ValueError(f'{owner.path}: duplicate {old}/{new}')
    node.kind = new


def _terminals(owner):
    unpack_terminals(owner)
    owner.one('PadTerminalCount').detach()
    for terminal in owner.children('PadTerminal'):
        points = terminal.one('ShapePoints')
        _count(points)


def _pad(pad):
    if len(pad.values) != 5:
        raise ValueError(f'{pad.path}: expected five pad header values')
    for name in MASK_FIELDS:
        field = pad.one(name)
        if len(field.values) not in (2, 3):
            raise ValueError(f'{field.path}: expected a mask-state tuple')
        _boolean(field.values[0], field.path)
        field.set_values(field.arguments[-1])
        field.set_values(mask_state(pad, name))
    for name in ('Number', 'Inverted', 'PadWidth', 'PadHeight', 'PadShape', 'CustomSwell', 'CustomShrink'):
        pad.one(name).detach()
    if pad.child('PadPoints_New') is not None:
        pad.one('Points').detach()
    else:
        _rename(pad, 'Points', 'PadPoints_New')
    _terminals(pad)
    _flags(pad, physical.PAD)
    pad.bind_schema(physical.PAD)


def _default_pad_geometry(pattern):
    """Keep the current default shape and contour, consuming older projections."""
    for name in ('PadShape', 'PadWidth', 'PadHeight'):
        pattern.one(name).detach()
        _rename(pattern, name+'_New', name)
    if pattern.one('PadAngle').values != (0,):
        raise NotImplementedError('nonzero default-pad ASC angle has no verified current mapping')
    pattern.one('PadAngle').detach()
    if pattern.child('PadPoints_New') is not None:
        pattern.one('PadPoints').detach()
        _rename(pattern, 'PadPoints_New', 'PadPoints')


def _layers(pattern, *, members=('Pads', 'Shapes', 'Holes')):
    """Consume the generated layer/member view, not another copy of the objects."""
    layers = pattern.one('Layers')
    if layers.values:
        raise ValueError(f'{layers.path}: unexpected layer header')
    for layer in rows(layers, 'Layer'):
        if layer.values or any(node.kind not in ('Enabled', 'Number', *members)
                               for node in layer.children()):
            raise ValueError(f'{layer.path}: unexpected layer data')
        _boolean(layer.scalar('Enabled'), layer.path)
        if type(layer.scalar('Number')) is not int:
            raise ValueError(f'{layer.path}: expected a layer number')
        for name in members:
            collection = layer.child(name)
            if collection is None:
                continue
            if collection.values:
                raise ValueError(f'{collection.path}: unexpected member header')
            for member in rows(collection, 'pt'):
                if len(member.values) != 1 or type(member.values[0]) is not int or member.children():
                    raise ValueError(f'{member.path}: expected one object index')
    layers.detach()
