"""Prepare PCB XML electrical records for the existing identity assembler.

This section does not complete a document import. Its caller must also consume
library metadata, settings, board geometry and the other XML sections.
"""
from ..assembly.graphic_inputs import GraphicInputs
from .components import read_component
from .nets import read_nets
from ..errors import PcbError
from .vias import read_vias
from .layers import read_layers, read_stack
from .classes import read_classes
from .pairs import read_pairs
from .design_rules import read_design_rules
from .length_rules import read_length_rules
from .graphics import read_outline, read_groups, read_non_signals, read_drawings
from .pours import read_pours
from .dimensions import read_dimensions
from .ratlines import read_ratlines
from .drc_results import read_results
from .tables import read_tables
from .assembly_variants import read_variants


def read_electrical(record, board, *, patterns, units, version, common_fiducials=True):
    placements = {}
    read_variants(record, board)
    layers = read_layers(record, board, units=units)
    read_stack(record, board, layers=layers, units=units)
    vias = read_vias(record, board, units=units, layer_count=len(layers))
    classes = read_classes(record, board, layers=layers, vias=vias, units=units)
    read_design_rules(record, board, classes=classes, layers=layers, units=units, version=version)
    components = board.add('Components')
    for row in record.rows('Components', 'Component'):
        placed = read_component(row, patterns=patterns, units=units, vias=vias, layers=layers,
                                common_fiducials=common_fiducials)
        key = placed.component['Number']
        if key in placements:
            raise PcbError(f'{row.node.path}: duplicate component Id {key}')
        placements[key] = placed
        components.append(placed.component)
    nets = read_nets(record, board, placements=placements, units=units,
                     layers=layers, vias=vias, classes=classes, version=version)
    separate = read_pairs(record, board, placements=placements, units=units,
                           layers=layers, vias=vias, classes=classes, version=version)
    read_pairs(record, board, placements=placements, units=units,
               layers=layers, vias=vias, classes=classes, version=version, removed=True)
    read_length_rules(record, board, placements=placements, classes=classes, units=units)
    read_ratlines(record, board, units=units, placements=placements)
    read_outline(record, board, units=units)
    read_groups(record, board)
    non_signals = read_non_signals(record, board)
    drawings = read_drawings(record, board, units=units, layers=layers, non_signals=non_signals, version=version)
    pours = read_pours(record, board, units=units, layers=layers, version=version)
    read_dimensions(record, board, units=units, placements=placements, version=version)
    read_results(record, board, units=units, placements=placements, classes=classes, layers=layers)
    read_tables(record, board, units=units, version=version)
    return GraphicInputs(nets, separate, drawings, pours)
