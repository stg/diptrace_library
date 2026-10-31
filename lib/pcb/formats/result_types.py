"""Numeric ASC/DIP check domains corresponding to the named XML vocabulary."""

# The model groups the four named paused domains after ordinary check domains.
# Their numeric file codes instead retain the underlying trace/via category.
_PAUSED_FILE_CODES = {24: 200, 25: 216, 26: 203, 27: 212}
_PAUSED_MODEL_CODES = {saved: current for current, saved in _PAUSED_FILE_CODES.items()}


def object_type_from_file(value):
    return _PAUSED_MODEL_CODES.get(value, value)


def object_type_to_file(value):
    return _PAUSED_FILE_CODES.get(value, value)
