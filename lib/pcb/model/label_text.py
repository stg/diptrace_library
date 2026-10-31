"""PCB field-bound text and identity-stable user-field selections.

Text refresh changes content only. Font, position and other drawing properties
remain independent; generating or positioning missing markings is separate.
"""
from ...common.field_edits import named_field, ReferenceValueEdit, ValueEdit
from ...common.model import Value
from ...common.references import Guard, Index, ReferenceError, UnresolvedReference
from ...common.text_lines import check_refresh, replace_line
from .markings import TEXT_FIELDS, PATTERN_TEXT_FIELDS, USER_FIELD_OFFSET


USER_ROLE = 'marking-user-field'


def component_of(shape):
    shapes = shape.parent
    pattern = shapes.parent if shapes is not None else None
    component = pattern.parent if pattern is not None else None
    if (shape.kind == 'Shape' and shapes is not None and shapes.kind == 'Shapes'
            and pattern is not None and pattern.kind == 'Pattern'
            and component is not None and component.kind == 'Component'
            and component.parent is not None and component.parent.kind == 'Components'):
        return component
    return None


def _selection(shape):
    component = component_of(shape)
    if component is None or shape.get('Type') != 7:
        return None
    mode = int(shape.get('TextShow', 0))
    if mode in PATTERN_TEXT_FIELDS:
        return component.one('Pattern').get(PATTERN_TEXT_FIELDS[mode], '')
    if mode in TEXT_FIELDS:
        return component.get(TEXT_FIELDS[mode], '')
    if mode >= USER_FIELD_OFFSET:
        users = component.select('UserFields/UserField')
        index = mode-USER_FIELD_OFFSET
        if index < len(users):
            return users[index]['Value']
    return None


def is_bound_label(shape):
    return _selection(shape) is not None


def dependent_shapes(document, slot, *, include_outputs=False):
    found = named_field(*slot)
    if found is None:
        return ()
    record, name = found
    if include_outputs and record.parent is not None and record.parent.kind == 'TextLine':
        shape = record.parent.parent
        return (shape,) if is_bound_label(shape) else ()
    if record.kind == 'Shape' and name in ('Type', 'TextShow'):
        return (record,) if component_of(record) is not None else ()
    if record.kind == 'Component':
        component = record
        selected = None if name == 'Enabled' else tuple(mode for mode, field in TEXT_FIELDS.items()
                                                       if field == name)
    elif record.kind == 'Pattern' and record.parent is not None:
        component = record.parent
        selected = tuple(mode for mode, field in PATTERN_TEXT_FIELDS.items() if field == name)
    elif record.kind == 'UserField' and name == 'Value' and record.parent is not None:
        component, selected = record.parent.parent, (USER_FIELD_OFFSET+record._ordinal(),)
    else:
        return ()
    if component is None or component.kind != 'Component' or selected == ():
        return ()
    return tuple(shape for shape in component.select('Pattern/Shapes/Shape')
                 if selected is None or shape.get('TextShow', 0) in selected)


def calculation_outputs(shapes):
    for shape in shapes:
        if is_bound_label(shape) and (lines := shape.child('TextLine')) is not None:
            if rows := lines.children('pt'):
                yield rows[0]._argument_owner(0)


def plan_text(document, shapes):
    plans = []
    for shape in dict.fromkeys(shapes):
        component = component_of(shape)
        if component is None or not component['Enabled']:
            continue
        text = _selection(shape)
        if text is None:
            continue  # Literal and unresolved selections keep their current text.
        lines = shape.child('TextLine')
        rows = lines.children('pt') if lines is not None else []
        if [row.values for row in rows] != [(text,)]:
            plans.append((shape, lines, rows, text))
    check_refresh(document, ((shape, lines, rows) for shape, lines, rows, _ in plans))
    return plans


def plan_values(plans):
    for _, _, rows, text in plans:
        if rows:
            yield rows[0], (Value.of(text),)


def apply_text(plans):
    for shape, lines, rows, text in plans:
        replace_line(shape, lines, rows, text)


def contained_shapes(root):
    if root.kind == 'Component':
        return root.select('Pattern/Shapes/Shape')
    return (root,) if component_of(root) is not None else ()


def refresh_new_text(document, root):
    """Normalize new/copied local content before exposing it to callers."""
    from ...common.structural_edits import assembly
    from .definitions import establish_records
    with assembly(document):
        establish_records(root)
        plans = plan_text(document, contained_shapes(root))
        apply_text(plans)
        for shape, *_ in plans:
            establish_records(shape)


def prepare_attachment(document, root, structure):
    """Bind only the newly attached component/drawing's local text selections."""
    shapes = contained_shapes(root)
    if not shapes:
        return ValueEdit(document, structure, None)
    specifications, issues = [], []
    for shape in shapes:
        if (specification := _user_specification(shape)) is not None:
            if specification[1] is None:
                issues.append(_issue(specification))
            else:
                specifications.append(specification)
    graph = document.references
    additions = graph._prepare_additions(specifications, structure=structure)
    for source, message, indices, collections, guards in issues:
        graph._validate_reference_guards(UnresolvedReference(source, message, indices, collections, guards), {})
    return ReferenceValueEdit(document, additions, None, tuple(issues))


def _user_specification(shape):
    component = component_of(shape)
    if component is None or shape.get('Type') != 7 or shape.get('TextShow', 0) < USER_FIELD_OFFSET:
        return None
    users = component.select('UserFields/UserField')
    index = int(shape['TextShow'])-USER_FIELD_OFFSET
    return (shape, users[index] if index < len(users) else None, USER_ROLE,
            (Index(shape.one('TextShow'), offset=USER_FIELD_OFFSET),),
            (Guard(shape.one('Type'), (7,)),))


def validate_reference(document, reference, target):
    if reference.role != USER_ROLE:
        return
    component = component_of(reference.source)
    if (component is None or reference.source['Type'] != 7 or target.kind != 'UserField'
            or target.parent is not component.child('UserFields')):
        raise ReferenceError('marking requires a user field in its own component')
    if any(link.uid != reference.uid for link in document.references.outgoing(reference.source, role=USER_ROLE)):
        raise ReferenceError('marking already selects a user field')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def _issue(specification):
    source, _, role, indices, guards = specification
    component = component_of(source)
    collection = component.child('UserFields')
    return (source, role+': target index cannot be resolved', indices,
            (collection if collection is not None else component,), guards)


def bind_user_fields(document, shapes):
    graph = document.references
    for shape in shapes:
        if (specification := _user_specification(shape)) is None:
            continue
        source, target, role, indices, guards = specification
        if target is None:
            source, message, indices, collections, guards = _issue(specification)
            graph.note(source, message, *indices, collections=collections, guards=guards)
        else:
            graph.bind(source, target, *indices, role=role, guards=guards, preserve=True)


def edit_specifications(document, named):
    """Describe newly meaningful user-field selections in prospective values."""
    graph = document.references
    shapes = tuple({owner for owner, field_name in named
                    if owner.kind == 'Shape' and field_name in ('Type', 'TextShow')})
    specifications, issues = [], []
    for shape in shapes:
        specification = _user_specification(shape)
        if specification is None:
            continue
        indices = specification[3]
        if any(graph.unresolved_slot(item.field, item.argument) for item in indices):
            continue
        if specification[1] is None:
            issues.append(_issue(specification))
        else:
            specifications.append(specification)
    return specifications, issues
