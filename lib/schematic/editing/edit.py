"""Schematic editing operations expressed through our elements and references."""
from dataclasses import dataclass
from itertools import groupby

from ...common.model import (Element)
from ...common.references import (Segment)


@dataclass(frozen=True)
class RemovedRoutePoint:
    line: Element
    point: Element
    position: int


def _referenced_route_points(graph, *, segment_targets=True):
    """Collect point identities used by links, guards and positional fields."""
    protected = set()

    def protect(node):
        while node is not None:
            if node.parent and node.parent.kind == 'Points':
                protected.add(node)
                return
            node = node.parent

    for reference in graph:
        protect(reference.source)
        if isinstance(reference.target, Segment):
            if segment_targets:
                protect(reference.target.start)
                protect(reference.target.end)
        else:
            protect(reference.target)
        for index in reference.indices:
            protect(index.field)
        for guard in reference.guards:
            protect(guard.field)
    for issue in graph.issues:
        protect(issue.source)
        for index in issue.indices:
            protect(index.field)
    return protected


def coalesce_routes(document, *, enabled_only=False):
    """Remove excess coincident route points, retaining connection anchors.

    Two coincident points can encode the entry and exit of a route handle.
    Additional unmarked copies carry no geometry. Preserve marked points, route
    endpoints and every referenced point; identity links then supply new indices.
    Return detached points and their original positions for inspection or undo.
    enabled_only restricts the operation to enabled nets during import.
    Unresolved links in unrelated domains remain intact. A related or unknown
    reference domain blocks the planned removals before any point is detached.
    """
    graph = document.references
    document.rebuild(force=False)
    protected = _referenced_route_points(graph)

    removed = []
    for line in document.select('/Schematic/Nets/Net/Lines/Line'):
        if enabled_only and line.parent.parent.scalar('Enabled', True) not in (True, 'Y'):
            continue
        geometry = line.child('Points')
        if geometry is None:
            continue
        points = geometry.children('pt')
        if not points:
            continue
        protected.update((points[0], points[-1]))
        for _, run in groupby(enumerate(points), key=lambda row: row[1].values[:2]):
            run = list(run)
            if len(run) < 3:
                continue
            keep = {point for _, point in run
                    if point in protected or len(point.values) != 3 or point.values[2] != 0}
            # Fill the two handle positions in source order, without dropping
            # any marked or referenced point when there are more than two.
            for _, point in run:
                if len(keep) >= 2:
                    break
                keep.add(point)
            for position, point in run:
                if point not in keep:
                    removed.append(RemovedRoutePoint(line, point, position))
    graph._check_collection_changes(item.point.parent for item in removed)
    for item in removed:
        item.point.detach()
    document.rebuild()
    return tuple(removed)
