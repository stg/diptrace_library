"""Selection envelopes over editable symbol geometry and vector-name metrics.

Pin bodies use their connection line and the symbol's longitudinal reach. Pin
names use readable horizontal/vertical lettering with an optional alternate
orientation about the text's start corner. Number labels are separate from this
group-selection envelope. Drawing strokes do not enlarge it.

The scalar reaches and clearances are measurable with ordinary one-pin fixtures:
hide the name to isolate each public pin symbol, then show a known-width name
and subtract its width from the selected group's far edge. Repeat in the four
orientations and with independent name shifts/rotation. A distant marker and
calibrated selection-rectangle coordinates recover the opposite extrema. These
are our own geometry operations and semantic measurements, not font contours.
"""
from .geometry import Bounds
from .text.vector_layout import pin_name_metrics


# Public pin types: Open/Open High/Open Low/3 State/Clock share a head reach.
_OPEN_HEADS = frozenset((5, 6, 7, 8, 13))
_OTHER_REACH = {9: 6., 10: 4., 11: 5., 12: 6., 14: 6.51}
_WIDE_NAME_CLEARANCE = frozenset((9, 12, 14))
_INWARD = ((1, 0), (0, 1), (-1, 0), (0, -1))


def pin_bounds(pin, *, measure_name=None):
    """Return an unplaced pin's group envelope without changing authored data.

    measure_name optionally returns TextMetrics for a pin. It affects only this
    calculation; the record retains its own name and font choices.
    """
    x, y, length = float(pin['X']), float(pin['Y']), float(pin['Length'])
    orientation = pin['Orientation']
    if orientation not in range(4):
        raise ValueError('pin envelope requires a cardinal orientation')
    kind = pin['Type']
    reach = 4.52 if kind in _OPEN_HEADS else _OTHER_REACH.get(kind, 0.)
    ux, uy = _INWARD[orientation]
    vx, vy = -uy, ux
    body = Bounds.from_points(((x-length*ux, y-length*uy), (x, y), (x+reach*ux, y+reach*uy)))
    if not pin['ShowName']:
        return body
    metrics = (measure_name or pin_name_metrics)(pin)
    width, height = metrics.width, metrics.height
    gap = 8.5 if kind in _WIDE_NAME_CLEARANCE else 6.5 if kind > 4 else 3.
    along, across = float(pin['PinNameXShift']), float(pin['PinNameYShift'])
    # Start from the same readable placement in every orientation. Changing
    # text orientation rotates at this corner rather than realigning its box.
    far_anchor = ((0., 0.), (0., width), (-width, 0.), (0., 0.))[orientation]
    half_height = (-height/2, 0.) if orientation % 2 else (0., -height/2)
    anchor = (x+ux*(gap+along)+vx*across+far_anchor[0]+half_height[0],
              y+uy*(gap+along)+vy*across+far_anchor[1]+half_height[1])
    vertical = bool(orientation % 2) != (pin['PinNameRotate'] == 1)
    advance, down = ((0., -width), (height, 0.)) if vertical else ((width, 0.), (0., height))
    corners = (anchor, (anchor[0]+advance[0], anchor[1]+advance[1]),
               (anchor[0]+down[0], anchor[1]+down[1]),
               (anchor[0]+advance[0]+down[0], anchor[1]+advance[1]+down[1]))
    return body.union(Bounds.from_points(corners))
