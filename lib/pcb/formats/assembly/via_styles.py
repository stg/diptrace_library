"""Resolve imported static-via geometry from its selected board style."""
from ....common.conversion import import_notice
from ...model.static_via import pad_geometry
from ..errors import PcbError


def source_span(through, first, last, layer_count):
    """Resolve saved span positions before binding current layer identities."""
    if through:
        return None
    last = min(last, layer_count-1)
    first = min(first, last-1)
    if not 0 <= first < last < layer_count:
        raise PcbError('via span does not identify two copper layers')
    return first, last


def normalize_static_vias(board):
    """Apply the selected style without replacing the pad or its connections.

    Import still has boundary pads and positional style/layer selectors. Their
    current identities are bound afterward. Mask, thermal, naming and placement
    data remain independent of the circular size, hole and copper span.
    """
    styles = board.select('ViaStyles/ViaStyle')
    layer_count = len(board.select('Layers/Layer'))
    changed = []
    for component in board.select('Components/Component'):
        pattern = component.one('Pattern')
        index = component.get('ViaStyle', -1)
        if (not component.get('Enabled', True) or pattern['Type'] != 16 or
                not 0 <= index < len(styles)):
            continue
        pads = pattern.select('Pads/Pad')
        if len(pads) < 3:
            continue
        pad = pads[1]
        _, through, size, hole, first, last = styles[index].values
        span = source_span(through, first, last, layer_count)
        excluded = [] if span is None else [layer for layer in range(layer_count)
                                           if not span[0] <= layer <= span[1]]
        altered = False
        for owner, fields in (
            (pattern, dict(Width=size, Height=size, PadWidth=size, PadHeight=size)),
            (pad, pad_geometry(size, hole)),
        ):
            for name, value in fields.items():
                if owner.get(name) != value:
                    owner.set_field(name, value)
                    altered = True
        layers = pad.child('BlindLayer')
        current = [row.values[0] for row in layers.children('Item')] if layers is not None else []
        if current != excluded:
            if layers is None:
                layers = pad.add('BlindLayer')
            for row in tuple(layers.children('Item')):
                row.detach()
            for position in excluded:
                layers.add('Item', position)
            altered = True
        if altered:
            changed.append(pad)
    if changed:
        import_notice('info', 'static-via-style',
                      'Resolved static-via size, circular hole and copper span from the selected style.',
                      changed, recoverability='pad identity, placement, connectivity and independent options remain')
