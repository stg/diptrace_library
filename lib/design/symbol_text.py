"""Resolve component-bound symbol text without changing drawing appearance."""
from .references import ReferenceError


def modernize_named_marking_choices(schematic):
    """Resolve global Common suffix choices to RefDes Show and Name Hide.

    Component-level Common still inherits the corresponding global choice.
    Unknown enum values remain current typed data rather than guessed choices.
    """
    for name, default in (('ShowRefDes_Global', 1), ('ShowName_Global', 2)):
        choice = schematic.one(name)
        if choice.values[1] == 0:
            choice.set_argument(1, default)


def refresh_symbol_text(document):
    """Update active TextShow drawings from current component properties.

    FontType zero is literal text. Known positive kinds select one component
    property or user field; their displayed text is calculated, even when the
    drawing has an authored position and appearance. Keep the first text-row
    identity and preflight removal of any redundant rows before changing data.
    """
    schematic = document.one('/Schematic')
    plans = []
    for part in schematic.select('Components/Part'):
        if part.scalar('Enabled', True) in (False, 'N'):
            continue
        values = {1:part.values[0], 2:part.values[1]}
        values.update((kind, part.scalar(name, '')) for kind, name in
                      ((3, 'Value'), (4, 'PartName'), (5, 'Manufacturer'), (6, 'Datasheet')))
        values.update((20+index, field.values[1]) for index, field in
                      enumerate(part.select('UserFields/UserField')))
        for shape in part.select('Shapes/Shape'):
            kind = shape.scalar('FontType')
            if (shape.scalar('Enabled', True) in (False, 'N') or shape.scalar('Type') != 10
                    or isinstance(kind, bool) or kind not in values):
                continue
            text = values[kind]
            show_part = None
            if kind in (1, 2):
                if shape.scalar('MarkingGenerated') in (True, 'Y'):
                    include_suffix = shape.scalar('ShowPart') in (True, 'Y')
                else:
                    name = 'ShowName' if kind == 1 else 'ShowRefDes'
                    global_variant = schematic.one(name+'_Global').values[1] or (1 if kind == 2 else 2)
                    variant = part.one(name).values[1] or global_variant
                    show_part = include_suffix = variant == 1
                suffix = part.scalar('PartName' if kind == 1 else 'PartDescriptor', '')
                if include_suffix and part.scalar('AllowParts') in (True, 'Y') and suffix.replace(' ', ''):
                    text += f' ({suffix})' if kind == 1 else '.'+suffix
            lines = shape.child('TextLine')
            rows = lines.children('pt') if lines is not None else []
            if [row.values for row in rows] != [(text,)] or (show_part is not None and shape.scalar('ShowPart') != show_part):
                plans.append((shape, lines, rows, text, show_part))
    structural = [(shape, lines, rows) for shape, lines, rows, _, _ in plans if len(rows) != 1]
    graph = document.references
    graph._check_collection_changes(lines if lines is not None else shape for shape, lines, _ in structural)
    removed = {row for _, _, rows in structural for row in rows[1:]}
    if any(graph.incoming(row) for row in removed):
        raise ReferenceError('symbol text refresh would remove a referenced text row')
    modernize_named_marking_choices(schematic)
    for shape, lines, rows, text, show_part in plans:
        if lines is None:
            lines = shape.add('TextLine')
        if rows:
            rows[0].set_values(text)
            for row in rows[1:]:
                row.detach()
        else:
            lines.add('pt', text)
        if show_part is not None:
            shape.set_field('ShowPart', show_part)
    if plans:
        from .conversion import import_notice
        import_notice('info', 'bound-symbol-text', 'Refreshed text bound to current component fields',
                      (shape for shape, *_ in plans), recoverability='text is calculated from current fields')
    return tuple(shape for shape, _, _, _, _ in plans)
