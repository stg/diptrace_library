"""Schematic destination capabilities and adaptation diagnostics."""
from ...common.conversion import (info, warn)


def report_generated_marking_attributes(schematic, *, use_part_font_color, font_name='', report=None):
    """Report placed label attributes absent from the current XML mapping.

    Text and anchors are calculated; these retained drawing settings can carry
    independent choices. Compare with actual fresh-label defaults on XML import.
    """
    color = schematic.one('Settings').scalar('PartFontColor', 0) if use_part_font_color else 0
    defaults = dict(FontColor=color, PenWidth=1, LineSpacing=1, TextAlign=-1, Locked=False, Group=-1)
    shapes = [shape for shape in schematic.select('Components/Part/Shapes/Shape')
              if shape.scalar('MarkingGenerated') in (True, 'Y')]
    omitted = [field for shape in shapes
               for name, value in defaults.items()
               if (field := shape.child(name)) is not None and field.values != (value,)]
    if schematic.one('Settings').child('MarkingFontName') is None:
        omitted.extend(shape.one('FontName') for shape in shapes
                       if shape.scalar('FontName') and shape.scalar('FontName') != font_name)
    omitted.extend(key for shape in shapes for key in shape.select('UnresolvedKeys/Key'))
    if omitted:
        warn(report, 'generated-marking-attributes', 'dchxml',
             'per-label drawing attributes are omitted by the current XML adapter', omitted,
             recoverability='label definitions and global marking settings remain; individual overrides do not reconstruct')


def _empty_inactive_drawing(node):
    """An unused undefined slot has no drawing, text or identity association."""
    if node.kind != 'Shape' or node.scalar('Enabled') not in (False, 'N') or node.scalar('Type') != 0:
        return False
    if node.scalar('Name', '') or any(any(row.values) for row in node.select('TextLine/pt')):
        return False
    if any(node.select(path) for path in ('Points/pt', 'Points_New/pt')):
        return False
    if any(node.scalar(name, -1) >= 0 for name in ('Group', 'PadId', 'RelatedNet', 'RelatedBus')):
        return False
    return True


def report_omitted_records(nodes, *, destination, report=None, rule='inactive-records'):
    """Separate empty compatibility slots from inactive content worth retaining."""
    empty, content = [], []
    for node in nodes:
        (empty if _empty_inactive_drawing(node) else content).append(node)
    if empty:
        info(report, 'inactive-empty-drawings', destination, 'empty inactive drawing slots are omitted', empty,
             recoverability='no drawing, text or association is lost; unused slot attributes remain in the authoring model')
    if content:
        warn(report, rule, destination, 'inactive records are omitted from this export view', content,
             recoverability='inactive states and content remain in the authoring model')


def nondefault_net_ids(schematic):
    """Persistent net identities that differ from the destination's defaults."""
    result = []
    for index, net in enumerate(schematic.select('Nets/Net')):
        node = net.child('HiddenId')
        if node is None:
            continue
        if len(node.arguments) != 1:
            raise ValueError(f'{node.path}: HiddenId requires one value')
        if node.values[0] != index:
            result.append(node)
    return result


def report_text_omissions(document, *, destination, report=None):
    """Report known saved data absent from the public text projections."""
    from ..model.traversal import (symbols, cached_definitions)
    schematic = document.one('/Schematic')
    locators, quotes, main_flags = [], [], []
    for part in symbols(schematic):
        supplier = part.child('Suppliers')
        if supplier is None:
            continue
        locator = supplier.child('SourceLocator')
        if locator is not None and locator.values and locator.values[0]:
            locators.append(locator)
        quotes.extend(supplier.select('Prices/Quote'))
        flag = supplier.child('MainSupplier')
        if destination == 'dchxml' and flag is not None and flag.values == (True,):
            main_flags.append(flag)
    for rule, message, nodes in (
            ('supplier-source-locator', 'stored supplier source locators are omitted', locators),
            ('supplier-quotes', 'stored supplier quantity/price rows are omitted', quotes)):
        if nodes:
            warn(report, rule, destination, message, nodes,
                 recoverability='the omitted saved values cannot be recovered from this destination alone; source facts remain intact')
    notes = [part.one('ModelNote') for definition in cached_definitions(schematic)
             if (part := definition.one('Part')).scalar('ModelNote', '')]
    if notes:
        warn(report, 'cached-model-note', destination, 'cached model notes are omitted by this adapter', notes,
             recoverability='model notes remain editable in the authoring model; the current destination mapping does not include them')
    if main_flags:
        info(report, 'supplier-preference', destination, 'the cached main-supplier match flag is omitted', main_flags,
             recoverability='the chosen supplier is retained; its match to a preferred supplier depends on the receiving environment, not the saved cached bit')
    if destination == 'asc':
        from ..model.page_titles import (has_title_data)
        titles = [grid for grid in schematic.select('Pages/Page/TitleBlocks/TitleBlock') if has_title_data(grid)]
        if titles:
            warn(report, 'page-title-blocks', destination, 'page title-grid names, layout and fields are omitted', titles,
                 recoverability='the original title definitions cannot be recovered from ASC; source facts remain intact')


def _remove_resources(document, containers):
    from ...common.references import (ReferenceError, Segment)
    removed = {node for container in containers for node in container.walk(include_self=True)}
    graph = document.references
    for reference in list(graph):
        targets = (reference.target.start, reference.target.end) if isinstance(reference.target, Segment) else (reference.target,)
        if reference.source in removed:
            graph.discard(reference)
        elif any(target in removed for target in targets):
            raise ReferenceError('an external reference into an omitted standalone resource needs an export mapping')
    for issue in list(graph.issues):
        if issue.source in removed:
            graph.discard_issue(issue)
        elif issue.collections and any(owner in removed for owner in issue.collections):
            raise ReferenceError('an unresolved external resource reference needs an export mapping')
    graph._watched = {owner: rows for owner, rows in graph._watched.items() if owner not in removed}
    graph._pending_index_collections = {(owner, kind) for owner, kind in graph._pending_index_collections if owner not in removed}
    for container in containers:
        container.detach()


def apply_capacity(document, *, destination, report=None):
    """Apply current DCH/ASC mappings to an already detached export view.

    Unknown fields and unknown geometry remain errors. These rules describe
    specific known fields, not a general permission to discard extra content.
    """
    from ..model.traversal import (footprints, cached_definitions)
    from .dchxml.catalog import (unrepresented_pattern_categories)
    schematic = document.one('/Schematic')
    from ..layout.markings import (common_marking_family)
    family = schematic.one('Settings').child('MarkingFontName')
    if family is not None and family.values[0] and common_marking_family(schematic) != family.values[0]:
        warn(report, 'global-marking-font', destination,
             'the global marking font choice cannot be recovered unambiguously from generated labels', [family],
             recoverability='this destination stores marking families on drawings; the global choice remains in the authoring model')
    from ..model.local_keys import (prepare_positional_keys)
    prepare_positional_keys(document, destination=destination, report=report)
    if destination == 'asc':
        report_text_omissions(document, destination=destination, report=report)
        rotated = [pad for pattern in footprints(schematic) for pad in pattern.select('Pads/Pad')
                   if pad.scalar('Standard') in (True, 'Y') and abs(float(pad.scalar('PadAngle'))) >= .001]
        if rotated:
            info(report, 'pad-standard-orientation', destination,
                 'rotated pads use explicit geometry and Standard=False in ASC', rotated,
                 recoverability='physical geometry and angle are retained; the authoring choice remains in the source model')
        hidden = nondefault_net_ids(schematic)
        if hidden:
            warn(report, 'net-hidden-id', destination, 'nondefault Net.HiddenId is omitted by ASC 46', hidden)
        linked = [shape for pattern in footprints(schematic) for shape in pattern.select('Shapes/Shape')
                  if shape.scalar('PadId', -1) != -1]
        if linked:
            warn(report, 'shape-pad-id', destination, 'footprint Shape.PadId is omitted by ASC 46', linked)
    cache = schematic.one('CacheLib')
    resources = [cache.child(name) for name in ('Patterns', 'PadStyles') if cache.child(name) is not None]
    if any(container.children() for container in resources):
        warn(report, 'standalone-library-resources', destination,
             'standalone XML library resources are omitted; embedded definitions remain',
             [row for container in resources for row in container.children()])
    if resources:
        _remove_resources(document, resources)
    empty_shapes = []
    for pattern in footprints(schematic):
        owners = [(pattern, 'PadShape'), *((pad, 'PadShape_New') for pad in pattern.select('Pads/Pad'))]
        for owner, name in owners:
            empty_shapes.extend(terminal.one('Type') for terminal in owner.children('PadTerminal')
                                if terminal.scalar('Type') == '')
            if owner.scalar(name) == '':
                empty_shapes.append(owner.one(name))
    if empty_shapes:
        info(report, 'empty-pad-shape', destination,
             'empty XML pad-shape labels use numeric -1 in this destination', empty_shapes,
             recoverability='both forms denote an unspecified shape; the empty label remains in the authoring model')
        for node in empty_shapes:
            node.set_values(-1)
    public_keys = []
    for pattern in footprints(schematic):
        for index, pad in enumerate(pattern.select('Pads/Pad')[1:-1], 1):
            key = pad.child('Id')
            if key is not None and key.values != (index,):
                public_keys.append(key)
    if public_keys:
        info(report, 'pad-public-ids', destination, 'XML pad keys become positional pad IDs', public_keys,
             recoverability='resolved targets are preserved; literal public keys remain in the authoring model')
    catalog = unrepresented_pattern_categories(schematic)
    if catalog:
        warn(report, 'unused-pattern-catalog', destination, 'unused XML pattern-category labels are omitted',
             schematic.select('CacheLib/PatternCategories/Category'))
    fields = []
    for pattern in footprints(schematic):
        for name, rule, text in (
                ('Sided', 'default-pad-side', 'XML default pad side is omitted'),
                ('RefDes', 'footprint-reference-prefix', 'XML footprint RefDes prefix is omitted'),
                ('Datasheet', 'footprint-datasheet', 'footprint Datasheet is omitted')):
            if name == 'Datasheet' and destination == 'asc' and pattern.parent.kind == 'Definition':
                continue  # Cached ASC footprints have their own Datasheet field.
            node = pattern.child(name)
            if node is not None:
                fields.append((node, rule, text))
    for definition in cached_definitions(schematic):
        part = definition.one('Part')
        if part.child('Datasheet') is not None:
            fields.append((part.one('Datasheet'), 'cached-symbol-datasheet', 'cached symbol Datasheet is omitted'))
        for pin in part.select('Pins/Pin'):
            if pin.child('SignalDelay') is not None:
                fields.append((pin.one('SignalDelay'), 'cached-pin-delay', 'cached pin SignalDelay is omitted'))
    grouped = {}
    for node, rule, text in fields:
        if node.values and node.values[0]:
            grouped.setdefault((rule, text), []).append(node)
        if destination == 'asc':
            node.annotations['asc_omit'] = 'known reported destination mapping omission'
    for (rule, text), nodes in grouped.items():
        warn(report, rule, destination, text, nodes)
    if destination == 'dch':
        labels, flags = [], []
        for definition in cached_definitions(schematic):
            part = definition.one('Part')
            labels.extend(row for row in part.select('UserFields/UserField') if any(value != 0 for value in row.values[3:]))
            flags.extend(shape for shape in part.select('Shapes/Shape') if shape.scalar('ShowPart') or shape.scalar('MarkingGenerated'))
        if labels:
            warn(report, 'cached-label-options', destination, 'cached UserField label choices are omitted', labels)
        if flags:
            warn(report, 'cached-drawing-flags', destination, 'cached ShowPart/MarkingGenerated flags are omitted', flags)
