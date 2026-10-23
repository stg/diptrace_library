"""Simulator object links, independent of plotting and display-name choices."""
from .references import Guard, Index, Key


def _schematic(node):
    while node is not None and node.kind != 'Schematic':
        node = node.parent
    return node


def collections(source, role):
    role = role.removeprefix('xml-')
    if not role.startswith('simulation-'):
        return None
    schematic = _schematic(source)
    if schematic is None:
        return None
    names = ('Components',) if role == 'simulation-current' else (
        ('Nets',) if role in ('simulation-voltage', 'simulation-ground') else ('Components', 'Nets'))
    return tuple(owner for name in names if (owner := schematic.child(name)) is not None)


def specifications(document, *, public_xml=False):
    schematic = document.root.child('Source').child('Schematic') if public_xml else document.root.child('Schematic')
    if schematic is None:
        return
    simulator = schematic.child('Simulator' if public_xml else 'ssimulator')
    if simulator is None:
        return
    key = 'Id' if public_xml else 'Number'
    targets = {}
    for label, path in (('current', 'Components/Part'), ('voltage', 'Nets/Net')):
        choices = {}
        for item in schematic.select(path):
            number = item.scalar(key)
            choices[number] = item if number not in choices else None
        targets[label] = choices
    prefix = 'xml-simulation-' if public_xml else 'simulation-'
    projection = Key if public_xml else Index
    ground = simulator.child('GndNetId' if public_xml else 'gndnum')
    if ground is not None and ground.values[0] >= 0:
        yield simulator, targets['voltage'].get(ground.values[0]), prefix+'ground', (projection(ground),), ()
    for signal in simulator.select('Signals/Signal' if public_xml else 'signals/signal'):
        kind = signal.child('Type' if public_xml else 'signal_tp')
        number = signal.child('Id' if public_xml else 'signal_num')
        if kind is None or number is None or number.values[0] < 0:
            continue
        label = ({'Current': 'current', 'Voltage': 'voltage'} if public_xml else
                 {0: 'current', 1: 'voltage'}).get(kind.values[0], 'unknown')
        yield signal, targets.get(label, {}).get(number.values[0]), prefix+label, (
            projection(number),), (Guard(kind, kind.values),)


def valid_target(reference):
    owners = collections(reference.source, reference.role)
    if owners is None:
        return True
    kind = 'Part' if reference.role.endswith('-current') else 'Net'
    return reference.target.kind == kind and reference.target.parent in owners
