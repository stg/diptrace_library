"""Public XML bus topology and bus connector data."""
from .dchxml import set_attribute
from .dchxml_settings import enum_text, field, numeric
from .model import Element


BUS_CONNECTIONS = ('Free', 'Free', 'Bus Wire', '3', 'Bus Connector', 'Free')


def project_bus_wire(line, *, units):
    result = Element('Wire')
    for public, own in (('Id', 'Number'), ('Sheet', 'Page')):
        set_attribute(result, public, line.scalar(own))
    for side in ('1', '2'):
        set_attribute(result, 'Connected'+side,
                      enum_text(line.scalar('ConnectMode'+side), BUS_CONNECTIONS, negative='Free'))
        for public, own in (('Bus', 'ConnectB'), ('Object', 'Connect'), ('SubObject', 'ConnectL')):
            set_attribute(result, public+side, line.scalar(own+side))
    points = line.select('Points/pt')
    if points:
        target = result.add('Points')
        for point in points:
            if len(point.arguments) != 3:
                raise ValueError(f'{point.path}: bus point requires X, Y and direction')
            item = target.add('Point')
            x, y = units.point(*point.arguments[:2])
            for name, value in (('X', numeric(x)), ('Y', numeric(y)), ('Dir', point.arguments[2])):
                set_attribute(item, name, value)
    if line.scalar('Group') >= 0:
        set_attribute(result, 'Group', line.scalar('Group'))
    if line.scalar('Selected'):
        set_attribute(result, 'Selected', True)
    return result


def project_bus(bus, *, units):
    result = Element('Bus')
    set_attribute(result, 'Id', bus.scalar('Number'))
    field(result, 'Name', bus.arguments[0])
    if not bus.scalar('Enabled'):
        set_attribute(result, 'Enabled', False)
    nets, numbers = bus.select('Nets/pt'), bus.select('Numbers/pt')
    if len(nets) != len(numbers):
        raise ValueError(f'{bus.path}: XML requires one connection number for each bus net')
    if nets:
        target = result.add('Nets')
        for net, number in zip(nets, numbers):
            item = target.add('Net')
            set_attribute(item, 'NetId', net.arguments[0])
            set_attribute(item, 'ConnectionNumber', number.arguments[0])
    lines = bus.select('Lines/Line')
    if lines:
        target = result.add('Wires')
        for line in lines:
            target.append(project_bus_wire(line, units=units))
    if bus.scalar('Locked'):
        set_attribute(result, 'Locked', True)
    return result


def project_buses(schematic, *, units):
    result = Element('Buses')
    for bus in schematic.select('Buses/Bus'):
        result.append(project_bus(bus, units=units))
    return result


def project_bus_connectors(schematic, *, units):
    result = Element('BusConnectors')
    for connector in schematic.select('PageConnectors/PageConnector'):
        if len(connector.arguments) != 3:
            raise ValueError(f'{connector.path}: bus connector requires name and position')
        item = result.add('BusConnector')
        name, x, y = connector.arguments
        x, y = units.point(x, y)
        field(item, 'Name', name)
        for public, value in (('Id', connector.scalar('Number')), ('Sheet', connector.scalar('Page')),
                              ('X', numeric(x)), ('Y', numeric(y))):
            set_attribute(item, public, value)
        if not connector.scalar('Enabled'):
            set_attribute(item, 'Enabled', False)
        set_attribute(item, 'Connected', connector.scalar('Connected'))
        if connector.scalar('Group') >= 0:
            set_attribute(item, 'Group', connector.scalar('Group'))
        for name in ('Selected', 'Locked'):
            if connector.scalar(name):
                set_attribute(item, name, True)
    return result


def project_groups(schematic):
    result = Element('Groups')
    for group in schematic.select('Groups/Group'):
        item = result.add('Group')
        set_attribute(item, 'Id', group.arguments[0])
        if not group.scalar('Enabled'):
            set_attribute(item, 'Enabled', False)
        if group.scalar('Selected'):
            set_attribute(item, 'Selected', True)
    return result
