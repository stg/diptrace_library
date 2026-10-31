"""Group ASC routing defaults and design checks by their current model meaning."""
from ...model.rule_records import CLEARANCE_KINDS, DRC
from ...model.routing_defaults import ROUTING
from ...model.settings_records import SETTINGS
from .values import booleans, numeric_row, rename, move_fields
from ..errors import PcbError


DRC_ALIASES = {'CheckPours': 'CheckCopperPours', 'ClassToClass': 'CheckClassToClass',
               'OnlineMode': 'RealTimeMode', 'Done': 'DRCDone',
               'CheckSameComponent': 'CheckSameComponentPads'}
SIZE_FIELDS = ('MinTrace', 'MinDrill', 'MinRing', 'MaxRing', 'MaxPlatedHole', 'MaxNonPlatedHole')


def _drc_tables(drc):
    clearances = drc.child('LayClearances')
    if clearances is not None:
        if clearances.values:
            raise PcbError(f'{clearances.path}: expected DRC clearance rows')
        for row in clearances.children():
            if row.kind != 'DRC_LayClearance' or row.values:
                raise PcbError(f'{row.path}: expected named DRC layer clearances')
            row.kind = 'LayClearance'
            rename(row, {'DRC_'+name: name for name in
                         ('SameTraceToTrace', 'SameSmdToVia', 'SameSmdToPad', 'SameSmdToSmd')})
            rows = row.children('pt')
            if len(rows) != 6 or row.child('ClearanceDetails') is not None:
                raise PcbError(f'{row.path}: expected six clearance rows')
            details = row.add('ClearanceDetails')
            for first, item in enumerate(rows):
                values = numeric_row(item, 7)
                for second in range(first, 7):
                    details.add(CLEARANCE_KINDS[first]+'To'+CLEARANCE_KINDS[second], values[second])
                item.detach()
    sizes = drc.child('LaySizes')
    if sizes is not None:
        if sizes.values:
            raise PcbError(f'{sizes.path}: expected DRC size rows')
        for row in sizes.children():
            values = numeric_row(row, 6, kind='DRC_LaySize')
            row.kind = 'LaySize'
            row.set_values()
            for name, value in zip(SIZE_FIELDS, values):
                row.add(name, value)


def unpack_rule_settings(board):
    settings = board.child('Settings')
    if settings is None:
        return
    booleans(settings, (name for name, field in SETTINGS.fields.items() if field.kind == 'boolean'))
    if any(settings.child(name) is not None for name in ROUTING.fields):
        routing = settings.child('Routing')
        if routing is None:
            routing = settings.add('Routing')
        move_fields(settings, routing, {name: name for name in ROUTING.fields})
    names = {'DRC_'+name: name for name in DRC.fields}
    for source, target in DRC_ALIASES.items():
        names['DRC_'+source] = target
    names.update({'DRC_LayClearances': 'LayClearances', 'DRC_LaySizes': 'LaySizes'})
    if any(settings.child(name) is not None for name in names):
        drc = board.child('DRC')
        if drc is None:
            drc = board.add('DRC')
        move_fields(settings, drc, names)
        booleans(drc, (name for name, field in DRC.fields.items() if field.kind == 'boolean'))
        _drc_tables(drc)
    names = {'Connectivity_'+source: target for source, target in
             (('Traces', 'Traces'), ('Shapes', 'Shapes'), ('Pours', 'CopperPours'))}
    if any(settings.child(name) is not None for name in names):
        connectivity = board.child('ConnectivityCheck')
        if connectivity is None:
            connectivity = board.add('ConnectivityCheck')
        move_fields(settings, connectivity, names)
        booleans(connectivity, names.values())
