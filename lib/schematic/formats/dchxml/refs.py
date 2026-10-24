"""Public DCHXML keys and positional pin/point links over owned elements."""
from ....common.references import (Guard, Index, Key, Property, ReferenceError, Segment)


def _children(parent, container, kind):
    owner = parent.child(container) if parent is not None else None
    return owner.children(kind) if owner is not None else []


def _keys(records, name='Id'):
    result = {}
    for record in records:
        value = record.scalar(name)
        if value is not None:
            result[value] = record if value not in result else None
    return result


def _at(records, value):
    if isinstance(value, bool):
        return None
    try:
        position = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return records[position] if position == value and 0 <= position < len(records) else None


def _specifications(document):
    source = document.root.child('Source')
    schematic = source.child('Schematic') if source is not None else None
    if schematic is None:
        return
    library = source.child('Library')
    pattern_library = library.child('Library') if library is not None else None
    styles = _keys(_children(library, 'Components', 'Component'), 'ComponentStyle')
    patterns = _keys(_children(pattern_library, 'Patterns', 'Pattern'), 'PatternStyle')
    pad_styles = _keys(_children(pattern_library, 'PadStyles', 'PadStyle'), 'Name')
    parts = _keys(_children(schematic, 'Components', 'Part'))
    nets = _keys(_children(schematic, 'Nets', 'Net'))
    buses = _keys(_children(schematic, 'Buses', 'Bus'))
    connectors = _keys(_children(schematic, 'BusConnectors', 'BusConnector'))
    groups = _keys(_children(schematic, 'Groups', 'Group'))
    classes = _keys(_children(schematic, 'NetClasses', 'NetClass'))
    settings = schematic.child('SheetSettings')
    sheets = _keys(_children(settings, 'Sheets', 'Sheet'))

    def field_link(node, name, targets, role, key='Id', *, negative=False):
        field = node.child(name)
        if field is not None and (not negative or field.values[0] >= 0):
            yield node, targets.get(field.values[0]), role, (Key(field, key),), ()

    active = settings.child('ActiveSheet') if settings is not None else None
    if active is not None and active.values[0] >= 0:
        target = _at(_children(settings, 'Sheets', 'Sheet'), active.values[0])
        yield settings, target, 'xml-active-sheet', (Index(active),), ()

    from .tables import (TITLE_BLOCKS)
    for sheet in sheets.values():
        if sheet is None:
            continue
        for name in TITLE_BLOCKS:
            for block in sheet.children(name):
                fields = _keys(_children(block, 'Fields', 'Field'))
                for column in _children(block, 'Cells', 'Item'):
                    for cell in column.children('Item'):
                        yield from field_link(cell, 'FieldId', fields, 'xml-title-field', negative=True)

    for container, kind in (('BusConnectors', 'BusConnector'), ('Tables', 'Table')):
        for item in _children(schematic, container, kind):
            yield from field_link(item, 'Sheet', sheets, 'xml-'+kind.lower()+'-sheet')
    for container, kind in (('Components', 'Part'), ('Shapes', 'Shape'), ('Tables', 'Table'),
                             ('BusConnectors', 'BusConnector')):
        for item in _children(schematic, container, kind):
            yield from field_link(item, 'Group', groups, 'xml-group', negative=True)

    for pattern in patterns.values():
        if pattern is None:
            continue
        for pad in [pattern.child('DefPad'), *_children(pattern, 'Pads', 'Pad')]:
            if pad is not None:
                yield from field_link(pad, 'Style', pad_styles, 'xml-pad-style', 'Name')
        targets = {name: _keys(_children(pattern, container, name))
                   for name, container in (('Pad', 'Pads'), ('Shape', 'Shapes'), ('Hole', 'Holes'))}
        local_groups = _keys(_children(pattern, 'Groups', 'Item'))
        for container, kind in (('Pads', 'Pad'), ('Shapes', 'Shape'), ('Holes', 'Hole'), ('Dimensions', 'Dimension')):
            for item in _children(pattern, container, kind):
                yield from field_link(item, 'Group', local_groups, 'xml-pattern-group', negative=True)
        for shape in _children(pattern, 'Shapes', 'Shape'):
            yield from field_link(shape, 'PadId', targets['Pad'], 'xml-pattern-shape-pad', negative=True)
        for dimension in _children(pattern, 'Dimensions', 'Dimension'):
            for side in ('1', '2'):
                mode = dimension.child('Connected'+side)
                owner = dimension.child('Object'+side)
                member = dimension.child('SubObject'+side)
                if mode is None or member is None:
                    continue
                if mode.values[0] in (-1, '-1'):
                    continue
                # Ordinary local targets use public Id keys; Object is unused.
                # Terminal selectors remain literal in this syntax-level view.
                choices = targets.get(mode.values[0], {})
                target = choices.get(member.values[0])
                guards = (Guard(mode, mode.values),)
                indices = (Key(member),)
                point = dimension.child('Point'+side)
                if mode.values[0] == 'Shape' and target is not None and target.scalar('Type') in ('Polyline', 'Polygon') and point is not None:
                    points = target.child('Points')
                    target = _at([row for row in points.children() if row.kind in ('Item', 'Point')]
                                 if points is not None else [], point.values[0])
                    indices = (Key(member, ancestor=2), Index(point))
                elif mode.values[0] == 'Terminal':
                    indices = tuple(Index(field) for field in (owner, member, point) if field is not None)
                yield dimension, target, 'xml-dimension-'+side, indices, guards
    for component in styles.values():
        if component is None:
            continue
        for part in component.children('Part'):
            if part.scalar('PartType') == 'Hierarchy Block':
                for pin in _children(part, 'Pins', 'Pin'):
                    number, name = pin.child('PadId'), pin.child('PadNumber')
                    if number is not None and name is not None and number.values[0] >= 0:
                        target = parts.get(number.values[0])
                        definition = styles.get(target.scalar('ComponentStyle')) if target is not None else None
                        variant = _at(definition.children('Part') if definition is not None else [],
                                      target.scalar('ComponentPart', 0) if target is not None else 0)
                        if (target is None or target.scalar('RefDes') != name.values[0] or
                                variant is None or variant.scalar('PartType') != 'Hierarchy Connector'):
                            target = None
                        yield part, target, 'xml-hierarchy-connector', (Key(number), Property(name, 'RefDes')), (
                            Guard(part.one('PartType'), part.one('PartType').values),)
            local_groups = _keys(_children(part, 'Groups', 'Item'))
            for container, kind in (('Pins', 'Pin'), ('Shapes', 'Shape')):
                for item in _children(part, container, kind):
                    yield from field_link(item, 'Group', local_groups, 'xml-symbol-group', negative=True)
            pattern = part.child('Pattern')
            pads = {}
            if pattern is not None:
                yield from field_link(pattern, 'Style', patterns, 'xml-pattern-style', 'PatternStyle')
                footprint=patterns.get(pattern.scalar('Style'))
                pads=_keys(_children(footprint,'Pads','Pad'))
                for pin in _children(part,'Pins','Pin') if part.scalar('PartType', 'Normal') == 'Normal' else ():
                    yield from field_link(pin,'PadId',pads,'xml-definition-pin-pad',negative=True)
            for connection in _children(part, 'InternalConnections', 'IntCon'):
                for name in ('X', 'Y'):
                    yield from field_link(connection, name, pads, 'xml-internal-pad-'+name, negative=True)
    for part in parts.values():
        if part is None:
            continue
        style, variant = part.child('ComponentStyle'), part.child('ComponentPart')
        if style is not None:
            component = styles.get(style.values[0])
            if variant is not None:
                target = _at(component.children('Part') if component is not None else [], variant.values[0])
                yield part, target, 'xml-component-definition', (
                    Key(style, 'ComponentStyle', ancestor=1), Index(variant)), ()
            else:
                yield part, component, 'xml-component-style', (Key(style, 'ComponentStyle'),), ()
        yield from field_link(part, 'Sheet', sheets, 'xml-part-sheet')
        for pin in _children(part, 'Pins', 'Pin'):
            yield from field_link(pin, 'NetId', nets, 'xml-pin-net', negative=True)
    for shape in _children(schematic, 'Shapes', 'Shape'):
        yield from field_link(shape, 'Sheet', sheets, 'xml-shape-sheet')
        for name, targets, role in (('NetId', nets, 'xml-drawing-net-name'), ('BusId', buses, 'xml-drawing-bus-name')):
            yield from field_link(shape, name, targets, role, negative=True)
    for pair in _children(schematic, 'DifferentialPairs', 'DifferentialPair'):
        for name in ('PosNet', 'NegNet'):
            yield from field_link(pair, name, nets, 'xml-differential-'+name)
        yield from field_link(pair, 'NetClass', classes, 'xml-differential-class')
    for net in nets.values():
        if net is None:
            continue
        yield from field_link(net, 'NetClass', classes, 'xml-net-class')
        for member in _children(net, 'Pins', 'Item'):
            part, pin = member.child('Part'), member.child('Pin')
            if part is not None and pin is not None:
                owner = parts.get(part.values[0])
                target = _at(_children(owner, 'Pins', 'Pin'), pin.values[0])
                yield member, target, 'xml-net-member', (Key(part, ancestor=2), Index(pin)), ()
    for owner, bus_wire in [(net, False) for net in nets.values() if net is not None] + [
            (bus, True) for bus in buses.values() if bus is not None]:
        if bus_wire:
            for member in _children(owner, 'Nets', 'Net'):
                yield from field_link(member, 'NetId', nets, 'xml-bus-net')
        for wire in _children(owner, 'Wires', 'Wire'):
            yield from field_link(wire, 'Sheet', sheets, 'xml-wire-sheet', negative=True)
            yield from field_link(wire, 'Group', groups, 'xml-group', negative=True)
            for side in ('1', '2'):
                mode = wire.child('Connected'+side)
                if mode is None or mode.values[0] == 'Free':
                    continue
                object_field = wire.child('Object'+side)
                subobject = wire.child('SubObject'+side)
                if object_field is None:
                    continue
                guard = Guard(mode, mode.values)
                if bus_wire and mode.values[0] == 'Bus Connector':
                    yield wire, connectors.get(object_field.values[0]), 'xml-bus-connector-'+side, (Key(object_field),), (guard,)
                elif subobject is None:
                    continue
                elif not bus_wire and mode.values[0] == 'Pin':
                    part = parts.get(object_field.values[0])
                    target = _at(_children(part, 'Pins', 'Pin'), subobject.values[0])
                    yield wire, target, 'xml-wire-pin-'+side, (
                        Key(object_field, ancestor=2), Index(subobject)), (guard,)
                elif (not bus_wire and mode.values[0] in ('Wire', 'Bus')) or (bus_wire and mode.values[0] == 'Bus Wire'):
                    bus = wire.child('Bus'+side)
                    targets = buses if bus_wire or mode.values[0] == 'Bus' else nets
                    remote = owner if bus is None or bus.values[0] < 0 else targets.get(bus.values[0])
                    # A net-to-bus endpoint always names the bus explicitly.
                    if not bus_wire and mode.values[0] == 'Bus' and (bus is None or bus.values[0] < 0):
                        remote = None
                    route = _keys(_children(remote, 'Wires', 'Wire')).get(object_field.values[0])
                    points = _children(route, 'Points', 'Point')
                    position = subobject.values[0]
                    end = _at(points, position)
                    target = Segment(points[position-1], end) if end is not None and position > 0 else None
                    indices = [Key(object_field, ancestor=2), Index(subobject)]
                    guards = [guard]
                    if bus is not None:
                        if bus.values[0] >= 0:
                            indices.append(Key(bus, ancestor=4))
                        else:
                            guards.append(Guard(bus, bus.values))
                    role = 'xml-bus-segment-' if bus_wire or mode.values[0] == 'Bus' else 'xml-wire-segment-'
                    yield wire, target, role+side, tuple(indices), tuple(guards)
                else:
                    yield wire, None, 'xml-unmapped-wire-mode-'+str(mode.values[0]), (
                        Key(object_field), Index(subobject)), (guard,)
    from ...model.simulation_refs import (specifications as simulation_specifications)
    yield from simulation_specifications(document, public_xml=True)


def _local_collection(source, role, graph):
    if role == 'xml-active-sheet':
        return source.child('Sheets')
    if role == 'xml-definition-pin-pad' or role.startswith('xml-internal-pad-'):
        pattern = source.parent.parent.child('Pattern')
        links = graph.outgoing(pattern, role='xml-pattern-style') if pattern is not None else []
        return links[0].target.child('Pads') if len(links) == 1 else None
    if role.startswith('xml-dimension-'):
        side = role[-1]
        mode = source.scalar('Connected'+side)
        if mode in ('Pad', 'Shape', 'Hole'):
            return source.parent.parent.child({'Pad': 'Pads', 'Shape': 'Shapes', 'Hole': 'Holes'}[mode])
    if role == 'xml-pattern-shape-pad':
        return source.parent.parent.child('Pads')
    if role == 'xml-title-field':
        return source.parent.parent.parent.child('Fields')
    if role in ('xml-pattern-group', 'xml-symbol-group'):
        return source.parent.parent.child('Groups')
    return None


def bind_references(document):
    graph = document.references

    def issue_collections(source, role):
        if role == 'xml-hierarchy-connector':
            return (document.one('/Source/Schematic/Components'),)
        from ...model.simulation_refs import (collections as simulation_scopes)
        simulation = simulation_scopes(source, role)
        if simulation is not None:
            return simulation
        if role.startswith('xml-dimension-') and source.scalar('Connected'+role[-1]) == 'Terminal':
            pattern = source.parent.parent
            pads = pattern.child('Pads')
            if pads is None:
                return (pattern,)
            number = source.scalar('Object'+role[-1])
            try:
                pad = _at(pads.children('Pad'), number-1)
            except (TypeError, ValueError, OverflowError):
                pad = None
            styles = graph.outgoing(pad, role='xml-pad-style') if pad is not None else []
            if len(styles) == 1:
                style = styles[0].target
                return (pads, style, *(node for node in style.walk() if node.kind in ('Terminals', 'Points')))
            return (pads,)
        owner = _local_collection(source, role, graph)
        if owner is not None and role.startswith('xml-dimension-'):
            mode = source.scalar('Connected'+role[-1])
            target = _keys(owner.children('Shape')).get(source.scalar('SubObject'+role[-1])) if mode == 'Shape' else None
            points = target.child('Points') if target is not None else None
            if points is not None:
                return (owner, points)
        return (owner,) if owner is not None else None

    with graph.binding_batch():
        for source, target, role, indices, guards in _specifications(document):
            if target is None:
                graph.note(source, f'{role}: target cannot be resolved', *indices,
                           collections=issue_collections(source, role), guards=guards)
            else:
                try:
                    graph.bind(source, target, *indices, role=role, guards=guards, preserve=True)
                except ReferenceError as error:
                    graph.note(source, str(error), *indices, collections=issue_collections(source, role), guards=guards)
    for node in document.root.walk():
        if node.kind in ('Components', 'Pins', 'Nets', 'Buses', 'BusConnectors', 'Groups', 'Wires', 'Points', 'Sheets', 'NetClasses', 'Patterns', 'PadStyles',
                         'Pads', 'Shapes', 'Holes', 'Dimensions', 'Fields', 'Signals'):
            graph.watch(node)
    document._reference_validator = validate_references


def validate_references(document):
    from .keys import (validate_keys)
    validate_keys(document)
    graph = document.references
    for source, target, role, indices, guards in _specifications(document):
        for item in indices:
            if not graph.manages(item.field, item.argument) and not graph.unresolved_slot(item.field, item.argument):
                raise ReferenceError(f'{role}: new reference needs an explicit binding')
    for reference in graph:
        role = reference.role
        if role == 'xml-hierarchy-connector':
            definitions = graph.outgoing(reference.target, role='xml-component-definition')
            if (reference.target.parent is not document.one('/Source/Schematic/Components') or
                    len(definitions) != 1 or definitions[0].target.scalar('PartType') != 'Hierarchy Connector'):
                raise ReferenceError(f'{role}: target is outside its hierarchy connector collection at {reference.source.path}')
        if role.startswith('xml-simulation-'):
            from ...model.simulation_refs import (valid_target)
            if not valid_target(reference):
                raise ReferenceError(f'{role}: target is outside its schematic collection at {reference.source.path}')
        if role in ('xml-active-sheet', 'xml-definition-pin-pad', 'xml-pattern-shape-pad', 'xml-title-field', 'xml-pattern-group', 'xml-symbol-group') or role.startswith(('xml-dimension-', 'xml-internal-pad-')):
            owner = _local_collection(reference.source, role, graph)
            target = reference.target
            if role.startswith('xml-dimension-') and target.kind in ('Item', 'Point') and target.parent.kind == 'Points':
                target = target.parent.parent
                if target.scalar('Type') not in ('Polyline', 'Polygon'):
                    raise ReferenceError(f'{role}: point target requires a polyline or polygon')
            if owner is None or target.parent is not owner:
                raise ReferenceError(f'{role}: target is outside its local '+
                                     ('sheet settings' if role == 'xml-active-sheet' else 'title block' if role == 'xml-title-field' else 'symbol' if role == 'xml-symbol-group' else 'footprint')+f' at {reference.source.path}')
