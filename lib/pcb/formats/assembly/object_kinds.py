"""Normalize placed pad/hole classifications and their marking visibility."""
from ....common.conversion import import_notice, info, warn
from ...model.markings import NAMES, SIDES


def _physical_objects(pattern, raw):
    pads = pattern.select('Pads/Pad')
    shapes = pattern.select('Shapes/Shape')
    holes = pattern.select('Holes/Hole')
    if raw:
        pads = [pad for position, pad in enumerate(pads[1:-1], 1)
                if pad['Number_New'] == position]
        shapes, holes = shapes[1:-1], holes[1:-1]
    enabled_holes = ([hole for hole in holes if hole.values[0]] if raw else
                     [hole for hole in holes if hole['Enabled']])
    return pads, [shape for shape in shapes if shape.get('Type', 0) > 0 and shape['Type'] != 7], enabled_holes


def _kind(original, pads, drawings, holes):
    count = len(pads)+len(drawings)+len(holes)
    if count == 1 and pads:
        return 20 if pads[0]['PadShape_New'] == 20 else 16 if original == 16 else 14
    if count == 1 and holes:
        return 15
    return 0 if original in (14, 15, 16) else original


def normalize_objects(board, *, raw=True, destination=None, report=None):
    """Resolve physical standalone objects without changing their identities.

    Saved boundary rows and electrical pad keys are adapter inputs. Text does
    not prevent a footprint from representing one physical pad or hole. Current
    model ordering replaces the source array compaction done during conversion.
    Typed export views use ordinary named edits so classification changes also
    release or acquire any style-owned properties through the reference graph.
    """
    changed, classified, hidden = [], [], []

    def assign(owner, name, value):
        if raw:
            owner.set_field(name, value)
        else:
            owner[name] = value

    for component in board.select('Components/Component'):
        if not component.get('Enabled', True):
            continue
        pattern = component.one('Pattern')
        original = pattern['Type']
        kind = _kind(original, *_physical_objects(pattern, raw))
        altered = kind != original
        if altered:
            assign(pattern, 'Type', kind)
            classified.append(component)
        if kind in (15, 16, 20):
            fields = [(component, label+'_'+side+'Show') for label in NAMES for side in SIDES]
            fields.extend((user, side+'Show') for user in component.select('UserFields/UserField')
                          for side in SIDES)
            for owner, name in fields:
                if owner.get(name, 0) != 2:
                    assign(owner, name, 2)
                    hidden.append(owner)
                    altered = True
        if altered:
            changed.append(component)
    if destination is None and changed:
        import_notice('info', 'standalone-object-normalization',
                      'Normalized standalone PCB objects and marking visibility.', changed)
    elif destination is not None:
        if classified:
            info(report, 'standalone-object-normalization', destination,
                 'Derived standalone object classifications from current physical geometry.', classified,
                 recoverability='physical objects and connections remain; only the detached output view changes')
        if hidden:
            warn(report, 'standalone-marking-visibility', destination,
                 'Standalone holes, vias and fiducials initialize component marking Show choices to Hide.',
                 tuple(dict.fromkeys(hidden)),
                 recoverability='marking text and relative placements remain; source Show choices are unchanged')
