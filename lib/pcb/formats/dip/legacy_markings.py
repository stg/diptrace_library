"""Resolve older PCB label slots into current public marking properties.

This pure conversion accepts measured layout inputs. Reading a file, measuring
existing text and synthesizing generated drawings are separate adapter stages.
"""
from dataclasses import dataclass

from ....common.geometry import transform_point
from ....common.legacy_labels import LegacyLabelSlot, label_anchor
from ...model.markings import NAMES


_CATEGORIES = {1: 'Name', 2: 'RefDes', 3: 'Value', 4: 'Pattern',
               6: 'Manufacturer', 7: 'Datasheet'}
_OPPOSITE = {1: 3, 2: 3, 3: 2, 4: 5, 5: 4, 6: 3}


@dataclass
class Placement:
    show: int = 0
    align: int = 0
    horizontal: int = 0
    vertical: int = 0
    x: float = 0.
    y: float = 0.
    angle: float = 0.

    def values(self):
        return (self.show, self.align, self.horizontal, self.vertical,
                self.x, self.y, self.angle)


def global_alignment(value):
    """The old global edge choices 0..6 become current positions 1..7."""
    return value+1 if 0 <= value <= 6 else value


def resolve_markings(*, version, first=LegacyLabelSlot(), second=LegacyLabelSlot(),
                     global_first=(2, 7), global_second=(0, 7), dimensions=(0., 0.),
                     user_field_count=0, measure_width, outside_text=False,
                     angle=0., bottom_side=False):
    """Return named Silk placements and user placements in current local axes.

    Global alignments have already been upgraded to current edge choices.
    ``dimensions`` describe the older axis-aligned footprint rectangle;
    ``angle`` is its combined placement rotation in radians. ``measure_width``
    accepts a label name or user-field index and returns a physical width.
    Assembly-side placements remain their independent declared defaults.
    """
    dimensions = tuple(map(float, dimensions))
    angle = float(angle)
    labels = {name: Placement() for name in NAMES}
    users = [Placement() for _ in range(user_field_count)]

    def target(category, user):
        if category == 5:
            return users[user] if 0 <= user < len(users) else None
        return labels.get(_CATEGORIES.get(category))

    def automatic(category, user):
        name = user if category == 5 else _CATEGORIES.get(category)
        width, height = dimensions
        return 4 if name is not None and height > width and measure_width(name) > width else 2

    slots = []
    for slot, (category, alignment) in zip((first, second), (global_first, global_second)):
        mode = slot.mode+2 if 0 < version < 39 and slot.mode > 5 else slot.mode
        user = slot.user_field
        if mode > 0:
            inherited = target(category, user)
            if inherited is not None and inherited.show == 0:
                inherited.show = 2
            if mode >= 8:
                category, user = 5, mode-8
            else:
                category = mode-1 if mode < 6 else mode
            if (selected := target(category, user)) is not None:
                selected.show = 1
        selected = target(category, user)
        if selected is not None and slot.alignment > 0:
            alignment = slot.alignment
        slots.append(dict(source=slot, category=category, user=user,
                          target=selected, alignment=alignment))

    first_alignment = slots[0]['alignment']
    for index, item in enumerate(slots):
        slot, selected, alignment = item['source'], item['target'], item['alignment']
        if selected is not None and slot.alignment > 0:
            selected.align = alignment
        if selected is not None and (abs(slot.x_shift) > .01 or abs(slot.y_shift) > .01
                                    or abs(angle) > .001 or outside_text
                                    or bottom_side and alignment == 6):
            selected.align = 8
            if alignment == 7:
                alignment = (automatic(item['category'], item['user']) if index == 0
                             else _OPPOSITE.get(first_alignment, alignment))
            if (anchor := label_anchor(alignment, (slot.x_shift, slot.y_shift), dimensions)) is not None:
                x, y, selected.horizontal, selected.vertical, selected.angle = anchor
                # Current local coordinates undo the placement's text angle.
                selected.x, selected.y = transform_point((x, y), angle=-angle)
                selected.angle -= angle
        item['alignment'] = alignment
        if index == 0:
            first_alignment = (automatic(item['category'], item['user'])
                               if alignment == 7 and selected is not None else
                               2 if alignment == 7 else alignment)

    priority = [{1: 2, 2: 1}.get(item['category'], item['category']) for item in slots]
    if (slots[0]['alignment'] == 7 and slots[1]['alignment'] != 7 or
            any(item['target'] is not None and item['target'].align == 8 for item in slots)):
        priority[1] = -1
    if priority[0] > priority[1]:
        if slots[0]['alignment'] == 7 and slots[0]['target'] is not None:
            slots[0]['alignment'] = slots[0]['target'].align = automatic(slots[0]['category'], slots[0]['user'])
        if slots[1]['alignment'] == 7 and slots[1]['target'] is not None:
            if (opposite := _OPPOSITE.get(slots[0]['alignment'])) is not None and slots[0]['alignment'] != 1:
                slots[1]['target'].align = opposite
    if bottom_side:
        for item in slots:
            if item['target'] is not None and item['target'].align != 8:
                item['target'].align = {4: 5, 5: 4}.get(item['alignment'], item['target'].align)
    return ({name: value.values() for name, value in labels.items()},
            tuple(value.values() for value in users))
