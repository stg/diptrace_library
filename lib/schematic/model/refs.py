"""Translate schematic index fields into our identity-based reference graph.

This is a boundary adapter over public fields. Component pins and wire segments
become targets; their containing array positions are projections of those targets.
"""
from ...common.references import (Guard, Index, Property, ReferenceError, Segment)
from ...common.structural_edits import assembling
from ...common.indexing import at as _at, integer as _integer
from .reference_scope import select as source_records, OrdinalLookup


REFERENCE_COLLECTIONS = frozenset(('Components', 'Pins', 'Nets', 'Lines', 'Points', 'Pages', 'Buses',
    'PageConnectors', 'NetClasses', 'Pads', 'Shapes', 'Holes', 'Dimensions', 'Slots', 'DesignCache_Links',
    'Groups', 'Pattern_Groups', 'Contents', 'signals', 'UserFields'))


def _children(parent, field, kind):
    node = parent.child(field) if parent else None
    return node._child_sequence(kind) if node else ()


def _number_keys(records):
    """Imported Number fields are keys and can have gaps after deletion.

    Targets still project to current array positions during rebuild. Refuse an
    ambiguous stored key; only a collection with no Number fields at all uses
    positional input (useful for newly authored minimal documents).
    """
    if not any(record.child('Number') is not None for record in records):
        return dict(enumerate(records))
    result = {}
    for record in records:
        number = _integer(record.scalar('Number'))
        if number is not None and number >= 0:
            result[number] = record if number not in result else None
    return result


def _field(node, name, ancestor=0):
    field = node.child(name)
    return Index(field, ancestor=ancestor) if field and len(field.values) == 1 else None


def _segment(net, line, point, *, clamp=False, lookup=_number_keys):
    route = lookup(_children(net, 'Lines', 'Line')).get(_integer(line))
    points = _children(route, 'Points', 'pt')
    if clamp and point is not None and len(points) >= 2:
        point = min(len(points)-1, max(1, point))
    end = _at(points, point) if point is not None and point > 0 else None
    return Segment(points[point-1], end) if end else None


def _specifications(document, *, clamp_segments=False, scope=None):
    for specification in _reference_specifications(document, clamp_segments=clamp_segments, scope=scope):
        if scope is None or scope.affects(specification):
            yield specification


def _reference_specifications(document, *, clamp_segments=False, scope=None):
    from .membership import MEMBER, NET_NUMBER
    from .definitions import has_derived_index
    schematics = document.root.children('Schematic')
    if len(schematics) != 1:
        return
    schematic = schematics[0]
    parts = _children(schematic, 'Components', 'Part')
    nets = _children(schematic, 'Nets', 'Net')
    buses = _children(schematic, 'Buses', 'Bus')
    connectors = _children(schematic, 'PageConnectors', 'PageConnector')
    lookup = OrdinalLookup if scope is not None else _number_keys
    net_numbers = lookup(nets)
    part_numbers = lookup(parts)
    bus_numbers = lookup(buses)
    connector_numbers = lookup(connectors)
    connector_attachments = {}
    for bus in source_records(schematic, 'Buses/Bus', scope):
        for line in source_records(bus, 'Lines/Line', scope):
            for suffix in ('1', '2'):
                if _integer(line.scalar('ConnectMode'+suffix)) == 4:
                    connector = connector_numbers.get(_integer(line.scalar('Connect'+suffix)))
                    if connector is not None:
                        connector_attachments.setdefault(connector, set()).add(bus)
                        if scope is not None:
                            scope.include_reference(connector, 'bus-connector-owner')

    def part_target(number):
        return part_numbers.get(_integer(number))

    def net_target(number):
        return net_numbers.get(_integer(number))
    pages = _children(schematic, 'Pages', 'Page')
    classes = _children(schematic, 'NetClasses', 'NetClass')

    def scalar(source, name, target, role):
        slot = _field(source, name)
        if slot:
            yield source, target, role, (slot,), ()

    def optional(source, name, choices, role, lookup=None):
        value = _integer(source.scalar(name))
        if value is not None and value >= 0:
            yield from scalar(source, name, lookup(value) if lookup else _at(choices, value), role)

    def selection(owner, lines):
        selected = lookup(lines).get(_integer(owner.scalar('ActiveLine')))
        point = _at(_children(selected, 'Points', 'pt'), owner.scalar('ActivePoint'))
        if point:
            yield owner, point, 'selected-wire-point', (
                _field(owner, 'ActiveLine', 2), _field(owner, 'ActivePoint')), ()
        elif selected:
            yield from scalar(owner, 'ActiveLine', selected, 'selected-wire')

    def segment_slots(line, suffix):
        return (_field(line, 'Connect'+suffix, 2), _field(line, 'ConnectL'+suffix),
                _field(line, 'ConnectB'+suffix, 4))

    def hierarchy_links(part):
        if part is None or part.scalar('Enabled') not in (True, 'Y') or part.scalar('PartType') != 4:
            return
        if scope is not None and any(part.child(name) in scope.nodes for name in ('PartType', 'Enabled')):
            scope.include_children(part, 'Pins/Pin')
            scope.include_reference(part, 'hierarchy-page')
            scope.include_reference(part, 'component-pin-reference')
        guard = (Guard(part.one('PartType'), part.one('PartType').values),)
        destination = part.child('Number1')
        if destination is not None and _integer(part.scalar('Number1')) is not None and part.scalar('Number1') >= 0:
            page = _at(pages, part.scalar('Number1'))
            slots = [Index(destination)]
            hidden = part.child('PageHiddenId')
            if hidden is not None and page is not None and hidden.values == page.one('PageHiddenId').values:
                slots.append(Property(hidden, 'PageHiddenId'))
            yield part, page, 'hierarchy-page', tuple(slots), guard
        for pin in source_records(part, 'Pins/Pin', scope):
            if pin.scalar('Enabled') in (True, 'Y'):
                # Saved Number values are component keys, with possible gaps.
                # StringNumber redundantly names the connector's RefDes. The
                # format loader maps these to runtime positions; our graph
                # resolves the saved identity without changing its source value.
                field = pin.child('Number')
                signature = pin.child('StringNumber')
                number = _integer(pin.scalar('Number'))
                if field and signature and number is not None and number >= 0:
                    target = part_target(number)
                    if target is None or target.scalar('PartType') != 3 or len(target.values) < 2 or target.values[1] != pin.scalar('StringNumber'):
                        target = None
                    yield part, target, 'component-pin-reference', (Index(field), Property(signature, target_argument=1)), guard

    for part in source_records(schematic, 'Components/Part', scope):
        yield from scalar(part, 'Number', part, 'component-order')
        yield from optional(part, 'Page', pages, 'component-page')
        for pin in source_records(part, 'Pins/Pin', scope):
            if pin.values and not has_derived_index(pin):
                yield pin, pin, 'pin-order', (Index(pin),), ()
            if pin.child('NetNumber') is not None and pin.one('NetNumber').schema is not NET_NUMBER:
                yield from optional(pin, 'NetNumber', nets, 'pin-net', lookup=net_target)
        yield from hierarchy_links(part)
    for definition in source_records(schematic, 'CacheLib/Slots/Slot/Definition', scope):
        yield from hierarchy_links(definition.one('Part') if scope is None else definition.child('Part'))

    for net in source_records(schematic, 'Nets/Net', scope):
        yield from scalar(net, 'Number', net, 'net-order')
        yield from optional(net, 'NetClass', classes, 'net-class')
        for member in source_records(net, 'Parts/pt', scope):
            if member.schema is MEMBER:
                if scope is None and len(document.references.outgoing(member, role='net-member')) != 1:
                    raise ReferenceError('net member is missing its pin identity; clone linked data through its document')
                continue
            if len(member.values) < 2:
                continue
            part = part_target(member.values[0])
            pin = _at(_children(part, 'Pins', 'Pin'), member.values[1])
            yield member, pin, 'net-member', (Index(member, 0, 2), Index(member, 1)), ()
        lines = _children(net, 'Lines', 'Line')
        yield from selection(net, lines)
        for line in source_records(net, 'Lines/Line', scope):
            yield from scalar(line, 'Number', line, 'wire-order')
            yield from scalar(line, 'NetNumber', net, 'wire-net')
            yield from optional(line, 'Page', pages, 'wire-page')
            for side in (1, 2):
                suffix = str(side)
                mode = _integer(line.scalar('ConnectMode'+suffix))
                if mode is None or mode < 0 or mode == 4:
                    continue  # Disconnected endpoints retain their unused fields.
                guard = Guard(line.child('ConnectMode'+suffix), (mode,))
                if mode == 0:
                    part = part_target(line.scalar('Connect'+suffix))
                    target = _at(_children(part, 'Pins', 'Pin'), line.scalar('ConnectL'+suffix))
                    slots = (_field(line, 'Connect'+suffix, 2), _field(line, 'ConnectL'+suffix))
                    yield line, target, 'wire-pin-'+suffix, slots, (guard,)
                elif mode == 1:
                    # Wire joins are local to the containing net. ConnectB is
                    # a redundant occurrence, preserved until index rebuilding.
                    target = _segment(net, line.scalar('Connect'+suffix), _integer(line.scalar('ConnectL'+suffix)),
                                      clamp=clamp_segments, lookup=lookup)
                    if target and target.start.parent.parent is line:
                        target = None
                    yield line, target, 'wire-segment-'+suffix, segment_slots(line, suffix), (guard,)
                elif mode == 3:
                    bus = bus_numbers.get(_integer(line.scalar('ConnectB'+suffix)))
                    target = _segment(bus, line.scalar('Connect'+suffix), _integer(line.scalar('ConnectL'+suffix)),
                                      clamp=clamp_segments, lookup=lookup)
                    yield line, target, 'wire-bus-segment-'+suffix, segment_slots(line, suffix), (guard,)
                else:
                    slots = tuple(_field(line, name+suffix) for name in ('Connect', 'ConnectL', 'ConnectB'))
                    yield line, None, 'unmapped-wire-mode-'+str(mode), slots, (guard,)
    for source in (*source_records(schematic, 'Shapes/Shape', scope), *source_records(schematic, 'Tables/Table', scope),
                   *source_records(schematic, 'PageConnectors/PageConnector', scope)):
        yield from optional(source, 'Page', pages, 'drawing-page')
    for drawing in source_records(schematic, 'Shapes/Shape', scope):
        if drawing.scalar('Type') == 10:
            guard = Guard(drawing.one('Type'), drawing.one('Type').values)
            for name, targets, role in (('RelatedNet', net_numbers, 'drawing-net-name'),
                                         ('RelatedBus', bus_numbers, 'drawing-bus-name')):
                number = _integer(drawing.scalar(name))
                if number is not None and number >= 0:
                    yield drawing, targets.get(number), role, (_field(drawing, name),), (guard,)
    selected_connectors = tuple(dict.fromkeys((*source_records(schematic, 'PageConnectors/PageConnector', scope),
                                              *connector_attachments)))
    for connector in selected_connectors:
        yield from scalar(connector, 'Number', connector, 'bus-connector-order')
        slot = _field(connector, 'BusNumber')
        owners = connector_attachments.get(connector, set())
        if scope is not None:
            owners = owners | {reference.source.parent.parent for reference in document.references.incoming(connector)
                               if reference.role.startswith('bus-wire-connector-')}
        if slot and owners:
            # The reverse BusNumber cache can be -1 or stale in real files.
            # Resolve the explicit bus-wire attachment first, without changing
            # that stored occurrence. An ambiguous owner is never guessed.
            target = next(iter(owners)) if len(owners) == 1 else None
            yield connector, target, 'bus-connector-owner', (slot,), ()
        elif slot and connector.scalar('Connected') in (True, 'Y'):
            number = _integer(connector.scalar('BusNumber'))
            if number is not None and number >= 0:
                guard = Guard(connector.child('Connected'), connector.child('Connected').values)
                yield connector, bus_numbers.get(number), 'bus-connector-owner', (slot,), (guard,)
    for bus in source_records(schematic, 'Buses/Bus', scope):
        yield from scalar(bus, 'Number', bus, 'bus-order')
        for member in source_records(bus, 'Nets/pt', scope):
            if member.values:
                yield member, net_target(member.values[0]), 'bus-net', (Index(member),), ()
        lines = _children(bus, 'Lines', 'Line')
        yield from selection(bus, lines)
        for line in source_records(bus, 'Lines/Line', scope):
            yield from scalar(line, 'Number', line, 'bus-wire-order')
            yield from scalar(line, 'BusNumber', bus, 'bus-wire-owner')
            yield from optional(line, 'Page', pages, 'bus-wire-page')
            for side in (1, 2):
                suffix = str(side)
                mode = _integer(line.scalar('ConnectMode'+suffix))
                if mode is None or mode < 0 or mode in (0, 1, 5):
                    continue  # XML names these bus endpoint modes Free.
                guard = Guard(line.child('ConnectMode'+suffix), (mode,))
                if mode == 2:
                    target = _segment(bus, line.scalar('Connect'+suffix), _integer(line.scalar('ConnectL'+suffix)),
                                      clamp=clamp_segments, lookup=lookup)
                    yield line, target, 'bus-wire-segment-'+suffix, segment_slots(line, suffix), (guard,)
                elif mode == 4:
                    target = connector_numbers.get(_integer(line.scalar('Connect'+suffix)))
                    yield line, target, 'bus-wire-connector-'+suffix, (_field(line, 'Connect'+suffix),), (guard,)
                else:
                    slots = tuple(_field(line, name+suffix) for name in ('Connect', 'ConnectL', 'ConnectB'))
                    yield line, None, 'unmapped-bus-mode-'+str(mode), slots, (guard,)
    from .pattern_refs import (specifications as pattern_specifications)
    yield from pattern_specifications(document, scope=scope)
    from ...common.cache_refs import specifications as cache_specifications
    if document.representation == 'schematic':
        yield from cache_specifications(schematic, scope=scope)
    from .data_refs import (specifications as data_specifications)
    yield from data_specifications(document, scope=scope)
    from .simulation_refs import (specifications as simulation_specifications)
    yield from simulation_specifications(document, scope=scope)


def reference_collections(document, source, role, *, authoring=False):
    from .pattern_refs import (issue_collections as pattern_scopes)
    from ...common.cache_refs import issue_collections as cache_scopes
    from .data_refs import (issue_collections as data_scopes)
    from .simulation_refs import (collections as simulation_scopes)

    def route_collections(owner):
        lines = owner.child('Lines') if owner is not None else None
        if lines is None:
            return ()
        return (lines, *(points for line in lines.children('Line')
                         if (points := line.child('Points')) is not None))

    if role.startswith(('wire-segment-', 'bus-wire-segment-')):
        return route_collections(source.parent.parent) or None
    if role.startswith('wire-bus-segment-'):
        schematic = document.one('/Schematic')
        buses = schematic.child('Buses')
        if buses is None:
            return None
        suffix = role[-1]
        lookup = OrdinalLookup if authoring else _number_keys
        owner = lookup(buses._child_sequence('Bus')).get(_integer(source.scalar('ConnectB'+suffix)))
        return (buses, *route_collections(owner))
    if role == 'component-pin-reference':
        return (document.one('/Schematic/Components'),)
    if role in ('pin-net', 'bus-net'):
        return (document.one('/Schematic/Nets'),)
    if role == 'net-member':
        components = document.one('/Schematic/Components')
        lookup = OrdinalLookup if authoring else _number_keys
        number = _integer(source.values[0]) if source.values else None
        part = lookup(components._child_sequence('Part')).get(number)
        pins = part.child('Pins') if part is not None else None
        return (components, pins) if pins is not None else (components,)
    if role in ('component-page', 'drawing-page', 'wire-page', 'bus-wire-page'):
        return (document.one('/Schematic/Pages'),)
    if role == 'net-class':
        return (document.one('/Schematic/NetClasses'),)
    if role == 'hierarchy-page':
        owner = document.one('/Schematic').child('Pages')
        return (owner,) if owner is not None else None
    if role in ('drawing-net-name', 'drawing-bus-name'):
        owner = source.parent.parent.child('Nets' if role == 'drawing-net-name' else 'Buses')
        return (owner,) if owner is not None else None
    return simulation_scopes(source, role) or cache_scopes(source, role) or pattern_scopes(source, role) or data_scopes(source, role)


@assembling
def bind_schematic_references(document, *, clamp_segments=False):
    from .definitions import establish
    establish(document)
    source = document.root.child('Source')
    if document.representation != 'schematic' and (
            not source or not source.values or source.values[0] != 'DipTrace-Schematic'):
        return
    graph = document.references
    with graph.binding_batch():
        for source, target, role, indices, guards in _specifications(document, clamp_segments=clamp_segments):
            if any(i is None for i in indices):
                continue
            if all(graph.manages(i.field, i.argument) for i in indices):
                continue
            # Import binding is not an explicit resolution of an existing
            # missing identity. A new record at the old literal index must not
            # silently become its target during a later binding pass.
            if any(graph.unresolved_slot(i.field, i.argument) for i in indices):
                continue
            if target is None:
                if not all(graph.unresolved_slot(i.field, i.argument) for i in indices):
                    graph.note(source, f'{role}: target index cannot be resolved', *indices,
                               collections=reference_collections(document, source, role), guards=guards)
            else:
                try:
                    graph.bind(source, target, *indices, role=role, guards=guards, preserve=True)
                except ReferenceError as error:
                    graph.note(source, str(error), *indices, collections=reference_collections(document, source, role), guards=guards)
    for node in document.root.walk():
        if node.kind in REFERENCE_COLLECTIONS:
            graph.watch(node)
    document._reference_validator = validate_schematic_references
    from .membership import consolidate
    consolidate(document)


def validate_schematic_references(document):
    # Resolve only to describe the expected slots. Existing targets continue to
    # come from the graph, including while their old indices await rebuilding.
    graph = document.references
    for source, target, role, indices, guards in _specifications(document):
        for item in indices:
            if item and not graph.manages(item.field, item.argument) and not graph.unresolved_slot(item.field, item.argument):
                raise ReferenceError(f'{role}: new reference needs an explicit binding')
    mismatches = connectivity_mismatches(document)
    if mismatches:
        raise_connectivity_mismatch(*mismatches[0])


def raise_connectivity_mismatch(source, role):
    if role in ('symbol-pin-pad', 'pattern-shape-pad') or role.startswith(('pattern-dimension-', 'pattern-internal-pad-')):
        raise ReferenceError(f'{role}: target is outside its local footprint at {source.path}')
    if role == 'design-cache-slot':
        raise ReferenceError(f'{role}: target is outside its design cache at {source.path}')
    if role in ('drawing-net-name', 'drawing-bus-name') or role.startswith('simulation-'):
        raise ReferenceError(f'{role}: target is outside its schematic collection at {source.path}')
    if role in ('schematic-group', 'title-cell-field', 'pattern-group', 'symbol-group', 'marking-user-field') or role.startswith('differential-'):
        raise ReferenceError(f'{role}: target is outside its local collection at {source.path}')
    raise ReferenceError(f'{role}: net membership disagrees at {source.path}')


def connectivity_mismatches(document, *, references=None):
    """Inspect reciprocal membership and wire attachments by identity."""
    def ancestor(node, depth):
        for _ in range(depth):
            node = node.parent if node is not None else None
        return node

    graph = document.references
    references = tuple(graph) if references is None else references
    pins = {r.target for r in references if r.role == 'net-member' or r.role.startswith('wire-pin-')}
    from .membership import get_net
    assignments = {}
    for pin in pins:
        try:
            assignments[pin] = get_net(pin)
        except ReferenceError:
            assignments[pin] = None
    bus_members = {(ancestor(member.source, 2), member.target) for r in references
                   if r.role.startswith('wire-bus-segment-')
                   for member in graph.incoming(ancestor(r.source, 2), role='bus-net')}
    connector_owners = {r.target: link.target for r in references if r.role.startswith('bus-wire-connector-')
                        for link in graph.outgoing(r.target, role='bus-connector-owner')}
    issues = []
    pad_orders = {}
    from .simulation_refs import (valid_target as valid_simulation_target)
    from .pattern_refs import (valid_dimension_target)
    for reference in references:
        if reference.role == 'component-pin-reference':
            if (reference.target.parent is not document.one('/Schematic/Components') or
                    reference.target.scalar('PartType') != 3):
                issues.append((reference.source, reference.role))
        elif reference.role == 'hierarchy-page':
            if reference.target.parent is not document.one('/Schematic').child('Pages'):
                issues.append((reference.source, reference.role))
        elif reference.role.startswith('simulation-'):
            if not valid_simulation_target(reference):
                issues.append((reference.source, reference.role))
        elif reference.role in ('schematic-group', 'title-cell-field', 'pattern-group', 'symbol-group', 'marking-user-field') or reference.role.startswith('differential-'):
            from .data_refs import (local_collection)
            if reference.target.parent is not local_collection(reference.source, reference.role):
                issues.append((reference.source, reference.role))
        elif reference.role == 'symbol-pin-pad':
            pattern = reference.source.child('Pattern') or reference.source.parent.child('Pattern')
            pads = pattern.child('Pads') if pattern is not None else None
            if pads not in pad_orders:
                pad_orders[pads] = set(pads.children('Pad')[1:-1]) if pads is not None else set()
            if reference.target.parent is not pads or reference.target not in pad_orders[pads]:
                issues.append((reference.source, reference.role))
        elif reference.role == 'design-cache-slot':
            cache = reference.source.child('CacheLib')
            slots = cache.child('Slots') if cache is not None else None
            if reference.target.kind != 'Slot' or reference.target.parent is not slots:
                issues.append((reference.source, reference.role))
        elif reference.role in ('drawing-net-name', 'drawing-bus-name'):
            kind = 'Net' if reference.role == 'drawing-net-name' else 'Bus'
            owner = ancestor(reference.source, 2).child(kind+'s')
            if reference.target.kind != kind or reference.target.parent is not owner:
                issues.append((reference.source, reference.role))
        elif reference.role.startswith('pattern-dimension-'):
            if not valid_dimension_target(reference):
                issues.append((reference.source, reference.role))
        elif reference.role == 'pattern-shape-pad' or reference.role.startswith('pattern-internal-pad-'):
            if ancestor(reference.target, 2) is not ancestor(reference.source, 2):
                issues.append((reference.source, reference.role))
        elif reference.role == 'net-member' or reference.role.startswith('wire-pin-'):
            owner = ancestor(reference.source, 2)
            if assignments.get(reference.target) is not owner:
                issues.append((reference.source, reference.role))
        elif reference.role.startswith('wire-segment-'):
            owner = ancestor(reference.source, 2)
            target_net = ancestor(reference.target.start, 4)
            if target_net is not owner:
                issues.append((reference.source, reference.role))
        elif reference.role.startswith('wire-bus-segment-'):
            owner = ancestor(reference.source, 2)
            target_bus = ancestor(reference.target.start, 4)
            if (target_bus, owner) not in bus_members:
                issues.append((reference.source, reference.role))
        elif reference.role.startswith('bus-wire-segment-'):
            owner = ancestor(reference.source, 2)
            if ancestor(reference.target.start, 4) is not owner:
                issues.append((reference.source, reference.role))
        elif reference.role.startswith('bus-wire-connector-'):
            if connector_owners.get(reference.target) is not ancestor(reference.source, 2):
                issues.append((reference.source, reference.role))
    return issues


def unresolved_connectivity(document):
    """Footprint assignments do not prevent independent electrical upgrades."""
    return [issue for issue in document.references.issues
            if not issue.message.startswith(('symbol-pin-pad:', 'pattern-dimension-', 'pattern-shape-pad:', 'pattern-internal-pad-', 'design-cache-slot:',
                                             'schematic-group:', 'title-cell-field:', 'differential-', 'pattern-group:', 'symbol-group:', 'marking-user-field:', 'simulation-'))]
