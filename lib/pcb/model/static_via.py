"""Current physical data implied by a selected static-via style."""
from dataclasses import replace

from ...common import footprint_records
from ...common.footprint_objects import new_pattern, new_pad
from ...common.model import Element
from ...common.schema import MISSING
from ...common.pad_masks import MASK_DATA_FIELDS, MASK_COLLECTIONS
from ...common.references import Property, ReferenceError
from . import definitions


def pad_geometry(size, hole):
    """The circular through-hole geometry controlled by a via style."""
    return dict(PadWidth_New=size, PadHeight_New=size, PadHole=hole, PadHoleH=hole,
                PadShape_New=0, SurfacePad=False, PadHoleType=0, PadCorner=0,
                PadShape_X=0, PadShape_Y=0)


DIMENSION_FIELDS = {'PadWidth_New': 'Size', 'PadHeight_New': 'Size',
                    'PadHole': 'HoleSize', 'PadHoleH': 'HoleSize'}
PATTERN_SIZE_FIELDS = ('Width', 'Height', 'PadWidth', 'PadHeight')


def controlled(component):
    return component['Enabled'] and component.one('Pattern')['Type'] == 16


def reference_projection(reference):
    """The component's style link owns its pad's dependent dimensions."""
    component = reference.source
    if reference.role != 'via-style' or component.kind != 'Component':
        return reference
    if not controlled(component) and not reference.indices:
        return reference
    pattern = component.one('Pattern')
    pads = component.select('Pattern/Pads/Pad')
    fields = {pattern.one(name) for name in PATTERN_SIZE_FIELDS}
    fields.update(pad.one(name) for pad in pads for name in DIMENSION_FIELDS)
    if any(not isinstance(item, Property) or item.field not in fields for item in reference.indices):
        raise ReferenceError('component via-style projections are owned by its physical pad')
    if not controlled(component):
        return replace(reference, indices=())
    if len(pads) != 1:
        raise ReferenceError('a selected static-via style requires exactly one physical pad')
    return replace(reference, indices=tuple(Property(pattern.one(name), 'Size') for name in PATTERN_SIZE_FIELDS)
                   + tuple(Property(pads[0].one(name), source) for name, source in DIMENSION_FIELDS.items()))


def edit_references(document, named):
    components = set()
    for node, name in named:
        if node.kind == 'Pattern' and name == 'Type' and node.parent is not None and node.parent.kind == 'Component':
            components.add(node.parent)
        elif node.kind == 'Component' and name == 'Enabled':
            components.add(node)
    return tuple(replacement for component in components
                 for reference in document.references.outgoing(component, role='via-style')
                 if (replacement := reference_projection(reference)) != reference)


def validate_reference(reference):
    component = reference.source
    if reference.role != 'via-style' or component.kind != 'Component' or not controlled(component):
        return
    pattern = component.one('Pattern')
    pads = pattern.select('Pads/Pad')
    if len(pads) != 1:
        raise ReferenceError('a selected static-via style requires exactly one physical pad')
    fixed = {name: value for name, value in pad_geometry(0, 0).items() if name not in DIMENSION_FIELDS}
    if any(pads[0][name] != value for name, value in fixed.items()):
        raise ReferenceError('selected static-via geometry must use its circular style; remove Via before editing it independently')
    if component._owner()._automatic_structure:
        from .via_layers import validate_structure
        validate_structure(component)


def validate_fields(document, named):
    components = set()
    for node, name in named:
        if node.kind == 'Pad' and name in pad_geometry(0, 0):
            pattern = node.parent.parent if node.parent is not None else None
            if (pattern is not None and pattern.kind == 'Pattern' and pattern.parent is not None
                    and pattern.parent.kind == 'Component'):
                components.add(pattern.parent)
        elif node.kind == 'Pattern' and name == 'Type' and node.parent is not None and node.parent.kind == 'Component':
            components.add(node.parent)
        elif node.kind == 'Component' and name == 'Enabled':
            components.add(node)
    for component in components:
        for reference in document.references.outgoing(component, role='via-style'):
            validate_reference(reference)


def conflicting_components(board):
    """Find local geometry which a receiving editor replaces from its style."""
    layers = board.select('Layers/Layer')
    for component in board.select('Components/Component'):
        pattern = component.one('Pattern')
        if not component['Enabled'] or pattern['Type'] != 16:
            continue
        style = component['Via']
        if style is None:
            continue
        pads = pattern.select('Pads/Pad')
        if not pads:
            continue
        pad = pads[0]
        expected = pad_geometry(style['Size'], style['HoleSize'])
        span = style['Span']
        excluded = (set() if span is None else
                    {layer for layer in layers if not style['Lay1'] <= layer._ordinal() <= style['Lay2']})
        actual = {row['Layer'] for row in pad.select('BlindLayer/Item')}
        if any(pad[name] != value for name, value in expected.items()) or actual != excluded:
            yield component


def pattern_for(style):
    """Construct current one-pad geometry, without saved-array boundary rows."""
    size, hole = style['Size'], style['HoleSize']
    pattern = new_pattern('').bind_schema(definitions.PATTERN)
    for name in ('InternalConnections', 'Pattern_Groups', 'UserFields', 'Pattern_Manufacturer'):
        if (child := pattern.child(name)) is not None:
            child.detach()
    for name, value in dict(Type=16, Mounting=0, Width=size, Height=size, PadWidth=size, PadHeight=size,
                            PadHole=hole, PadHoleH=hole).items():
        pattern[name] = value
    pad = new_pad('1')
    pad.one('Number_New').detach()
    for name, value in dict(PadWidth_New=size, PadHeight_New=size,
                            PadHole=hole, PadHoleH=hole, Standard=True).items():
        pad[name] = value
    pattern.one('Pads').append(pad)
    # Ownership selects the placed hole/dimension collection schemas. Use a
    # temporary current-model owner, then return the independently typed pattern.
    owner = Element('Component', '', '')
    owner.append(pattern)
    definitions.establish_records(owner)
    pattern.detach()
    return pattern


def _facts(node, schema=None):
    schema = node.schema if schema is None else schema
    if schema is None:
        if node.arguments or node.children():
            raise ValueError(f'{node.path}: physical recipe requires typed content')
        return ()
    fields = []
    placed_pad = schema is footprint_records.PAD
    for name, field in schema.fields.items():
        if (field.getter is not None or name == 'Number_New' or
                placed_pad and name in (*MASK_DATA_FIELDS, 'Standard')):
            continue
        if node.child(name) is None and field.default is MISSING:
            value = MISSING
        else:
            value = node.get(name, None if field.default is MISSING else field.default)
        fields.append((name, value))
    children = []
    for name in schema.children:
        if placed_pad and name in MASK_COLLECTIONS:
            continue
        # A pad's electrical/layer overrides are emitted on its placement. The
        # same is true of via mask/paste. Remaining physical geometry compares.
        rows = node.children(name)
        children.append((name, tuple(_facts(row, footprint_records.PAD if row.kind == 'Pad' else None)
                                     for row in rows)))
    return tuple(fields), tuple(children)


def matches(pattern, style):
    """True only when the style recipe reproduces every current physical fact."""
    if pattern['Type'] != 16:
        return False
    return _facts(pattern, footprint_records.PATTERN) == _facts(pattern_for(style), footprint_records.PATTERN)
