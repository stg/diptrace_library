"""PCB component RefDes occupancy uses the shared numbered-family rules."""
from ...common.refdes import split_refdes


def components(document):
    return (component for component in document.one('/Board/Components')._child_sequence('Component')
            if component['Enabled'])


def validate_name(document, component, *, previous=None, parent=None):
    parent = component.parent if parent is None else parent
    if parent is not document.one('/Board/Components') or not component['Enabled']:
        return
    name = component['RefDes']
    if not name or name == previous:
        return
    key = split_refdes(name)
    for other in components(document):
        if other is component or not other['RefDes']:
            continue
        if split_refdes(other['RefDes']) == key:
            raise ValueError(f"RefDes {name!r} is already occupied by {other['RefDes']!r}")


def validate_edit(document, component, name):
    """Check new occupancy without treating an unchanged name as a rename."""
    previous = None
    if name == 'RefDes' and (field := component.child(name)) is not None:
        values = field._stored_arguments()
        previous = values[0].value if values else ''
    validate_name(document, component, previous=previous)
