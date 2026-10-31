"""Fallback marking settings and current custom-field categories."""
from ..model.markings import GLOBAL_USER_FIELD, GLOBAL_USER_FIELDS, NAMES, SIDES, field_key


def default_markings():
    """Library fallbacks: show the silk RefDes; hide other inherited labels.

    Automatic alignment avoids inventing authored coordinates. These values
    apply only to absent settings, independently of application preferences.
    """
    return {name+'_Global_'+side+field: value
            for name in NAMES for side in SIDES
            for field, value in (('Show', 1 if (name, side) == ('RefDes', 'Silk') else 2),
                                 ('Align', 7))}


def complete_user_markings(board):
    """Return renamed fields and newly added hidden global marking rules.

    Existing ordered rules retain their independent settings, including unused
    categories. A component field's text and its own placement are unaffected.
    Callers use this on an importing document or a detached export view.
    """
    rules = board.child('Userfields_Global')
    known = {row['Value'] for row in rules.children('UserField')} if rules is not None else set()
    renamed, added = [], []
    for component in board.select('Components/Component'):
        if not component.get('Enabled', True):
            continue
        for field in component.select('UserFields/UserField'):
            name = field['Name']
            if not field_key(name):
                field['Name'] = name = 'Untitled'
                renamed.append(field)
            key = field_key(name)
            if key in known:
                continue
            if rules is None:
                rules = board.add('Userfields_Global').bind_schema(GLOBAL_USER_FIELDS)
            row = rules.add('UserField').bind_schema(GLOBAL_USER_FIELD)
            row['Name'] = name
            for side in ('Silk', 'Assy'):
                row[side+'Show'], row[side+'Align'] = 2, 7
            added.append(row)
            known.add(key)
    return renamed, added
