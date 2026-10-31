"""Current public ASC traces into named geometry and temporary endpoint keys."""
from ...model.routing_records import POINT
from ..assembly.routing_inputs import TraceInput
from ..connection_types import CONNECTION_NAMES
from ..errors import PcbError
from .values import booleans, rename, numeric_row
from . import routing_columns as columns


def _point(row, index, *, separate=False):
    names = columns.SEPARATE_POINT if separate else columns.POINT
    values = numeric_row(row, len(names), kind='Point' if separate else 'pt',
                         flags=columns.indices(names, columns.FLAGS),
                         integers=columns.indices(names, columns.INTEGERS))
    row.kind = 'Point'
    row.set_values(index)
    for name, value in zip(names, values):
        if name in columns.COMPATIBILITY:
            continue
        try:
            if not POINT.fields[name].readonly:
                POINT.fields[name].validate(value.value)
        except (TypeError, ValueError) as error:
            raise PcbError(f'{row.path}/{name}: {error}') from error
        row.add(name, value)
    # The two row dialects place the repeated through-via choice differently.
    # Direction and repeated via size/span values are calculated by the writer
    # from current segment geometry and the selected via-style identity.
    return row


def unpack_trace(trace, *, separate=False):
    """Consume one current trace without keeping redundant compatibility flags.

    Ordinary-net ASC uses opposite L2/P2 spellings from separate pair traces.
    Both dialects become Object/SubObject/Point endpoint selectors here.
    """
    names = {'Connect1': 'Object1', 'ConnectL1': 'SubObject1', 'ConnectP1': 'Point1',
             'Connect2': 'Object2', 'ConnectMode1': 'Connected1', 'ConnectMode2': 'Connected2',
             'PairLine_Link': 'PairSeparateTrace', 'Teardrops_Connected': 'ConnectedTeardrops'}
    names.update({'ConnectL2': 'SubObject2', 'ConnectP2': 'Point2'} if separate else
                 {'ConnectP2': 'SubObject2', 'ConnectL2': 'Point2'})
    if separate:
        names['NetLine_Link'] = 'TraceId'
    rename(trace, names)
    for end in (1, 2):
        for name in ('Object', 'SubObject', 'Point', 'Connected'):
            field = trace.child(name+str(end))
            if (field is None or len(field.arguments) != 1 or field.children()
                    or type(field.values[0]) is not int):
                raise PcbError(f'{trace.path}: expected integer {name}{end}')
        if trace['Connected'+str(end)] not in CONNECTION_NAMES:
            raise PcbError(f'{trace.path}: unimplemented connection mode {trace["Connected"+str(end)]}')
    booleans(trace, ('Selected',))
    saved = trace.one('OldNumber')
    if len(saved.values) != 1 or type(saved.values[0]) is not int:
        raise PcbError(f'{saved.path}: expected a saved trace key')
    key = saved.values[0]
    saved.detach()
    for name in ('ConnectedToLine1', 'ConnectedToLine2', 'FreeEnd1', 'FreeEnd21', 'FreeEnd2'):
        if (field := trace.child(name)) is not None:
            field.detach()
    points = tuple(_point(row, index, separate=separate)
                   for index, row in enumerate(trace.one('Points').children()))
    for item in trace.select('ConnectedTeardrops/pt'):
        if len(item.values) != 1 or type(item.values[0]) is not int or item.children():
            raise PcbError(f'{item.path}: expected one teardrop key')
        item.kind = 'Item'
    return TraceInput(trace, key, points)
