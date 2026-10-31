"""Public pad-shape names and their current numeric meanings.

Main stacks and terminals have different unnamed values. Numeric aliases keep
their supplied value; an empty label cannot recover a code lost by an exporter.
"""
from .model import Value
from .xml_output import enum_text
from .xml_records import enum_value


_NAMES = {0: 'Ellipse', 1: 'Obround', 2: 'Rectangle', 3: 'Polygon', 4: 'D-shape', 20: 'Fiducial'}
_CODES = {name.casefold(): code for code, name in _NAMES.items()}


def shape_code(value, *, terminal=False):
    raw = value.value if isinstance(value, Value) else value
    if raw == '':
        return -1 if terminal else 5
    code = _CODES.get(str(raw).casefold())
    if code is not None and not (terminal and code == 20):
        return code
    return enum_value(value, ())


def shape_label(value, *, terminal=False):
    # Reuse ordinary enum validation for integer values and unit rejection.
    numeric = enum_text(value, ())
    code = int(numeric)
    if code == (-1 if terminal else 5):
        return ''
    return _NAMES.get(code, numeric) if not (terminal and code == 20) else numeric
