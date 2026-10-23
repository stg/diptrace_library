"""Public user-field lookup keys, independent of application UI state."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _lowercase_mapping():
    data=json.loads(Path(__file__).with_name('windows_lowercase.json').read_text(encoding='utf-8'))
    return {int(key):chr(value) for key,value in data['mapping'].items()}


def label_lowercase(text):
    """Measured Windows lowercase plus the format label helper's ending rule."""
    mapping=_lowercase_mapping()
    result=''.join(mapping.get(ord(character),character) for character in text)
    raw=result.encode('utf-16-le',errors='surrogatepass')
    if len(raw)>2 and raw[-2:] in (b'\r\x00',b'\n\x00'):
        raw=raw[:-4]+raw[-2:]
    return raw.decode('utf-16-le',errors='surrogatepass')


def user_field_key(name):
    """Lookup normalization removes literal spaces before lowercasing."""
    return label_lowercase(name.replace(' ',''))


def modernize_user_field_names(schematic):
    """Give blank placed-field labels their current default during import.

    Only enabled component fields participate. Tabs and other non-space text
    remain authored names; cached library definitions are independent resources.
    """
    for part in schematic.select('Components/Part'):
        if part.scalar('Enabled', True) in (True, 'Y'):
            for field in part.select('UserFields/UserField'):
                name = field.arguments[0]
                if name.kind != 'string' or name.unit:
                    raise TypeError('user-field names must be plain text')
                if not name.value.replace(' ', ''):
                    field.set_argument(0, 'Untitled')


def global_user_field_choice(name, rows, *, enabled=True):
    """First exact key match; ASC rows contain display name, key, state, position."""
    if enabled:
        key=user_field_key(name)
        for display,stored_key,state,position in rows:
            if key == stored_key:
                return state,position
    return 2,7


def global_user_field_registry(parts, previous=()):
    """Build choices in first-use order from enabled components.

    Display names retain their spelling; lookup keys ignore spaces and case.
    An existing choice at the same position has priority, followed by the first
    matching key. New keys use hidden state 2 and standard position 7.
    """
    previous = tuple(previous)
    by_key = {}
    for row in previous:
        if len(row) != 4:
            raise ValueError('global user-field choices require four values')
        by_key.setdefault(row[1], row)
    result, seen = [], set()
    for part in parts:
        if part.scalar('Enabled') not in (True, 'Y'):
            continue
        for field in part.select('UserFields/UserField'):
            name = field.values[0]
            display = name if name.replace(' ', '') else 'Untitled'
            key = user_field_key(display)
            if key in seen:
                continue
            seen.add(key)
            index = len(result)
            choice = previous[index] if index < len(previous) and previous[index][1] == key else by_key.get(key)
            state, position = choice[2:] if choice is not None else (2, 7)
            result.append((display, key, state, position))
    return tuple(result)


def refresh_global_user_fields(schematic, *, destination, report=None):
    """Refresh a detached export view, reporting choices it no longer carries."""
    choices = schematic.one('ShowUserfield_Global')
    rows = choices.children('pt')
    projected = global_user_field_registry(schematic.select('Components/Part'), (row.values for row in rows))
    omitted = [row for row in rows if row.values not in projected]
    if omitted:
        from .conversion import info
        info(report, 'global-user-field-choices', destination,
             'user-field registry refresh replaces unused or differently spelled choices', omitted,
             recoverability='stored choices remain in the authoring model')
    for row in rows:
        row.detach()
    for values in projected:
        choices.add('pt', *values)
