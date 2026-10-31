"""Prepare current PCB ASC electrical, routing and rule data for shared assembly.

This is an internal import stage. Other document sections still need their own
ASC mappings before a complete public adapter can be registered.
"""
from dataclasses import dataclass

from ....common.asc import loads, loads_bytes
from ....common.model import Element, Value
from ....common.units import display_units
from ...model.definitions import NET
from .values import booleans as _flags
from .routing import unpack_trace
from .differential_pairs import unpack_pairs
from ..assembly.routing_inputs import NetInput
from ..assembly.graphic_inputs import GraphicInputs
from ..errors import PcbError
from .components import unpack_component
from .board_rules import unpack_rules
from .rule_settings import unpack_rule_settings
from .document_settings import unpack_document_settings
from .panel import unpack_panel
from .hierarchy import unpack_hierarchy
from .cache import unpack_cache
from .tables import unpack_tables
from .length_rules import unpack_length_rules
from .graphics import unpack_graphics
from .ratlines import unpack_ratlines
from .drc_results import unpack_results
from .teardrops import unpack_teardrops


@dataclass(frozen=True)
class CoreInput:
    root: Element
    source_version: int
    upgrades: GraphicInputs = GraphicInputs()

    def prepare(self, context):
        from ..assembly.object_kinds import normalize_objects
        from ..assembly.graphic_colors import normalize_graphic_colors
        normalize_objects(self.board)
        normalize_graphic_colors(self, context)

    @property
    def board(self):
        return self.root.one('Board')


def _net(net):
    if len(net.arguments) != 1:
        raise PcbError(f'{net.path}: expected one net name')
    if (field := net.child('HideConnections')) is not None:
        if net.child('HideRatlines') is not None:
            raise PcbError(f'{net.path}: duplicate ratline visibility')
        field.kind = 'HideRatlines'
    _flags(net, (name for name, field in NET.fields.items() if field.kind == 'boolean'))
    unpack_teardrops(net)
    members = net.child('Component')
    if members is None or net.child('Pads') is not None:
        raise PcbError(f'{net.path}: expected one component membership collection')
    members.kind = 'Pads'
    for member in members.children():
        if (member.kind != 'pt' or len(member.arguments) != 2 or member.children()
                or any(type(value) is not int for value in member.values)):
            raise PcbError(f'{member.path}: expected component and pad keys')
        member.kind = 'Item'
    traces = net.child('Lines')
    if traces is None or net.child('Traces') is not None:
        raise PcbError(f'{net.path}: expected one trace collection')
    traces.kind = 'Traces'
    prepared = []
    for trace in traces.children():
        if trace.kind != 'Line':
            raise PcbError(f'{trace.path}: expected a trace')
        trace.kind = 'Trace'
        prepared.append(unpack_trace(trace))
    # These repeat the selected default via style's dimensions. They are not
    # independent per-net facts in the editable model.
    for name in ('ViaSize', 'ViaRing', 'ThroughVia'):
        if (field := net.child(name)) is not None:
            field.detach()
    return NetInput(net, tuple(prepared))


def prepare_core(text, *, source=None, encoding=None):
    """Prepare components, membership, routing and rules from one ASC input.

    The source version is diagnostic input syntax, not a binary geometry gate.
    ASC's named current geometry is not run through older binary upgrades.
    Returned input can enter the shared core assembler; its document remains
    incomplete until the remaining adapter stages have been implemented.
    """
    syntax = (loads(text, source=source) if isinstance(text, str) else
              loads_bytes(text, source=source, encoding=encoding))
    try:
        header = syntax.one('/Source')
        board = syntax.one('/Board')
    except LookupError as error:
        raise PcbError('PCB ASC requires one Source and one Board') from error
    if (len(header.values) != 2 or header.values[0] != 'DipTrace-PCBN'
            or type(header.values[1]) is not int):
        raise PcbError('unsupported PCB ASC source declaration')
    source_version = header.values[1]
    header.detach()
    units = syntax.one('/Units')
    if len(units.values) != 1:
        raise PcbError('PCB ASC requires one unit selection')
    units.set_values(display_units(units.values[0]))
    root = Element('')
    # Transfer the parser-owned top-level records through normal tree operations;
    # this avoids cloning a large design solely to acquire an unowned root.
    for child in tuple(syntax.root.children()):
        child.move_to(root)
    for component in board.one('Components').children():
        if component.kind != 'Component':
            raise PcbError(f'{component.path}: expected a component')
        unpack_component(component)
    # Header text positions must be decoded before lexical spelling is removed.
    # Their identities are bound later, together with the other prepared data.
    unpack_rules(board)
    for node in root.walk(include_self=True):
        node._syntax = None
        if node.arguments:
            node.set_values(*(Value(value.value, value.kind, value.unit, source=value.source)
                              for value in node.arguments))
    nets = []
    for net in board.one('Nets').children():
        if net.kind != 'Net':
            raise PcbError(f'{net.path}: expected a net')
        nets.append(_net(net))
    unpack_document_settings(board)
    unpack_panel(board)
    unpack_hierarchy(board)
    unpack_cache(board)
    unpack_tables(board)
    unpack_rule_settings(board)
    unpack_length_rules(board)
    unpack_ratlines(board)
    unpack_results(board)
    drawings, pours = unpack_graphics(board)
    separate = unpack_pairs(board)
    unpack_pairs(board, removed=True)
    return CoreInput(root, source_version, GraphicInputs(tuple(nets), separate, drawings, pours))
