"""Shared detached export preparation for schematic destinations."""
from ...common.references import ReferenceError, Segment
from ..layout.markings import update_markings, resolve_marking_style, apply_marking_style


def _inactive_pattern_records(part):
    pattern = part.child('Pattern')
    if pattern is None:
        return
    # Pads, drawings and holes have boundary slots outside their real records.
    for index, pad in enumerate(pattern.select('Pads/Pad')[1:-1], 1):
        number = pad.scalar('Number_New')
        if number is not None and number != index:
            yield pad
    for shape in pattern.select('Shapes/Shape')[1:-1]:
        if shape.scalar('Type') <= 0:
            yield shape
    for hole in pattern.select('Holes/Hole')[1:-1]:
        if hole.values and hole.values[0] in (False, 'N'):
            yield hole
    for dimension in pattern.select('Dimensions/Dimension'):
        if dimension.scalar('Enabled') in (False, 'N'):
            yield dimension


def prepare_export(document, *, marking_style=None, text_layout=None, additional_user_fields=(),
                   retain_inactive=(), materialize_markings=True,
                   refresh_user_fields=False, compact_inactive=True, destination='asc', report=None,
                   default_main_supplier=False):
    """Clone the current design and prepare destination record arrays.

    References are rebuilt by identity after compaction. A live connection to an
    inactive record is an error, rather than an invitation to discard topology.
    This is preparation only; it does not mark a partial document as complete.
    """
    override = marking_style
    if destination in ('dch', 'asc'):
        active = document.one('/Schematic').child('ActiveSheet')
        if active is not None and active.values != (0,):
            from ...common.conversion import info
            info(report, 'active-sheet', destination,
                 'the selected sheet is omitted; this adapter does not store a sheet selection',
                 (active,), recoverability='sheet contents and per-sheet view settings remain')
    marking_style = resolve_marking_style(document, marking_style)
    view = document.clone()
    # This detached adapter view may pass through incomplete intermediate states.
    # Explicit validation/projection boundaries check the finished result.
    view._automatic_structure = False
    from ..model.definitions import complete_output_defaults
    complete_output_defaults(view)
    view.rebuild(force=False)
    apply_marking_style(view, override)
    schematic = view.one('/Schematic')
    from ..model.symbol_text import (modernize_named_marking_choices)
    modernize_named_marking_choices(schematic)
    if destination in ('asc','dch'):
        from ..model.supplier_data import (prepare_preferences)
        prepare_preferences(schematic,default=default_main_supplier,destination=destination,report=report)
    from ..model.component_links import (prepare_component_links)
    prepare_component_links(view)
    from ..model.multipart_patterns import (prepare_patterns)
    prepare_patterns(view)
    from ..model.traversal import (footprints)
    from ..layout.footprint_frame import (prepare_pattern)
    if destination in ('asc', 'dchxml'):
        # Public drawing views need selection frames. Binary output encodes
        # current physical coordinates and must not recenter an authored edit.
        for pattern in footprints(schematic):
            if pattern is not None and (pattern.parent.kind != 'Part' or pattern.parent.scalar('Enabled') not in (False, 'N')):
                prepare_pattern(pattern)
    from ..model.wire_visibility import (update_wire_visibility)
    update_wire_visibility(schematic)
    if refresh_user_fields:
        from ..model.user_fields import (refresh_global_user_fields)
        refresh_global_user_fields(schematic, destination=destination, report=report)
    choices=schematic.one('ShowUserfield_Global')
    known_keys={row.values[1] for row in choices.children('pt')}
    for row in additional_user_fields:
        if len(row)!=4:
            raise ValueError('global user-field choices require display name, key, state and position')
        if row[1] not in known_keys:
            choices.add('pt',*row)
            known_keys.add(row[1])
    from ..model.angles import (prepare_angles)
    prepare_angles(view, destination=destination, report=report)
    protected = {target for reference in view.references
                 for target in ((reference.target.start, reference.target.end)
                                if isinstance(reference.target, Segment) else (reference.target,))}
    removed, omitted = set(), []
    for name in ('Components','PageConnectors','Shapes','Nets','Buses','Groups','Tables'):
        if not compact_inactive or name in retain_inactive:
            continue
        collection=schematic.child(name)
        for node in collection.children() if collection else ():
            if node.scalar('Enabled') in (False,'N'):
                removed.update(node.walk(include_self=True))
                omitted.append(node)
    for part in schematic.select('Components/Part'):
        if part in removed:
            continue
        if not compact_inactive and part.scalar('Enabled') in (False,'N'):
            continue
        if compact_inactive:
            for node in _inactive_pattern_records(part):
                removed.update(node.walk(include_self=True))
                omitted.append(node)
        shapes = part.one('Shapes')
        if materialize_markings:
            update_markings(part, schematic, style=marking_style, text_layout=text_layout,
                            protected=protected)
        if compact_inactive:
            for drawing in shapes.children('Shape'):
                if drawing.scalar('Enabled') in (False, 'N'):
                    removed.update(drawing.walk(include_self=True))
                    omitted.append(drawing)
        for pin in part.select('Pins/Pin') if compact_inactive else ():
            if pin.scalar('Enabled') in (False, 'N'):
                removed.update(pin.walk(include_self=True))
                omitted.append(pin)

    from ..model.symbol_text import (refresh_symbol_text)
    refresh_symbol_text(view)
    # Validate the whole removal plan before modifying either collections or
    # bindings. Self-index bindings on discarded slots disappear with the slot.
    discarded = []
    for reference in view.references:
        if reference.source in removed:
            discarded.append(reference)
            continue
        targets = ((reference.target.start, reference.target.end)
                   if isinstance(reference.target, Segment) else (reference.target,))
        if any(target in removed for target in targets):
            raise ReferenceError(f'{reference.role}: {destination.upper()} compaction would remove a referenced record')
    discarded_issues = [issue for issue in view.references.issues if issue.source in removed]
    if omitted:
        from .compatibility import (report_omitted_records)
        report_omitted_records(omitted, destination=destination, report=report)
    for reference in discarded:
        view.references.discard(reference)
    for issue in discarded_issues:
        view.references.discard_issue(issue)
    for node in list(removed):
        if node.parent is not None and node.parent not in removed:
            node.parent.remove(node)
    if materialize_markings:
        from ..model.refs import (bind_schematic_references)
        bind_schematic_references(view)
    view.rebuild(force=True)
    return view
