"""Verified import normalization over owned route geometry and identities."""
from fractions import Fraction
from decimal import Decimal
from collections import defaultdict, deque

from .model import Element, Value
from .references import Segment
from .asc_policy import calculation_number
from .conversion import import_notice


def _defer(document, message):
    message = 'Route normalization deferred: '+message
    if message not in document.diagnostics:
        document.diagnostics.append(message)
    import_notice('warning', 'route-normalization-deferred', message,
                  recoverability='source geometry and unresolved constraints retained')


def _enabled_net(line):
    return line.parent.parent.scalar('Enabled', True) in (True, 'Y')


def normalize_imported_routes(document):
    """Apply established loading rules independently of file format/version.

    Unknown attachment domains defer geometry changes. This is deliberately
    limited to verified conditions, rather than a complete routing engine.
    """
    if not document.select('/Schematic/Nets/Net/Lines/Line'):
        return 0
    from .schematic_refs import connectivity_mismatches
    from .references import ReferenceError
    mismatches = connectivity_mismatches(document)
    domains = [node for net in document.select('/Schematic/Nets/Net')
               for node in (net.child('Lines'), *net.select('Lines/Line/Points')) if node is not None]
    try:
        document.references._check_collection_changes(domains)
    except ReferenceError:
        blocked = True
    else:
        blocked = False
    if blocked or mismatches:
        _defer(document, f'{len(document.references.issues)} unresolved references and '
                         f'{len(mismatches)} inconsistent memberships')
        return 0
    from .schematic_edit import coalesce_routes
    changed = len(upgrade_overlapping_junctions(document))
    changed += len(upgrade_short_junctions(document))
    changed += len(coalesce_routes(document, enabled_only=True))
    changed += len(upgrade_redundant_route_handles(document))
    changed += upgrade_short_route_axes(document)
    if changed:
        import_notice('info', 'route-modernization',
                      'Normalized route directions, redundant handles and established wire attachments',
                      document.select('/Schematic/Nets'), recoverability='current geometry and identity links are authoritative')
    return changed


def upgrade_redundant_route_handles(document):
    """Drop coincident interior handles with a consistent straight-axis hint.

    Keep endpoint direction changes, marked handles and referenced identities.
    A coincident direction hint can move onto a retained segment anchor instead
    of deleting that anchor and repairing its incoming references.
    This narrowly simplifies zero-length segments; it does not reroute bends or
    remove ordinary collinear vertices. Return removed points to the caller.
    """
    from .schematic_edit import RemovedRoutePoint, _referenced_route_points
    protected = _referenced_route_points(document.references)
    direct = _referenced_route_points(document.references, segment_targets=False)
    removed = []
    flags = {}
    for line in document.select('/Schematic/Nets/Net/Lines/Line'):
        if not _enabled_net(line):
            continue
        points = line.select('Points/pt')
        positions = {point: index for index, point in enumerate(points)}
        index = 1
        while index < len(points)-1:
            before, current, after = points[index-1:index+2]
            axis = flags.get(current, current.arguments[2]).value
            coincident = (before.values[:2] == current.values[:2]
                          or current.values[:2] == after.values[:2])
            straight = (axis in (0, 1) and axis == flags.get(after, after.arguments[2]).value
                        and before.values[1-axis] == after.values[1-axis]
                        and before.values[axis] != after.values[axis])
            entry_hint = (index == 1 and before.values[:2] == current.values[:2]
                          and flags.get(before, before.arguments[2]).value != axis)
            if coincident and straight and not entry_hint and current not in protected:
                removed.append(RemovedRoutePoint(line, current, positions[current]))
                points.pop(index)
            elif (coincident and straight and index > 1 and current in protected and current not in direct
                  and before not in protected and before.values[:2] == current.values[:2]
                  and flags.get(before, before.arguments[2]).value == 1-axis):
                flags[current] = flags.get(before, before.arguments[2])
                removed.append(RemovedRoutePoint(line, before, positions[before]))
                points.pop(index-1)
                index -= 1
            else:
                index += 1
    document.references._check_collection_changes(item.point.parent for item in removed)
    for point, flag in flags.items():
        point.set_argument(2, flag)
    for item in removed:
        item.point.detach()
    if removed:
        document.rebuild()
    return tuple(removed)


def refresh_segment_axes(line):
    """Classify each incoming segment by its larger coordinate displacement.

    Equal displacements, including a zero-length handle, use the horizontal
    flag. The first point has no incoming segment and keeps its stored flag.
    """
    points = line.select('Points/pt')
    changes = []
    for previous, current in zip(points, points[1:]):
        dx = calculation_number(current)-calculation_number(previous)
        dy = calculation_number(current, 1)-calculation_number(previous, 1)
        axis = int(abs(dy) > abs(dx))
        if current.values[2] != axis:
            changes.append((current, axis))
    if changes:
        for point, axis in changes:
            point.set_argument(2, axis)
    return bool(changes)


def upgrade_short_route_axes(document):
    """Normalize two-point routes with pin or disconnected endpoints.

    Longer routes can retain endpoint direction hints after the format cleanup
    step. They require their attachment rules, rather than global reflagging.
    """
    changed = 0
    for line in document.select('/Schematic/Nets/Net/Lines/Line'):
        if not _enabled_net(line):
            continue
        points = line.select('Points/pt')
        if len(points) == 2 and all(line.scalar('ConnectMode'+str(side)) in (-1,0,4) for side in (1,2)):
            changed += refresh_segment_axes(line)
    return changed


def _coherent_pin_endpoint(graph, line, side, point):
    links = graph.outgoing(line, role='wire-pin-'+str(side+1))
    if len(links) != 1:
        return False
    pin = links[0].target
    part = pin.parent.parent
    orientation = pin.scalar('Orientation')
    if (pin.scalar('Enabled', True) in (False, 'N') or part.scalar('Enabled', True) in (False, 'N')
            or isinstance(orientation, bool) or orientation not in (0, 1, 2, 3) or len(pin.arguments) != 3):
        return False
    # Pin coordinates and orientation are already placed. Compare the exact
    # stored physical facts; do not infer snapping for an inconsistent endpoint.
    direction = ((-1, 0), (0, -1), (1, 0), (0, 1))[int(orientation)]
    tip = tuple(Fraction(str(part.scalar(axis)))+Fraction(str(pin.values[index+1]))
                + Fraction(str(pin.scalar('Length')))*direction[index]
                for index, axis in enumerate(('X', 'Y')))
    return tip == tuple(Fraction(str(value)) for value in point.values[:2])


def upgrade_short_junctions(document):
    """Orthogonalize a short branch on a straight segment of its host route.

    Keep physical pin tips and endpoint identities. The incoming direction
    selects a bend or projection before direction cleanup. Outside projections
    use a dogleg; an overlapping lead departs from the adjacent host segment.
    """
    graph = document.references
    references = [r for r in graph if r.role in ('wire-segment-1','wire-segment-2')
                  and isinstance(r.target, Segment)]
    # A host must settle before its dependent branches. Cyclic attachment
    # constraints keep their source geometry rather than choosing a root.
    by_line = defaultdict(list)
    for reference in references:
        by_line[reference.source].append(reference)
    dependencies, following = {}, defaultdict(list)
    for line, links in by_line.items():
        hosts = {r.target.start.parent.parent for r in links} & by_line.keys()
        dependencies[line] = len(hosts)
        for host in hosts:
            following[host].append(line)
    ready = deque(line for line, count in dependencies.items() if not count)
    ordered = []
    while ready:
        line = ready.popleft()
        ordered.extend(by_line[line])
        for child in following[line]:
            dependencies[child] -= 1
            if not dependencies[child]:
                ready.append(child)
    if len(ordered) < len(references):
        _defer(document, 'cyclic wire attachments')
    # Preflight every possibly affected collection before applying geometry.
    graph._check_collection_changes(r.source.one('Points') for r in ordered)
    changed = []
    for original in ordered:
        reference = graph.get(original.uid)
        if reference.role not in ('wire-segment-1', 'wire-segment-2') or not isinstance(reference.target, Segment):
            continue
        line, segment = reference.source, reference.target
        if not _enabled_net(line):
            continue
        side = int(reference.role[-1])-1
        endpoint = line.scalar('ConnectMode'+str(2-side))
        if line.scalar('Enabled', True) in (False, 'N') or endpoint not in (-1, 0, 4):
            continue
        points = line.select('Points/pt')
        host = segment.start.parent.children('pt')
        owner = segment.start.parent.parent
        if len(points) != 2 or owner.scalar('Enabled', True) in (False, 'N'):
            continue
        if any(owner.scalar('ConnectMode'+str(end)) == 0 and
               not _coherent_pin_endpoint(graph, owner, end-1, host[0 if end == 1 else -1])
               for end in (1, 2)):
            _defer(document, 'host pin endpoint needs resolution')
            continue
        first, last = (point.values[:2] for point in (segment.start, segment.end))
        join_xy, free_xy = points[side].values[:2], points[1-side].values[:2]
        if first == last or not (first[0] == last[0] or first[1] == last[1]) or join_xy == free_xy:
            continue
        axis = int(first[0] == last[0])
        normal = 1-axis
        if (segment.end.values[2] != axis or join_xy[normal] != first[normal]
                or not min(first[axis], last[axis]) <= join_xy[axis] <= max(first[axis], last[axis])):
            continue
        direction = points[-1].values[2]
        if direction not in (0, 1):
            # Compatibility directions have no established orthogonal intent.
            if join_xy[0] != free_xy[0] and join_xy[1] != free_xy[1]:
                _defer(document, 'branch has a compatibility direction without established orthogonal intent')
            continue
        if endpoint == 0:
            if not _coherent_pin_endpoint(graph, line, 1-side, points[1-side]):
                _defer(document, 'branch pin endpoint needs resolution')
                continue
        coordinates = _branch_path(join_xy, free_xy, first, last, axis, direction, endpoint == 0)
        coordinates, target = _trim_host_overlap(coordinates, host, segment)
        if side:
            coordinates.reverse()
        values = []
        for position in coordinates:
            flag = points[0].values[2] if not values else int(position[0] == values[-1][0])
            values.append((*position, flag))
        if len(values) == len(points) and target == segment and all(tuple(row) == point.values
                                                                   for row, point in zip(values, points)):
            continue
        dependents = []
        blocked = False
        for incoming in graph.incoming(points[0])+graph.incoming(points[-1]):
            if incoming in dependents:
                continue
            if isinstance(incoming.target, Segment):
                child_points = incoming.source.select('Points/pt')
                if incoming.role not in ('wire-segment-1','wire-segment-2') or len(child_points) != 2:
                    blocked = True
                    break
                child_side = int(incoming.role[-1])-1
                child_mode = incoming.source.scalar('ConnectMode'+str(2-child_side))
                if (child_points[-1].values[2] not in (0,1) or child_mode not in (-1,0,4)
                        or child_mode == 0 and not _coherent_pin_endpoint(
                            graph,incoming.source,1-child_side,child_points[1-child_side])):
                    blocked = True
                    break
                dependents.append(incoming)
            elif incoming.role != 'selected-wire-point':
                blocked = True
                break
        if blocked:
            _defer(document, 'unsupported dependent geometry')
            continue
        if target != reference.target:
            graph.retarget(reference, target)
        points[0].set_values(*values[0])
        points[-1].set_values(*values[-1])
        for index, row in enumerate(values[1:-1], 1):
            line.one('Points').insert(Element('pt', *row), index)
        current = line.select('Points/pt')
        # Keep the nearest physical attachment when a formerly straight host
        # acquires bends. The dependent's own direction/pin rule runs next.
        # This uses settled geometry and is independent of line-array order.
        for incoming in dependents:
            child = incoming.source.select('Points/pt')
            end = int(incoming.role[-1])-1
            point = child[0 if end == 0 else -1]
            candidates = []
            for index, (a_node,b_node) in enumerate(zip(current,current[1:])):
                a, b = a_node.values[:2], b_node.values[:2]
                axis = int(a[0] == b[0])
                position = list(point.values[:2])
                position[1-axis] = a[1-axis]
                position[axis] = min(max(a[axis],b[axis]), max(min(a[axis],b[axis]), position[axis]))
                distance = sum((Fraction(str(x))-Fraction(str(y)))**2
                               for x,y in zip(position,point.values[:2]))
                candidates.append((distance,index,position,Segment(a_node,b_node)))
            _, _, position, new_target = min(candidates, key=lambda row: row[:2])
            graph.retarget(incoming, new_target)
            point.set_values(*position, point.arguments[2])
        changed.append(line)
    if changed:
        document.rebuild()
    return tuple(changed)


def _branch_path(joined, free, first, last, axis, direction, pinned):
    bend = tuple(joined[i] if i == axis else free[i] for i in (0, 1))
    if direction == axis:
        # Preserve an authored free lead too: collapsing it would erase wire
        # coverage. A pin is a fixed physical fact regardless of its distance.
        return [joined, bend, free]
    if not pinned:
        return [joined, bend]
    low, high = sorted((first[axis], last[axis]))
    along = min(high, max(low, free[axis]))
    junction = tuple(along if i == axis else joined[i] for i in (0, 1))
    if along == free[axis]:
        return [junction, free]
    middle = (Decimal(str(joined[1-axis]))+Decimal(str(free[1-axis])))/2
    return [junction, tuple(along if i == axis else middle for i in (0, 1)),
            tuple(free[i] if i == axis else middle for i in (0, 1)), free]


def _trim_host_overlap(coordinates, host, segment):
    """Follow a contiguous overlapping lead to its physical departure point."""
    coordinates = list(coordinates)
    corner = host.index(segment.end)
    while len(coordinates) > 1:
        start, end = coordinates[:2]
        if start == end:
            coordinates.pop(0)
            continue
        for candidate in (corner, corner-1, corner+1):
            if not 1 <= candidate < len(host):
                continue
            a, b = (p.values[:2] for p in host[candidate-1:candidate+1])
            axis = int(a[0] == b[0])
            if (a == b or a[1-axis] != b[1-axis] or start[1-axis] != a[1-axis]
                    or end[1-axis] != a[1-axis] or
                    not min(a[axis],b[axis]) <= start[axis] <= max(a[axis],b[axis])):
                continue
            next_xy = list(start)
            next_xy[axis] = min(max(a[axis],b[axis]), max(min(a[axis],b[axis]), end[axis]))
            next_xy = tuple(next_xy)
            if next_xy != start:
                coordinates[0] = next_xy
                corner = candidate
                break
        else:
            break
    coordinates = [xy for i, xy in enumerate(coordinates) if not i or xy != coordinates[i-1]]
    if len(coordinates) == 1:
        coordinates *= 2
    return coordinates, Segment(host[corner-1], host[corner])


def upgrade_overlapping_junctions(document):
    """Move a redundant straight lead to the preceding corner of its host wire.

    This handles the old three-point pin-to-wire representation. Restrict the
    upgrade to an isolated leading handle; other routes remain ordinary source
    data until their corresponding format conversion is established.
    """
    changed=[]
    graph=document.references
    for reference in list(graph):
        line=reference.source
        if reference.role!='wire-segment-1' or line.scalar('ConnectMode2')!=0:
            continue
        points=line.select('Points/pt')
        if len(points)!=3 or points[0].values!=points[1].values or points[0].values[2]!=0:
            continue
        segment=reference.target
        if not isinstance(segment,Segment):
            continue
        host=segment.start.parent.children('pt')
        corner=host.index(segment.start)
        if corner==0 or segment.end.values[:2]!=points[0].values[:2]:
            continue
        start=tuple(map(Fraction,points[0].values[:2]))
        end=tuple(map(Fraction,points[-1].values[:2]))
        junction=tuple(map(Fraction,segment.start.values[:2]))
        direction=tuple(b-a for a,b in zip(start,end))
        advance=tuple(b-a for a,b in zip(start,junction))
        if direction[0] and direction[1]:
            continue
        axis=int(direction[0]==0)
        if points[-1].values[2]!=axis:
            continue
        if (direction[0]*advance[1]!=direction[1]*advance[0] or
                not 0<sum(a*b for a,b in zip(direction,advance))<sum(a*a for a in direction)):
            continue
        moved=set(points[:2])
        attached=False
        for incoming in graph:
            target=incoming.target
            targets=(target.start,target.end) if isinstance(target,Segment) else (target,)
            if any(t in moved for t in targets) and (incoming.role!='selected-wire-point'
                                                     or (axis==0 and points[1] in targets)):
                attached=True
                break
        if attached:
            continue
        graph.retarget(reference,Segment(host[corner-1],host[corner]))
        coordinates=segment.start.values[:2]
        points[0].set_values(*coordinates,0)
        if axis:
            points[1].set_values(*coordinates,axis)
        else:
            points[1].detach()
        changed.append(line)
    return tuple(changed)
