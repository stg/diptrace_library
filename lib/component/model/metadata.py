"""Component-owned descriptions exposed through familiar part field names."""
from ...common.schema import Field


SHARED_FIELDS = ('Name', 'RefDes', 'Manufacturer', 'Datasheet',
                 'Component_CategoryName', 'Component_CategoryIndex', 'SubfolderIndex')
FOLDER_ROLE = 'component-library-folder'


def component_of(node):
    while node is not None:
        if node.kind == 'Component':
            return node
        node = node.parent
    return None


def shared_field(name, kind, *, default='', unit=''):
    def get(part):
        component = component_of(part)
        return component.get(name, default) if component is not None else default

    def set_value(part, value):
        component = component_of(part)
        if component is None:
            raise ValueError('attach the part to a component before editing component metadata')
        component[name] = value

    return Field(name, kind, required=True, getter=get, setter=set_value, unit=unit,
        value_dependencies=lambda part: ((owner, name),) if (owner := component_of(part)) is not None else (),
        description='Shared component metadata; assigning through a part edits its component.')
