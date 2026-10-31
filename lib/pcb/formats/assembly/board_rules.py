"""Bind copper, via and class indices during the unfinished board import."""
from dataclasses import dataclass, field

from ....common.structural_edits import assembly
from ...model import board_rules, routing_records
from ...model.definitions import COMPONENT, NET
from ...model.stackup import default_stackup
from .routing import RoutingAssembly, assemble_routing
from ..errors import PcbError
from .via_styles import source_span


@dataclass(frozen=True)
class BoardRulesAssembly:
    routing: RoutingAssembly
    layers: dict
    via_styles: dict
    classes: dict
    length_connections: dict = field(default_factory=dict)
    length_scopes: dict = field(default_factory=dict)

    @property
    def document(self):
        return self.routing.document


def assemble_rules(decoded, routed=None):
    """Consume known routing-rule positions, retaining only model identities.

    Other per-layer/class tables still require their complete record mappings.
    The resulting document remains explicitly incomplete and is not public I/O.
    """
    routed = assemble_routing(decoded) if routed is None else routed
    board, document = decoded.board, routed.document
    layers = dict(enumerate(board.select('Layers/Layer')))
    vias = dict(enumerate(board.select('ViaStyles/ViaStyle')))
    classes = dict(enumerate(board.select('NetClasses/NetClass')))
    links, consumed, style_values = [], [], []

    def consume(node, field, choices, role):
        slot = node.child(field)
        if slot is None:
            return
        index = slot.values[0]
        if index >= 0:
            target = choices.get(index)
            if target is None:
                raise PcbError(f'unresolved {role} index {index}')
            links.append((node, role, target))
        consumed.append(slot)

    for layer in layers.values():
        consumed.append(layer.one('Number'))
        consume(layer, 'NetNumber', routed.core.nets, 'layer-net')
    # Earlier limits have already been modernized into FixedLength and
    # LengthDelta. They are compatibility slots, not a second editable policy.
    for net_class in classes.values():
        consumed.extend(slot for name in ('MinLength', 'MaxLength')
                        if (slot := net_class.child(name)) is not None)
    for style in vias.values():
        name, through, size, hole, start, end = style.values
        style_values.append((style, name, size, hole))
        if (bounds := source_span(through, start, end, len(layers))) is not None:
            # The current stack bounds the saved span. An explicitly bounded
            # span remains bounded even when it currently reaches both outside
            # layers; adding another layer must not turn that into Through.
            start, end = bounds
            links.extend(((style, 'via-span-from', layers[start]), (style, 'via-span-to', layers[end])))

    for node in board.walk(include_self=True):
        if node.schema is COMPONENT:
            consume(node, 'ConnectedLayer', layers, 'copper-layer')
            consume(node, 'ViaStyle', vias, 'via-style')
        elif node.schema in (routing_records.POINT, routing_records.SIDE_POINT, routing_records.CENTER):
            consume(node, 'Lay', layers, 'copper-layer')
            consume(node, 'ViaStyle', vias, 'via-style')
        elif node.schema in (NET, routing_records.PAIR, routing_records.REMOVED_PAIR):
            consume(node, 'NetClass', classes, 'net-class')
        elif node.kind == 'LayerStackItem' and node.parent.kind == 'LayerStackItems':
            consume(node, 'Lay', layers, 'copper-layer')
            material = node.child('Material')
            if material is not None and (kind := material.child('Type')) is not None:
                value = kind.values[0]
                selected = node.one('Lay').values[0]
                if (value < 2) != (selected >= 0):
                    raise PcbError('stackup material classification requires import normalization')
                consumed.append(kind)

    with assembly(document):
        for slot in consumed:
            slot.detach()
        for style, name, size, hole in style_values:
            style.set_values(name)
            style.add('Size', size)
            style.add('HoleSize', hole)
        for node in board.walk(include_self=True):
            schema = board_rules.definition(node)
            if schema is not None:
                if schema is board_rules.STACK_ITEM:
                    node.set_values()
                node.bind_schema(schema)
        with document.references.binding_batch():
            for source, role, target in links:
                document.references.bind(source, target, role=role, preserve=True)
        for style in vias.values():
            board_rules.validate_span(document, style)
        stack = board.child('LayerStackItems')
        if stack is None or not stack.children():
            try:
                proposal = default_stackup(layers.values())
            except ValueError as error:
                raise PcbError(str(error)) from error
            if stack is not None:
                stack.detach()
            board['LayerStackName'] = proposal.name
            board.append(proposal.items)
            with document.references.binding_batch():
                for item, layer in proposal.copper_layers:
                    document.references.bind(item, layer, role='copper-layer', preserve=True)
    from .rule_tables import assemble_tables
    from .pad_overrides import assemble_pad_overrides
    from .length_matching import assemble_length_rules
    from .teardrops import assemble_teardrops
    result = assemble_tables(BoardRulesAssembly(routed, layers, vias, classes))
    return assemble_teardrops(assemble_length_rules(assemble_pad_overrides(result)))
