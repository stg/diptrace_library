"""Consume graphic, pour and group selectors into current PCB identities."""
from dataclasses import dataclass

from ....common.conversion import import_notice
from ....common.structural_edits import assembly
from ...model import graphic_records
from ...model import label_text
from ...model.definitions import definition
from ..errors import PcbError
from ..marking_defaults import complete_user_markings
from .board_rules import BoardRulesAssembly, assemble_rules
from .library import FootprintAssembly
from .tables import prepare_rows, bind_rows
from .non_signal_layers import prepare as prepare_non_signals, bind as bind_non_signals
from .pictures import prepare_pictures
from .footprint_data import consume_drawing_pads, bind_drawing_pads
from .pour_regions import prepare as prepare_pour_regions
from .board_drawings import disable_degenerate_drawings
from ...model.pour_regions import ROLE as REGION_ROLE
from .dimensions import (prepare_local_dimensions, prepare_board_dimensions,
                         bind_local_dimensions, bind_board_dimensions, board_dimension_scope)


@dataclass(frozen=True)
class GraphicAssembly:
    rules: BoardRulesAssembly
    groups: dict
    drawings: dict
    pours: dict
    non_signals: dict
    placed_shapes: dict
    placed_holes: dict

    @property
    def document(self):
        return self.rules.document


def _keyed(upgrades, name):
    result = {}
    for item in upgrades:
        node = getattr(item, name)
        if not node.get('Enabled', True):
            continue
        if item.previous_number in result:
            raise PcbError(f'ambiguous saved {name} key {item.previous_number}')
        result[item.previous_number] = node
    return result


def normalize_graphic_nets(drawings, pours, nets):
    """Resolve unavailable assignments before binding current identities."""
    changed = []
    for owners, name in ((drawings, 'NetNumber'), (pours, 'NetId')):
        for owner in owners:
            slot = owner.child(name)
            if slot is None or slot.values[0] < 0:
                continue
            target = nets.get(slot.values[0])
            if target is None or not target.get('Enabled', True):
                slot.set_values(-1)
                changed.append(owner)
    return changed


def _bind_record(node):
    """Stored primitive fields use their owner's schema, not a record lookup."""
    parent = node.parent
    if node.schema is None and parent is not None and parent.schema is not None:
        field = parent.schema.fields.get(node.kind)
        if field is not None and field.getter is None and field.kind in ('boolean', 'integer', 'number', 'text'):
            return
    if (schema := definition(node)) is not None:
        node.bind_schema(schema)


def assemble_graphics(decoded, rules=None):
    """Modernize current graphics and resolve their relationships."""
    rules = assemble_rules(decoded) if rules is None else rules
    document, board = rules.document, decoded.board
    groups, signals, links, consumed, inactive = {}, {}, [], [], []
    placed_shapes, placed_holes, footprints = {}, {}, []
    group_values, signal_values, clear_values = [], [], []

    for group in board.select('Groups/Group'):
        key, x, y = group.values
        if not group.get('Enabled', True):
            inactive.append(group)
            continue
        if key in groups:
            raise PcbError(f'ambiguous saved group key {key}')
        groups[key] = group
        group_values.append((group, x, y))
    for index, layer in enumerate(board.select('NonSignals/NonSignal')):
        name, color, _number, side = layer.values
        signals[index] = layer
        signal_values.append((layer, name, color, side))

    with assembly(document):
        disable_degenerate_drawings(board)
    drawings = _keyed(decoded.upgrades.drawings, 'drawing')
    pours = _keyed(decoded.upgrades.pours, 'pour')
    # Input revisions name the same current drawing geometry differently.
    # Consume that vocabulary here, after any adapter geometry modernization.
    with assembly(document):
        cleared_nets = normalize_graphic_nets(drawings.values(), pours.values(), rules.routing.core.nets)
        for drawing in drawings.values():
            if (points := drawing.child('Points_New')) is not None:
                if drawing.child('Points') is not None:
                    raise PcbError(f'{drawing.path}: duplicate board drawing geometry')
                points.kind = 'Points'
            vector = drawing.child('PictureVector')
            if (vector is not None and vector.get('Width', 0) == vector.get('Height', 0) == 0
                    and all(child.kind in ('Width', 'Height', 'Polygons') for child in vector.children())
                    and (polygons := vector.child('Polygons')) is not None and not polygons.children()):
                # Empty zero-size compatibility data does not describe a picture.
                vector.detach()
    for path in ('Shapes/Shape', 'CopperPours/CopperPour', 'Tables/Table', 'Dimensions/Dimension'):
        inactive.extend(node for node in board.select(path) if not node.get('Enabled', True))
    for component in rules.routing.core.components.records:
        shape_map, hole_map = {}, {}
        shapes = component.select('Pattern/Shapes/Shape')
        holes = component.select('Pattern/Holes/Hole')
        for index, shape in enumerate(shapes):
            if shape.get('Type', 0) < 1:
                inactive.append(shape)
            else:
                placed_shapes[component, index] = shape
                if 0 < index < len(shapes)-1:
                    shape_map[index] = shape
        for index, hole in enumerate(holes):
            if not hole.values[0]:
                inactive.append(hole)
            else:
                placed_holes[component, index] = hole
                if 0 < index < len(holes)-1:
                    hole_map[index] = hole
        inactive.extend(node for node in component.select('Pattern/Dimensions/Dimension')
                        if not node.get('Enabled', True))
        footprints.append(FootprintAssembly(component.one('Pattern'),
            rules.routing.core.pad_positions[component], shape_map, hole_map))
    dimension_scope = board_dimension_scope(rules.routing, footprints, drawings=drawings, pours=pours)
    with assembly(document):
        drawing_links = [link for footprint in footprints for link in consume_drawing_pads(footprint)]
        for footprint in footprints:
            prepare_local_dimensions(footprint)
        prepare_board_dimensions(document, dimension_scope)
        table_rows = prepare_rows(board, rules.routing.core.components.records)
    removed = set(inactive)
    with assembly(document):
        non_signal_plan = prepare_non_signals(board, removed)
        prepare_pictures(board, drawings.values())

    def consume(node, field, targets, role):
        slot = node.child(field)
        if slot is None:
            return
        key = slot.values[0]
        if key >= 0:
            target = targets.get(key)
            if target is None:
                raise PcbError(f'unresolved saved {role} selector {key}')
            links.append((node, role, target))
        consumed.append(slot)

    for drawing in drawings.values():
        scope = graphic_records.layer_scope(drawing)
        if scope is not None:
            consume(drawing, 'LayId', rules.layers if scope == 'Layers' else signals, 'drawing-layer')
        elif (slot := drawing.child('LayId')) is not None:
            consumed.append(slot)
        consume(drawing, 'NetNumber', rules.routing.core.nets, 'graphic-net')
        clear_values.append(drawing)
    for pour in pours.values():
        consume(pour, 'Lay', rules.layers, 'copper-layer')
        consume(pour, 'NetId', rules.routing.core.nets, 'graphic-net')
        clear_values.append(pour)

    # Footprint-internal group codes have a separate scope. Only whole board
    # objects participate in these group identities.
    paths = ('Components/Component', 'Nets/Net/Traces/Trace',
             'DifferentialPairs/DifferentialPair/PosSeparateTraces/PosTrace',
             'DifferentialPairs/DifferentialPair/NegSeparateTraces/NegTrace',
             'Shapes/Shape', 'CopperPours/CopperPour', 'Tables/Table', 'Dimensions/Dimension')
    for path in paths:
        for node in board.select(path):
            if node not in removed:
                consume(node, 'Group', groups, 'pcb-group')
    for path in ('Tables/Table', 'Dimensions/Dimension', 'Components/Component/Pattern/Dimensions/Dimension'):
        clear_values.extend(node for node in board.select(path) if node not in removed)

    with assembly(document):
        region_links = prepare_pour_regions(decoded.upgrades.pours)
        for node in inactive:
            node.detach()
        for slot in consumed:
            slot.detach()
        for node in clear_values:
            node.set_values()
        for group, x, y in group_values:
            group.set_values()
            group.add('X', x)
            group.add('Y', y)
        for layer, name, color, side in signal_values:
            layer.set_values(name)
            layer.add('Color', color)
            layer.add('Side', side)
        pending = [board]
        while pending:
            node = pending.pop()
            # Definition-local geometry has its own grouping scope.
            if node.kind == 'CacheLib':
                continue
            _bind_record(node)
            pending.extend(reversed(node._child_sequence()))
        renamed, added = complete_user_markings(board)
        if renamed:
            import_notice('info', 'empty-user-field-name',
                          'Named blank component fields Untitled.', renamed)
        if added:
            import_notice('info', 'user-field-marking-defaults',
                          'Added hidden global marking rules for component custom fields.', added,
                          recoverability='field text and individual placements remain unchanged')
        with document.references.binding_batch():
            for primitive, group in region_links:
                document.references.bind(primitive, group, role=REGION_ROLE, preserve=True)
            bind_drawing_pads(document, drawing_links)
            for source, role, target in links:
                document.references.bind(source, target, role=role, preserve=True)
            for footprint in footprints:
                bind_local_dimensions(document, footprint)
            bind_board_dimensions(document, dimension_scope)
            bind_rows(document, table_rows)
            bind_non_signals(document, non_signal_plan)
        text_shapes = tuple(shape for footprint in footprints
                            for shape in footprint.pattern.select('Shapes/Shape'))
        label_text.bind_user_fields(document, text_shapes)
        plans = label_text.plan_text(document, text_shapes)
        label_text.apply_text(plans)
        for shape, *_ in plans:
            for node in shape.walk(include_self=True):
                _bind_record(node)
        if plans:
            import_notice('info', 'bound-pattern-text', 'Refreshed text bound to current component fields',
                          (shape for shape, *_ in plans), recoverability='text is calculated from current fields')
    if cleared_nets:
        import_notice('info', 'graphic-net-normalization',
                      'Cleared drawing or pour assignments to unavailable nets.', cleared_nets,
                      recoverability='geometry remains; unavailable or disabled nets do not remain assigned')
    from .drc_results import assemble_results
    result = assemble_results(GraphicAssembly(rules, groups, drawings, pours, signals, placed_shapes, placed_holes))
    document.complete = True
    document.diagnostics[:] = [message for message in document.diagnostics
                               if message != 'PCB import assembly is incomplete']
    return result
