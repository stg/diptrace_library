"""Supplied ratline endpoints and geometry; no connectivity recalculation."""
from ....common.conversion import import_notice
from ....common.xml_records import point


def read_ratlines(record, board, *, units, placements):
    collection = board.add('Connections')
    for index, source in enumerate(record.rows('Ratlines', 'Ratline')):
        source.integer('Id', index)  # Output counter, not an identity.
        values = dict(Enabled=source.boolean('Enabled', True), Hidden=source.boolean('Hidden', False))
        for end in (1, 2):
            for name, value in zip(('X', 'Y'), point(source, units, ('X'+str(end), 'Y'+str(end)), 0)):
                values[name+str(end)] = value
        stale = False
        for end in (1, 2):
            component, pad = source.integer('Comp'+str(end), -1), source.integer('Pad'+str(end), -1)
            placed = placements.get(component)
            mapped = placed.pad_positions.get(pad) if placed is not None else None
            stale |= pad > 0 and mapped is None
            values['Comp'+str(end)] = component if pad > 0 else -1
            values['Pad'+str(end)] = mapped if pad > 0 else -1
        source.finish()
        if stale:
            import_notice('info', 'stale-ratlines', 'Removed ratlines whose selected pads no longer exist.', (source.node,),
                          recoverability='current electrical data and valid ratlines retained')
            continue
        row = collection.add('Connection', index)
        for name, value in values.items():
            row.add(name, value)
