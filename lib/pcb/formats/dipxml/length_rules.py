"""Public length-rule records, with saved keys confined to import assembly."""
from ....common.conversion import import_notice
from ....common.xml_records import enum_value, length
from ...model.length_matching import DEFAULT_FIXED_LENGTH, DEFAULT_DELTA
from .keys import position


TYPES = ('By User', 'By NetClass')


def _policy(source, target, *, placements, classes, units):
    target.add('Name', source.text('Name', ''))
    target.add('FixedLength', length(source.number('FixedLength'), units)
               if source.has('FixedLength') else DEFAULT_FIXED_LENGTH)
    target.add('Delta', length(source.number('Delta'), units) if source.has('Delta') else DEFAULT_DELTA)
    target.add('AnyError', source.boolean('AnyError', False))
    kind = enum_value(source.value('Type', 'By User'), TYPES)
    target.add('Type', kind)
    key = source.integer('NetClass', -1)
    # A user rule has no class association. An unused selection must not force
    # resolution of a class unrelated to this policy.
    target.add('NetClass', position(key, classes, label='length-rule class', path=source.node.path)
               if kind == 1 else -1)
    rows = target.add('Rules')
    for index, row in enumerate(source.rows('Rules', 'Rule')):
        values = dict(NetId=row.integer('NetId'))
        stale = False
        for end in (1, 2):
            component, pad = row.integer('Comp'+str(end)), row.integer('Pad'+str(end))
            placement = placements.get(component)
            mapped = placement.pad_positions.get(pad) if placement is not None else None
            stale |= pad > 0 and mapped is None
            values['Comp'+str(end)] = component if pad > 0 else -1
            values['Pad'+str(end)] = mapped if pad > 0 else -1
        values['Length'] = length(row.number('Length', 0), units)
        values['Error'] = row.boolean('Error', False)
        row.finish()
        if stale:
            import_notice('info', 'stale-length-connections',
                          'Removed length connections whose selected pads no longer exist.', (row.node,),
                          recoverability='current policies and valid connections retained')
            continue
        node = rows.add('Rule', index)
        for name, value in values.items():
            node.add(name, value)
    source.finish()


def read_length_rules(record, board, *, placements, classes, units):
    if (source := record.take('MainLengthRule')) is not None:
        _policy(source, board.add('MainLengthRule'), placements=placements, classes=classes, units=units)
    target = board.add('LengthRules')
    for index, source in enumerate(record.rows('LengthRules', 'LengthRule')):
        _policy(source, target.add('LengthRule', index), placements=placements, classes=classes, units=units)
