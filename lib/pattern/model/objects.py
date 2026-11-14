"""Small data constructors; no template regeneration or geometric editing."""
from ...common.model import Element
from ...common import unplaced_footprint_objects as physical
from ...common.unplaced_footprint_objects import new_pad, new_drawing, new_group, new_internal_connection
from .document import Document
from . import records
from .schema import establish_records


def new_library(name='Library', *, hint='Untitled Library'):
    root = Element('')
    library = root.add('Library')
    library.add('Name', name)
    library.add('Hint', hint)
    library.add('Categories')
    library.add('Patterns')
    establish_records(root)
    return Document(root)


def new_pattern(name=''):
    result = physical.new_pattern(name)
    result.add('Verification', False, False, False, False)
    result.bind_schema(records.PATTERN)
    establish_records(result)
    return result
