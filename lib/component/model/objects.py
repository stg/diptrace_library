"""Small standalone-library constructors without template or routing algorithms."""
from ...common.model import Element
from ...common.symbol_objects import symbol_data
from ...common import symbol_objects
from ...common.symbol_text_style import normalize_text_style
from ...common.unplaced_footprint_objects import (new_pattern, new_pad, new_group,
    new_drawing as new_pattern_drawing, new_internal_connection)
from .document import Document
from .metadata import SHARED_FIELDS
from . import records
from . import symbols
from .schema import establish_records


def new_library(name='Library', *, hint='Untitled Library'):
    root = Element('')
    library = root.add('Library')
    library.add('Name', name)
    library.add('Hint', hint)
    for name in ('Categories', 'Subfolders', 'Components'):
        library.add(name)
    establish_records(root)
    return Document(root)


def new_part(name='Part 1'):
    part = symbol_data()
    part.set_values()
    for name_to_remove in (*SHARED_FIELDS, 'Component_CategoryTypes', 'UserFields', 'Suppliers', 'ModelNote'):
        if (field := part.child(name_to_remove)) is not None:
            field.detach()
    part.one('PartName').set_values(name)
    part.add('Verification', *(False,)*7)
    part.add('Groups')
    part.bind_schema(records.PART)
    establish_records(part)
    return part


def new_component(name='', reference='', *, part_name='Part 1'):
    component = Element('Component')
    for key, value in dict(Name=name, RefDes=reference, Manufacturer='', Datasheet='',
            Component_CategoryName='', Component_CategoryIndex=-1).items():
        component.add(key, value)
    component.add('Parts').append(new_part(part_name))
    for key in ('Component_CategoryTypes', 'UserFields'):
        component.add(key)
    suppliers = component.add('Suppliers')
    for key in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'SourceLocator', 'Currency'):
        suppliers.add(key, '')
    component.bind_schema(records.COMPONENT)
    establish_records(component)
    return component


def new_pin():
    pin = symbol_objects.new_pin()
    for name in ('Number', 'Group'):
        pin.one(name).detach()
    pin.bind_schema(symbols.PIN)
    return pin


def new_drawing(*, kind=1):
    drawing = symbol_objects.new_drawing()
    for name in ('ShowPart', 'MarkingGenerated', 'Group'):
        drawing.one(name).detach()
    drawing['Type'] = kind
    drawing.bind_schema(symbols.DRAWING)
    normalize_text_style(drawing)
    establish_records(drawing)
    return drawing
