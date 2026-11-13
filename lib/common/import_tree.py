"""Controlled ownership changes before a parser tree acquires model bindings.

These helpers are for adapter-owned construction. Public edits use Element's
constraint and relationship planning instead.
"""


def assign_fields(parent, fields, *, overwrite=True):
    """Assign decoded scalar facts before schema/relationship binding.

    Preserve ordinary scalar replacement and no-op behavior, including source
    metadata and retained field identities. A compact provisional layout can
    accept the values without constructing editable field handles.
    """
    from .element_storage import RecordItems
    from .model import Element, Value, _valid_element_name
    from .schema import MISSING

    if parent.schema is not None:
        raise TypeError('import assignment requires an unbound parser record')
    document = parent._owner()
    if document is not None and (document._reference_validator is not None
            or len(document.references) or document.references.issues or document.references._watched):
        raise ValueError('import assignment must precede relationship binding')
    prepared = []
    for name, supplied in fields:
        if not _valid_element_name(name):
            raise ValueError('invalid import field name: '+repr(name))
        prepared.append((name, supplied, Value.of(supplied)))
    storage = parent._content if type(parent._content) is RecordItems else None
    for name, supplied, value in prepared:
        if storage is not None and storage.can_import(name, replace=True):
            current = storage.value(name)
            if current is not MISSING:
                if not overwrite:
                    continue
                slot = storage.storage.layout.slots[name]
                definition = storage.storage.layout.definitions[slot]
                if definition.kind != 'tuple' or len(current) == 1:
                    previous = storage.argument(slot)
                    if ((previous.value, previous.kind, previous.unit) == (value.value, value.kind, value.unit)
                            and (not isinstance(supplied, Value) or previous == value)):
                        continue
            storage.import_field(name, (value,), replace=True)
        else:
            previous = parent.child(name)
            if previous is None:
                parent._append_import(Element(name, value))
            elif overwrite:
                previous.set_values(supplied)
    return parent


def move_children(source, target, children=None):
    """Transfer raw children together, retaining order, identities and arguments."""
    if source is target:
        raise ValueError('import transfer requires distinct parents')
    for parent in (source, target):
        if parent.schema is not None or type(parent._content) is not list:
            raise TypeError('import transfer requires unbound parser records')
        document = parent._owner()
        if document is not None and (document._reference_validator is not None
                or len(document.references) or document.references.issues or document.references._watched):
            raise ValueError('import transfer must precede relationship binding')
    selected = tuple(source.children() if children is None else children)
    selected_set = set(selected)
    if len(selected_set) != len(selected):
        raise ValueError('import transfer contains the same child more than once')
    if any(child.parent is not source or child.schema is not None for child in selected):
        raise ValueError('import transfer requires unbound children of the source')
    ancestor = target
    while ancestor is not None:
        if ancestor in selected_set:
            raise ValueError('import transfer cannot create an ownership cycle')
        ancestor = ancestor.parent
    if not selected:
        return target
    source._content = [item for item in source._content if item not in selected_set]
    target._content.extend(selected)
    for child in selected:
        child._parent = target
    source._touch(reordered=True)
    target._touch(reordered=True)
    return target
