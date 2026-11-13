"""Resolve older rotated-pad thermal choices into current layer-linked data.

This runs once during binary import, after geometry and references are current.
It neither fills pours nor changes their boundaries or calculated geometry.
"""
import math

from ....common.conversion import import_notice
from ....common.geometry import transform_point


def _orientation_map(angle):
    # Older spoke choices use the placement axes. These two compatibility
    # intervals distinguish diagonal and perpendicular placements respectively.
    if abs(math.remainder(float(angle)/(math.pi/2), 1)) > .45:
        return {1: 3, 2: 3, 3: 4, 4: 3}
    if abs(math.remainder(float(angle)/math.pi, 1)) > .49:
        return {1: 2, 2: 1}
    return None


def _contains(point, vertices):
    """Even-odd containment with half-open edges and no coordinate perturbation."""
    if len(vertices) < 3:
        return False
    x, y = point
    inside = False
    ax, ay = vertices[-1]
    for bx, by in vertices:
        if (ay < y <= by) or (by < y <= ay):
            crossing = ax+(y-ay)*(bx-ax)/(by-ay)
            if x > crossing:
                inside = not inside
        ax, ay = bx, by
    return inside


def _on_layer(component, pad, layer, layers):
    if pad['SurfacePad']:
        bottom = component['BottomSide'] != pad['Sided']
        return layer is layers[-1 if bottom else 0]
    return all(layer is not row['Layer'] for group in ('HideLayer', 'BlindLayer')
               for row in pad.select(group+'/Item'))


def modernize_thermals(document, *, version, placements):
    """Consume pre-47 choices on the supplied current, positional input pads.

    placements is a transient import iterator of (component, eligible pads).
    Saved-key validity stays with the importer; this transformation works on
    ordinary current properties and layer/net identities only.
    """
    if version >= 47:
        return ()
    board = document.one('/Board')
    layers = tuple(board.select('Layers/Layer'))
    pours_by_net = {}
    for pour in board.select('CopperPours/CopperPour'):
        if pour['Enabled'] and pour['Net'] is not None and pour['Layer'] is not None:
            pours_by_net.setdefault(pour['Net'], []).append(pour)
    if not pours_by_net or not layers:
        return ()
    polygons, changed = {}, []
    for component, pads in placements:
        if not component['Enabled']:
            continue
        for pad in pads:
            pours = pours_by_net.get(pad['Net'])
            if not pours or (mapping := _orientation_map(component['Angle']+pad['PadAngle'])) is None:
                continue
            rows = pad.select('CustomSpokes/CustomSpoke')
            modified = False
            for row in rows:
                before = row['Spoke']
                if (after := mapping.get(before, before)) != before:
                    row['Spoke'] = after
                    modified = True
            covered = {row['Layer'] for row in rows}
            if None not in covered:
                world = None
                for pour in pours:
                    layer = pour['Layer']
                    if layer in covered or not _on_layer(component, pad, layer, layers):
                        continue
                    if world is None:
                        world = transform_point((pad['X'], pad['Y']),
                            origin=(component['X'], component['Y']), angle=component['Angle'])
                    if pour not in polygons:
                        polygons[pour] = tuple((float(p['X']), float(p['Y']))
                                               for p in pour.select('Points/pt'))
                    if not _contains(world, polygons[pour]):
                        continue
                    # The first applicable pour supplies the older default.
                    # It still has precedence when its choice needs no upgrade.
                    if (spoke := mapping.get(pour['Spoke'])) is not None:
                        collection = pad.child('CustomSpokes')
                        if collection is None:
                            collection = pad.add('CustomSpokes')
                        row = collection.add('CustomSpoke')
                        row['Type'], row['Spoke'], row['Width'] = 0, spoke, pour['SpokeWidth']
                        if rows:
                            row['Layer'] = layer
                        modified = True
                    break
            if modified:
                changed.append(pad)
    if changed:
        import_notice('info', 'legacy-thermal-spokes',
                      'Modernized rotated pad thermal settings.', changed,
                      recoverability='current spoke choices and layer assignments retain the older placement meaning')
    return tuple(changed)
