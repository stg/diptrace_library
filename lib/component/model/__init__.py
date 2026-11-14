"""Editable standalone component-library ownership, under development."""
from .document import Document
from .objects import (new_library, new_component, new_part, new_pin, new_drawing,
                      new_pattern, new_pad, new_group, new_pattern_drawing, new_internal_connection)

__all__ = ['Document', 'new_library', 'new_component', 'new_part', 'new_pin',
           'new_drawing', 'new_pattern', 'new_pad', 'new_group', 'new_pattern_drawing', 'new_internal_connection']
