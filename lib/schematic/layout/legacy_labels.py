"""Old two-slot label choices expressed as public, editable label settings."""
from dataclasses import dataclass
from ...common.legacy_labels import LegacyLabelSlot, label_anchor


@dataclass
class LabelSettings:
    state: int = 0
    name_variant: int = 0
    position: int = 0
    horizontal: int = 0
    vertical: int = 0
    x: float = 0.
    y: float = 0.
    angle: float = 0.

    @classmethod
    def from_values(cls, values, *, named=False):
        if len(values) != (8 if named else 7):
            raise ValueError('a label requires its complete public tuple')
        return cls(*values) if named else cls(values[0], 0, *values[1:])

    def values(self, *, named=False):
        return (self.state, *((self.name_variant,) if named else ()), self.position,
                self.horizontal, self.vertical, self.x, self.y, self.angle)


LABEL_NAMES = ('ShowName', 'ShowRefDes', 'ShowValue', 'ShowDatasheet', 'ShowManufacturer')
_GLOBAL_TARGETS = {1: 'ShowName', 2: 'ShowRefDes', 3: 'ShowValue',
                   4: 'ShowName', 6: 'ShowManufacturer', 7: 'ShowDatasheet'}
_EXPLICIT = {2: (1, 1), 3: (2, 0), 4: (3, 0), 5: (4, 2), 6: (6, 0), 7: (7, 0)}
_SIDE_PIN = {2: 1, 4: 0, 5: 2, 3: 3}
_OPPOSITE = {1: 3, 2: 3, 3: 2, 4: 5, 5: 4, 6: 3}


def label_side(preferred, pin_orientations):
    """Prefer a free edge, then top/left/right/bottom, then a corner."""
    occupied = {value if 0 <= value < 4 else 0 for value in pin_orientations}
    if _SIDE_PIN.get(preferred) not in occupied:
        return preferred
    return next((side for side, pin in _SIDE_PIN.items() if pin not in occupied), 6)


def _anchor(settings, alignment, slot, dimensions):
    if (anchor := label_anchor(alignment, (slot.x_shift, slot.y_shift), dimensions)) is not None:
        settings.x, settings.y, settings.horizontal, settings.vertical, settings.angle = anchor


def resolve_legacy_labels(*, version, first=LegacyLabelSlot(), second=LegacyLabelSlot(),
                          global_first=(2, 7), global_second=(0, 0), dimensions=(10., 6.),
                          user_field_count=0, pin_orientations=(), measure_width,
                          outside_text=False):
    """Return label tuples and the first resolved edge choice.

    ``measure_width(name)`` receives a public label name or ``UserFieldN``. It
    measures the current displayed text in the caller's chosen font environment.
    The caller can discard the old slot inputs after applying these results.
    """
    labels = {name: LabelSettings() for name in LABEL_NAMES}
    labels.update((f'UserField{i}', LabelSettings()) for i in range(user_field_count))

    def target(mode, user):
        name = f'UserField{user}' if mode == 5 else _GLOBAL_TARGETS.get(mode)
        return name if name in labels else None

    slots = []
    for slot, (global_mode, global_alignment) in zip((first, second), (global_first, global_second)):
        mode = slot.mode+2 if version < 33 and slot.mode > 5 else slot.mode
        category, user, variant = global_mode, slot.user_field, 0
        if mode > 0:
            inherited = target(global_mode, user)
            if inherited and labels[inherited].state == 0:
                labels[inherited].state = 2
            if mode >= 8:
                category, user = 5, mode-8
            else:
                category, variant = _EXPLICIT.get(mode, (0, 0))
            selected = target(category, user)
            if selected:
                labels[selected].state = 1
                if selected == 'ShowName':
                    labels[selected].name_variant = variant
        name = target(category, user)
        alignment = global_alignment
        if name and slot.alignment > 0:
            alignment = slot.alignment
        slots.append(dict(source=slot, category=category, name=name, alignment=alignment))

    def automatic(name):
        width, height = dimensions
        preferred = 4 if height > width and measure_width(name) > width else 2
        return label_side(preferred, pin_orientations)

    first_slot, second_slot = slots
    for index, item in enumerate(slots):
        name, slot = item['name'], item['source']
        if name and slot.alignment > 0:
            labels[name].position = item['alignment']
        if name and (abs(slot.x_shift) > .01 or abs(slot.y_shift) > .01 or outside_text):
            labels[name].position = 8
            if item['alignment'] == 7:
                item['alignment'] = automatic(name) if index == 0 else _OPPOSITE.get(first_alignment, 7)
            _anchor(labels[name], item['alignment'], slot, dimensions)
        if index == 0:
            first_alignment = item['alignment']
            if first_alignment == 7:
                first_alignment = automatic(name) if name else 2

    priorities = [{1: 2, 2: 1}.get(item['category'], item['category']) for item in slots]
    if (first_slot['alignment'] == 7 and second_slot['alignment'] != 7 or
            any(item['name'] and labels[item['name']].position == 8 for item in slots)):
        priorities[1] = -1
    if priorities[0] > priorities[1]:
        if first_slot['alignment'] == 7 and first_slot['name']:
            name = first_slot['name']
            first_slot['alignment'] = labels[name].position = automatic(name)
        if second_slot['alignment'] == 7 and second_slot['name']:
            opposite = _OPPOSITE.get(first_slot['alignment']) if first_slot['alignment'] != 1 else None
            if opposite is not None:
                labels[second_slot['name']].position = opposite
    result = {name: value.values(named=name in ('ShowName', 'ShowRefDes')) for name, value in labels.items()}
    result['FirstAlignment'] = first_alignment
    return result
