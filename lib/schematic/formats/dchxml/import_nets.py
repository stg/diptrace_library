"""Public net/bus topology into the shared identity-binding vocabulary."""
from .buses import (BUS_CONNECTIONS)
from ....common.xml_records import (enum_value, point, replace_rows)
from .nets import (WIRE_CONNECTIONS, ARROWS)
from ....common.model import (Element)
from ...model.new import (fields)


def _sheet(record, sheets):
    key = record.integer('Sheet', 0)
    if key == -1:
        # format exports retain wires without a sheet. This is a stored state,
        # not an instruction to attach them to the first available sheet.
        return key
    if key not in sheets:
        raise ValueError(f'{record.node.path}: unresolved sheet Id {key}')
    return sheets[key]


def _class(record, classes):
    key = record.integer('NetClass', 0)
    if key >= 0 and key not in classes:
        raise ValueError(f'{record.node.path}: unresolved net-class Id {key}')
    return classes[key] if key >= 0 else key


def _wire(record, *, index, owner, units, sheets, bus=False):
    line = Element('Line')
    fields(line, Number=record.integer('Id', index), Page=_sheet(record, sheets),
           Region=0, Selected=record.boolean('Selected', False), Group=record.integer('Group', -1))
    labels = BUS_CONNECTIONS if bus else WIRE_CONNECTIONS
    for side in ('1', '2'):
        line.add('ConnectMode'+side, enum_value(record.value('Connected'+side, 'Free'), labels))
        for public, own in (('Bus', 'ConnectB'), ('Object', 'Connect'), ('SubObject', 'ConnectL')):
            line.add(own+side, record.integer(public+side, -1))
    if bus:
        line.add('BusNumber', owner)
    else:
        fields(line, NetNumber=owner, Hidden=record.boolean('HiddenPower', False),
               CanUnhide=record.boolean('CanUnhide', False), Arrows=enum_value(record.value('Arrows', 'None'), ARROWS))
    points = line.add('Points')
    for item in record.rows('Points', 'Point'):
        points.add('pt', *point(item, units), item.integer('Dir', 0))
        item.finish()
    record.finish()
    return line


def read_nets(record, schematic, *, units, sheets, classes):
    nets, keys = [], set()
    for index, source in enumerate(record.rows('Nets', 'Net')):
        key = source.integer('Id', index)
        if key in keys:
            raise ValueError(f'{source.node.path}: duplicate net Id')
        keys.add(key)
        net = Element('Net', source.text('Name', ''))
        fields(net, Number=key, Enabled=source.boolean('Enabled', True),
               UniteByName=source.boolean('UniteByName', False), ConnectPinByName=source.boolean('ConnectPinByName', False),
               Locked=source.boolean('Locked', False), ActiveLine=-1, ActivePoint=-1,
               Width=-1, Clearance=-1, NetClass=_class(source, classes),
               CustomColor=source.boolean('CustomColor', False), WireColor=source.integer('WireColor', 0),
               Global=source.boolean('Global', False))
        hidden = net.add('HiddenId', source.integer('HiddenId', index))
        hidden.annotations.update(default_value=index, asc_omit='not present in ASC')
        members = net.add('Parts')
        for item in source.rows('Pins', 'Item'):
            members.add('pt', item.integer('Part'), item.integer('Pin'))
            item.finish()
        wires = net.add('Lines')
        for ordinal, item in enumerate(source.rows('Wires', 'Wire')):
            wires.append(_wire(item, index=ordinal, owner=key, units=units, sheets=sheets))
        source.finish()
        nets.append(net)
    replace_rows(schematic, 'Nets', nets)


def read_pairs(record, schematic, *, classes):
    pairs = []
    for index, source in enumerate(record.rows('DifferentialPairs', 'DifferentialPair')):
        source.integer('Id', index)
        pairs.append(Element('DifferentialPair', source.text('Name', ''), True,
                             source.integer('PosNet'), source.integer('NegNet'), _class(source, classes),
                             source.boolean('CustomColor', False), source.integer('WireColor', 0)))
        source.finish()
    replace_rows(schematic, 'DifferentialPairs', pairs)


def read_buses(record, schematic, *, units, sheets):
    buses, keys = [], set()
    for index, source in enumerate(record.rows('Buses', 'Bus')):
        key = source.integer('Id', index)
        if key in keys:
            raise ValueError(f'{source.node.path}: duplicate bus Id')
        keys.add(key)
        bus = Element('Bus', source.text('Name', ''))
        fields(bus, Number=key, Enabled=source.boolean('Enabled', True), Locked=source.boolean('Locked', False),
               ActiveLine=-1, ActivePoint=-1, Region=0)
        members, numbers = bus.add('Nets'), bus.add('Numbers')
        for item in source.rows('Nets', 'Net'):
            members.add('pt', item.integer('NetId'))
            numbers.add('pt', item.integer('ConnectionNumber'))
            item.finish()
        lines = bus.add('Lines')
        for ordinal, item in enumerate(source.rows('Wires', 'Wire')):
            lines.append(_wire(item, index=ordinal, owner=key, units=units, sheets=sheets, bus=True))
        source.finish()
        buses.append(bus)
    replace_rows(schematic, 'Buses', buses)
    connectors, keys = [], set()
    for index, source in enumerate(record.rows('BusConnectors', 'BusConnector')):
        key = source.integer('Id', index)
        if key in keys:
            raise ValueError(f'{source.node.path}: duplicate bus-connector Id')
        keys.add(key)
        connector = Element('PageConnector', source.text('Name', ''), *point(source, units, default=0))
        fields(connector, Number=key, Enabled=source.boolean('Enabled', True), Connected=source.boolean('Connected', False),
               Page=_sheet(source, sheets), BusNumber=-1, Region=0, Group=source.integer('Group', -1),
               Selected=source.boolean('Selected', False), Locked=source.boolean('Locked', False))
        source.finish()
        connectors.append(connector)
    replace_rows(schematic, 'PageConnectors', connectors)


def read_groups(record, schematic):
    groups, keys = [], set()
    for index, source in enumerate(record.rows('Groups', 'Group')):
        key = source.integer('Id', index)
        if key in keys:
            raise ValueError(f'{source.node.path}: duplicate group Id')
        keys.add(key)
        group = Element('Group', key, 0, 0)
        fields(group, Enabled=source.boolean('Enabled', True), Selected=source.boolean('Selected', False))
        source.finish()
        groups.append(group)
    replace_rows(schematic, 'Groups', groups)
