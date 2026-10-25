"""Named field layouts and shared content traversal for the DCH adapter.

Layouts describe only the wire order and public document fields. Traversals
combine equivalent content from placed instances and cached definitions.
"""
from ....common.symbol_codec import PIN_FONT

COMPONENT_PLACEMENT = (
    ("Enabled", "boolean"), ("Selected", "boolean"),
    ("Type", "integer"), ("Number1", "integer"), ("Number2", "integer"),
    ("Page", "integer"), ("Orientation", "integer"), ("Group", "integer"), ("Number", "integer"),
    ("X", "number"), ("Y", "number"), ("Width", "number"), ("Height", "number"),
)
