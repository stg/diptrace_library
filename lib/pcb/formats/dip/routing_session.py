"""Consume transient routing-session data during ordinary document import.

Opening a design normalizes this session away, as does saving. Validate its
scalar and collection encoding without adding preview geometry, selections or
undo history to the authored model. Committed board routing is read separately.
"""
from ....common.conversion import import_notice


def _values(reader, kind, count):
    read = getattr(reader, kind)
    for _ in range(count):
        read()


def _trace_points(reader):
    for _ in range(reader.count('routing-session points')):
        _values(reader, 'integer', 9)
        _values(reader, 'number', 6)
        _values(reader, 'boolean', 4)


def _side_points(reader):
    for _ in range(reader.count('routing-session side points')):
        _values(reader, 'number', 4)
        _values(reader, 'integer', 3)
        _values(reader, 'boolean', 2)


def _pair_segment(reader):
    _values(reader, 'integer', 6)
    for _ in range(reader.count('routing-session center points')):
        _values(reader, 'number', 2)
        _values(reader, 'integer', 9)
        _values(reader, 'boolean', 2)
        _side_points(reader)
        _side_points(reader)


def _route(reader):
    _values(reader, 'integer', 11)
    _values(reader, 'number', 3)
    _trace_points(reader)
    _values(reader, 'number', 2)
    _values(reader, 'integer', 8)
    _trace_points(reader)
    for _ in range(reader.count('routing-session trace history')):
        reader.integer()
        reader.boolean()
        _values(reader, 'integer', 8)
        _trace_points(reader)


def read_routing_session(reader):
    """Consume the active section after its presence flag, retaining no model data."""
    _values(reader, 'boolean', 3)
    _values(reader, 'integer', 5)
    for _ in range(2):
        _values(reader, 'integer', reader.count('routing-session selections'))
    for _ in range(reader.count('routing-session routes')):
        _route(reader)
    _values(reader, 'integer', 4)
    _values(reader, 'number', 2)
    _pair_segment(reader)
    _pair_segment(reader)
    for _ in range(2):
        _values(reader, 'number', 4)
        _values(reader, 'integer', 3)
        _values(reader, 'boolean', 2)
    for _ in range(reader.count('routing-session pair history')):
        _pair_segment(reader)
        reader.integer()
        _values(reader, 'boolean', 2)
    import_notice('info', 'interactive-routing-session',
                  'Cleared transient interactive routing state during document import.',
                  recoverability='normal file loading and saving clear this session; committed board routing remains')
