"""Prepare hierarchy pin links by public StringNumber/connector RefDes names."""
from .schematic_refs import _integer, _number_keys
from .references import Guard, Index, Property


def prepare_links(schematic):
    parts = schematic.select('Components/Part')
    targets = _number_keys(parts)
    named = {}
    for index, part in enumerate(parts):
        if part.scalar('Enabled') in (True, 'Y') and part.scalar('PartType') == 3:
            named.setdefault(part.values[1], (part.scalar('Number', index), part))
    changes = 0
    for part in parts:
        if part.scalar('Enabled') not in (True, 'Y') or part.scalar('PartType') != 4:
            continue
        first_page = None
        for pin in part.select('Pins/Pin'):
            if pin.scalar('Enabled') not in (True, 'Y'):
                continue
            identity, signature = _integer(pin.scalar('Number')), pin.scalar('StringNumber')
            target = targets.get(identity)
            valid = target is not None and target.scalar('PartType') == 3 and target.values[1] == signature
            if not valid and signature in named:
                identity, target = named[signature]
                if pin.scalar('Number') != identity:
                    pin.set_field('Number', identity)
                    changes += 1
            if first_page is None and target is not None and target.values[1] == signature:
                first_page = target.scalar('Page')
        if first_page is not None and part.scalar('Number1') != first_page:
            part.set_field('Number1', first_page)
            changes += 1
    return changes


def prepare_component_links(document):
    schematic = document.one('/Schematic')
    changes = prepare_links(schematic)
    parts = schematic.select('Components/Part')
    targets = _number_keys(parts)
    graph = document.references
    for part in parts:
        if part.scalar('Enabled') not in (True, 'Y') or part.scalar('PartType') != 4:
            continue
        for pin in part.select('Pins/Pin'):
            identity = _integer(pin.scalar('Number'))
            if pin.scalar('Enabled') not in (True, 'Y') or identity not in targets:
                continue
            target = targets[identity]
            field = pin.one('Number')
            if target is not None and target.scalar('PartType') == 3 and target.values[1] == pin.scalar('StringNumber') and not graph.manages(field):
                graph.bind(part, target, Index(field), Property(pin.one('StringNumber'), target_argument=1),
                           role='component-pin-reference',
                           guards=(Guard(part.one('PartType'), part.one('PartType').values),), preserve=True)
    return changes

