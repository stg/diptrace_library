"""Public XML net and wire views of the shared schematic data.

Connection numbers are current model facts. Rebuild identity references at the
document boundary before projecting a modified schematic.
"""
from .syntax import (set_attribute)
from ....common.xml_output import enum_text, field, numeric
from ....common.model import (Element)


WIRE_CONNECTIONS = ('Pin', 'Wire', '2', 'Bus', 'Free')
ARROWS = ('None', 'Forward', 'Backward')


def project_wire(line, *, units):
    result = Element('Wire')
    set_attribute(result, 'Id', line.scalar('Number'))
    set_attribute(result, 'Sheet', line.scalar('Page'))
    for side in ('1', '2'):
        mode = line.scalar('ConnectMode'+side)
        set_attribute(result, 'Connected'+side, 'Free' if mode < 0 else enum_text(mode, WIRE_CONNECTIONS))
        for public, own in (('Bus', 'ConnectB'), ('Object', 'Connect'), ('SubObject', 'ConnectL')):
            set_attribute(result, public+side, line.scalar(own+side))
    set_attribute(result, 'HiddenPower', line.scalar('Hidden'))
    set_attribute(result, 'CanUnhide', line.scalar('CanUnhide'))
    arrows = line.scalar('Arrows')
    if arrows > 0:
        set_attribute(result, 'Arrows', enum_text(arrows, ARROWS))
    if line.scalar('Group') >= 0:
        set_attribute(result, 'Group', line.scalar('Group'))
    if line.scalar('Selected'):
        set_attribute(result, 'Selected', True)
    points = line.select('Points/pt')
    if points:
        target = result.add('Points')
        for point in points:
            if len(point.arguments) != 3:
                raise ValueError(f'{point.path}: wire point requires X, Y and direction')
            x, y = units.point(*point.arguments[:2])
            item = target.add('Point')
            set_attribute(item, 'X', numeric(x))
            set_attribute(item, 'Y', numeric(y))
            set_attribute(item, 'Dir', point.arguments[2])
    return result


def project_net(net, *, units, hidden_ids=True):
    result = Element('Net')
    set_attribute(result, 'Id', net.scalar('Number'))
    set_attribute(result, 'NetClass', net.scalar('NetClass'))
    if hidden_ids:
        set_attribute(result, 'HiddenId', net.scalar('HiddenId'))
    for name in ('UniteByName', 'ConnectPinByName', 'Global', 'CustomColor'):
        if net.scalar(name):
            set_attribute(result, name, True)
    if net.scalar('CustomColor') and net.scalar('WireColor'):
        set_attribute(result, 'WireColor', net.scalar('WireColor'))
    if net.scalar('Locked'):
        set_attribute(result, 'Locked', True)
    if not net.scalar('Enabled'):
        set_attribute(result, 'Enabled', False)
    field(result, 'Name', net.arguments[0])
    pins = net.select('Parts/pt')
    if pins:
        target = result.add('Pins')
        for pin in pins:
            if len(pin.arguments) != 2:
                raise ValueError(f'{pin.path}: net member requires component and pin')
            item = target.add('Item')
            set_attribute(item, 'Part', pin.arguments[0])
            set_attribute(item, 'Pin', pin.arguments[1])
    lines = net.select('Lines/Line')
    if lines:
        target = result.add('Wires')
        for line in lines:
            target.append(project_wire(line, units=units))
    return result


def project_nets(schematic, *, units, hidden_ids=True):
    result = Element('Nets')
    for net in schematic.select('Nets/Net'):
        result.append(project_net(net, units=units, hidden_ids=hidden_ids))
    return result


def project_net_classes(schematic, *, units):
    result = Element('NetClasses')
    for index, source in enumerate(schematic.select('NetClasses/NetClass')):
        if len(source.arguments) != 10:
            raise ValueError(f'{source.path}: net class requires ten values')
        name, mode, width, clearance, update, *differential = source.arguments
        target = result.add('NetClass')
        set_attribute(target, 'Id', index)
        set_attribute(target, 'UpdateId', update)
        set_attribute(target, 'Type', enum_text(mode.value, ('Normal', 'Differential Pair')))
        for public, value in (('Width', width), ('Clearance', clearance)):
            if value.value != -1:
                set_attribute(target, public, numeric(units.length(value)))
        if mode.value == 1:
            for public, value in zip(('DifClearance', 'MaxUncoupledLength', 'Tolerance', 'Phase', 'Phase_ErrorLength'), differential):
                if public != 'DifClearance' or value.value != -1:
                    set_attribute(target, public, numeric(units.length(value)))
        field(target, 'Name', name)
    return result


def project_differential_pairs(schematic, *, include_ids=True):
    result = Element('DifferentialPairs')
    for index, source in enumerate(schematic.select('DifferentialPairs/DifferentialPair')):
        if len(source.arguments) != 7:
            raise ValueError(f'{source.path}: differential pair requires seven values')
        name, enabled, positive, negative, net_class, custom, color = source.arguments
        if not enabled.value:
            continue
        target = result.add('DifferentialPair')
        if include_ids:
            set_attribute(target, 'Id', index)
        for public, value in (('PosNet', positive), ('NegNet', negative), ('NetClass', net_class)):
            set_attribute(target, public, value)
        if custom.value:
            set_attribute(target, 'CustomColor', True)
            set_attribute(target, 'WireColor', color)
        field(target, 'Name', name)
    return result
