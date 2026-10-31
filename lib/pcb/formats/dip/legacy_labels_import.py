"""Modernize older marking choices using current text and measured geometry."""
import math
from functools import lru_cache

from ....common.conversion import import_notice
from ....common.legacy_labels import LegacyLabelSlot
from ....common.text.markings import MarkingStyle, marking_width
from ...model.markings import NAMES, SIDES
from .binary import DipError
from .legacy_markings import global_alignment, resolve_markings


_PROPERTIES = ('Show', 'Align', 'Horz', 'Vert', 'X', 'Y', 'Angle')
_CATEGORIES = {1: 'Name', 2: 'RefDes', 3: 'Value', 5: 'Pattern',
               6: 'Manufacturer', 7: 'Datasheet'}


def _globals(board, choices):
    placements = {name: [2, 7] for name in NAMES}
    fields = board.add('Userfields_Global')
    for slot, (category, alignment) in enumerate(choices, 1):
        if category == 4:
            field = fields.add('UserField')
            field.add('Name', board.get('UserField'+str(slot), ''))
            for name, value in dict(SilkShow=1, SilkAlign=alignment,
                                    AssyShow=0, AssyAlign=0).items():
                field.add(name, value)
        elif category and category not in _CATEGORIES:
            raise DipError(f'unknown legacy global marking choice {category}')
        if (name := _CATEGORIES.get(category)) is not None:
            placements[name] = [1, alignment]
    for name, (show, alignment) in placements.items():
        for side in SIDES:
            board.set_field(name+'_Global_'+side+'Show', show if side == 'Silk' else 2)
            board.set_field(name+'_Global_'+side+'Align', alignment if side == 'Silk' else 7)


def _write(owner, prefix, values):
    for property_name, value in zip(_PROPERTIES, values):
        owner.set_field(prefix+property_name, value)


def modernize_markings(decoded, *, layout):
    """Run after physical drawing expansion, before rebasing the local frame.

    Older dimensions describe the quarter-turned selection rectangle. Current
    local geometry has already undone that quarter turn; the two frames are
    related without retaining a second set of model dimensions.
    """
    if decoded.header.version >= 47:
        return
    board = decoded.board
    raw = decoded.upgrades.initial.legacy_markings
    choices = ((raw[0], global_alignment(raw[1])), (raw[2], global_alignment(raw[3])))
    _globals(board, choices)
    if not decoded.upgrades.components:
        return
    # Older automatic edge selection used the stored system font even when the
    # drawing itself used vector text. This is a measurement policy, not a change
    # to the current board's authored font selection.
    style = MarkingStyle(font_size=board['CompFontSize'], font_name=board['CompFontName'],
                        vector=False)
    changed = []
    for item in decoded.upgrades.components:
        component = item.component
        pattern = component.one('Pattern')
        quarter = round(float(component['Angle'])/(math.pi/2))
        dimensions = tuple(float(pattern[name]) for name in ('Width', 'Height'))
        selection = dimensions[::-1] if quarter % 2 else dimensions
        angle = float(component['Angle'])+math.radians(float(item.legacy_field_bindings[2]))
        outside = False
        for drawing in item.drawings:
            shape = drawing.shape
            if shape['Type'] != 7 or drawing.text_marker:
                continue
            lo, hi = layout.pattern_bounds(shape)
            outside |= any(lo[i] < -dimensions[i]/2.1 or hi[i] > dimensions[i]/2.1
                           for i in (0, 1))
        users = component.select('UserFields/UserField')

        @lru_cache(maxsize=None)
        def measure(name):
            text = (users[name].values[1] if isinstance(name, int) else
                    pattern.values[0] if name == 'Pattern' else component.get(name, ''))
            return marking_width(text, style, text_layout=layout, point_size_divisor=1)

        modes, shifts = item.legacy_markings, item.legacy_text_positions
        slots = [LegacyLabelSlot(modes[i*2], modes[i*2+1], item.legacy_field_bindings[i],
                                 shifts[i*2], shifts[i*2+1]) for i in (0, 1)]
        labels, user_placements = resolve_markings(version=decoded.header.version,
            first=slots[0], second=slots[1], global_first=choices[0], global_second=choices[1],
            dimensions=selection, user_field_count=len(users), measure_width=measure,
            outside_text=outside, angle=angle, bottom_side=component['BottomSide'])
        for name, values in labels.items():
            _write(component, name+'_Silk', values)
            _write(component, name+'_Assy', (0,)*7)
        for user, values in zip(users, user_placements):
            _write(user, 'Silk', values)
            _write(user, 'Assy', (0,)*7)
        changed.append(component)
    if changed:
        import_notice('info', 'legacy-marking-settings',
                      'Modernized older component marking settings.', changed)
