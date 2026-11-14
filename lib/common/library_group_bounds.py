"""Current standalone group centres from membership and editable geometry.

Serialized group coordinates are calculated selection caches. They do not own
another position or preserve the geometry of an earlier import. Model access
uses the current library text profile; output calculations can supply a receiver
layout explicitly. Group identity and member identity remain independent of it.
"""
from .geometry import Bounds, circular_arc_bounds, stable_midpoint
from .footprint_bounds import physical_bounds
from .symbol_envelope import pin_bounds
from .text.vector_layout import pin_name_metrics


def members(group):
    document = group._owner()
    if document is None:
        return ()
    return tuple(dict.fromkeys(link.source for link in document.references.incoming(group)
        if link.source.kind in ('Pad', 'Shape', 'Hole', 'Dimension', 'Pin')
        and link.source.schema is not None and 'Group' in link.source.schema.fields
        and link.source['Group'] is group))


def _member_bounds(member, layout):
    if not member.get('Enabled', True):
        return None
    kind = member.kind
    if kind == 'Pad':
        return physical_bounds(pads=(member,))
    if kind == 'Hole':
        return physical_bounds(holes=((member['X'], member['Y'], member['Diam']),))
    if kind == 'Dimension':
        box = Bounds.from_points((member[x], member[y]) for x, y in
                                 (('X1', 'Y1'), ('X2', 'Y2'), ('XD', 'YD')))
        return Bounds(box.left-2, box.top-2, box.right+2, box.bottom+2)
    if kind == 'Pin':
        return pin_bounds(member, measure_name=lambda pin: pin_name_metrics(pin, font=layout.vector_metrics))
    if kind == 'Shape':
        physical = 'Layer' in member.schema.fields
        if member['Type'] == (7 if physical else 10):
            corners = layout.pattern_bounds(member) if physical else layout.symbol_bounds(member)
            return Bounds.from_points(corners)
        if physical:
            return physical_bounds(drawings=(member,))
        if member['Type'] <= 0:
            return None
        points = tuple(point.values for point in member.select('Points_New/pt'))
        return circular_arc_bounds(*points) if member['Type'] == 2 else Bounds.from_points(points)
    return None


def coordinates(group, *, layout=None):
    """Calculate a centre, using zero only when the group has no geometry."""
    from .library_versions import library_text_layout
    layout = layout if layout is not None else library_text_layout()
    box = None
    for member in members(group):
        current = _member_bounds(member, layout)
        if current is not None:
            box = current if box is None else box.union(current)
    return ((stable_midpoint(box.left, box.right), stable_midpoint(box.top, box.bottom))
            if box is not None else (0., 0.))


def value_dependencies(group):
    return tuple((record, name) for member in members(group)
        for record in member._record_walk(include_self=True) if record.schema is not None
        for name, field in record.schema.fields.items() if field.getter is None and record.child(name) is not None)


def collection_dependencies(group):
    return tuple((record, name) for member in members(group)
        for record in member._record_walk(include_self=True) if record.schema is not None
        for name in (*record.schema.children, *(name for name, field in record.schema.fields.items()
                                               if field.getter is None)))


def normalize(group):
    """Consume an imported positional code and stale centre before model binding."""
    from . import group_records, unplaced_footprint_records
    if group.schema is unplaced_footprint_records.GROUP:
        return group
    if group.schema is None:
        group.bind_schema(group_records.LOCAL_GROUP)
    group.schema.validate_fields(group)
    for name in ('Id', 'X', 'Y'):
        if (field := group.child(name)) is not None:
            field.detach()
    return group.bind_schema(unplaced_footprint_records.GROUP)


def rows(collection, *, layout=None):
    """Generate destination group rows after the output view has been adapted."""
    return ((group['Enabled'], group['Id'], *coordinates(group, layout=layout))
            for group in collection.children('pt'))
