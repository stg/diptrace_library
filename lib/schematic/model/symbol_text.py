"""Resolve component-bound symbol text without changing drawing appearance."""
from ...common.text_lines import check_refresh, replace_line


def dependent_shapes(document, slot, *, include_outputs=False):
    """Bound labels affected by one named value, including copied properties."""
    from ...common.field_edits import named_field
    found = named_field(*slot)
    if found is None:
        return ()
    record, name = found
    if include_outputs:
        shape = (record.parent.parent if record.parent is not None and record.parent.kind == 'TextLine'
                 else record if record.kind == 'Shape' and name == 'ShowPart' else None)
        if shape is not None and is_bound_label(shape):
            return (shape,)
    if record.parent is not None and record.kind in ('ShowName', 'ShowRefDes',
                                                     'ShowName_Global', 'ShowRefDes_Global'):
        record, name = record.parent, record.kind
    kinds = {'Name': (1,), 'RefDes': (2,), 'Value': (3,), 'PartName': (1, 4),
             'PartDescriptor': (2,), 'Manufacturer': (5,), 'Datasheet': (6,),
             'AllowParts': (1, 2), 'ShowName': (1,), 'ShowRefDes': (2,)}
    if record.kind == 'Schematic' and name in ('ShowName_Global', 'ShowRefDes_Global'):
        selected = (1,) if name == 'ShowName_Global' else (2,)
        parts = record.select('Components/Part')
    elif record.kind == 'Part' and record.parent is not None and record.parent.kind == 'Components':
        selected = None if name == 'Enabled' else kinds.get(name, ())
        parts = (record,)
    elif record.kind == 'UserField' and name == 'Value' and record.parent is not None:
        part = record.parent.parent
        if part is None or part.parent is None or part.parent.kind != 'Components':
            return ()
        selected, parts = (20+record._ordinal(),), (part,)
    elif record.kind == 'Shape' and name in ('Type', 'FontType', 'Enabled', 'MarkingGenerated'):
        part = record.parent.parent if record.parent is not None else None
        if part is None or part.parent is None or part.parent.kind != 'Components':
            return ()
        return (record,)
    else:
        return ()
    return tuple(shape for part in parts for shape in part.select('Shapes/Shape')
                 if selected is None or shape.scalar('FontType') in selected)


def calculation_outputs(shapes):
    for shape in shapes:
        kind = shape.scalar('FontType')
        if shape.scalar('Type') != 10 or kind not in (*range(1, 7), *range(20, 20+len(
                shape.parent.parent.select('UserFields/UserField')))):
            continue
        rows = shape.select('TextLine/pt')
        if rows:
            yield rows[0]._argument_owner(0)
        if kind in (1, 2) and shape.child('ShowPart') is not None:
            yield shape.one('ShowPart')._argument_owner(0)


def is_bound_label(shape):
    part = shape.parent.parent if shape.parent is not None else None
    if part is None or part.parent is None or part.parent.kind != 'Components':
        return False
    kind = shape.scalar('FontType')
    return (shape.kind == 'Shape' and shape.scalar('Type') == 10 and not isinstance(kind, bool) and
            kind in (*range(1, 7), *range(20, 20+len(part.select('UserFields/UserField')))))


def modernize_named_marking_choices(schematic):
    """Resolve global Common suffix choices to RefDes Show and Name Hide.

    Component-level Common still inherits the corresponding global choice.
    Unknown enum values remain current typed data rather than guessed choices.
    """
    for name, default in (('ShowRefDes_Global', 1), ('ShowName_Global', 2)):
        choice = schematic.one(name)
        if choice.values[1] == 0:
            choice.set_argument(1, default)


def plan_symbol_text(document, *, parts=None, overrides=None, shapes=None):
    """Preflight affected TextShow rows, optionally against proposed field edits.

    FontType zero is literal text. Known positive kinds select one component
    property or user field; their displayed text is calculated, even when the
    drawing has an authored position and appearance. Keep the first text-row
    identity and preflight removal of any redundant rows before changing data.
    """
    schematic = document.one('/Schematic')
    overrides = overrides or {}

    def field_values(record, name, default=()):
        if (record, name) in overrides:
            return tuple(value.value for value in overrides[record, name]) or default
        field = record.child(name)
        return field.values if field is not None else default

    def scalar(record, name, default=''):
        return field_values(record, name, (default,))[0]

    plans = []
    selected_shapes = frozenset(shapes) if shapes is not None else None
    for part in parts if parts is not None else schematic.select('Components/Part'):
        if part.scalar('Enabled', True) in (False, 'N'):
            continue
        values = {1:scalar(part, 'Name', part.values[0]), 2:scalar(part, 'RefDes', part.values[1])}
        values.update((kind, scalar(part, name)) for kind, name in
                      ((3, 'Value'), (4, 'PartName'), (5, 'Manufacturer'), (6, 'Datasheet')))
        values.update((20+index, scalar(field, 'Value', field.values[1])) for index, field in
                      enumerate(part.select('UserFields/UserField')))
        for shape in part.select('Shapes/Shape'):
            if selected_shapes is not None and shape not in selected_shapes:
                continue
            kind = shape.scalar('FontType')
            if (shape.scalar('Enabled', True) in (False, 'N') or shape.scalar('Type') != 10
                    or isinstance(kind, bool) or kind not in values):
                continue
            text = values[kind]
            show_part = None
            if kind in (1, 2):
                name = 'ShowName' if kind == 1 else 'ShowRefDes'
                global_variant = field_values(schematic, name+'_Global')[1] or (1 if kind == 2 else 2)
                variant = field_values(part, name)[1] or global_variant
                show_part = include_suffix = variant == 1
                suffix = scalar(part, 'PartName' if kind == 1 else 'PartDescriptor')
                has_suffix = include_suffix and scalar(part, 'AllowParts', False) in (True, 'Y') and bool(suffix.replace(' ', ''))
                if shape.scalar('MarkingGenerated') in (True, 'Y'):
                    show_part = has_suffix
                if has_suffix:
                    text += f' ({suffix})' if kind == 1 else '.'+suffix
            lines = shape.child('TextLine')
            rows = lines.children('pt') if lines is not None else []
            if [row.values for row in rows] != [(text,)] or (show_part is not None and shape.scalar('ShowPart') != show_part):
                plans.append((shape, lines, rows, text, show_part))
    check_refresh(document, ((shape, lines, rows) for shape, lines, rows, _, _ in plans))
    return plans


def apply_symbol_text(plans):
    """Apply a preflighted local plan without touching drawing appearance."""
    for shape, lines, rows, text, show_part in plans:
        replace_line(shape, lines, rows, text)
        if show_part is not None:
            shape.set_field('ShowPart', show_part)
    if plans:
        from ...common.conversion import (import_notice)
        import_notice('info', 'bound-symbol-text', 'Refreshed text bound to current component fields',
                      (shape for shape, *_ in plans), recoverability='text is calculated from current fields')
    return tuple(shape for shape, _, _, _, _ in plans)


def refresh_symbol_text(document):
    """Refresh current component-bound text during import or detached export."""
    plans = plan_symbol_text(document)
    modernize_named_marking_choices(document.one('/Schematic'))
    return apply_symbol_text(plans)
