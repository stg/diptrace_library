"""Decode a complete DIP stream before current-model modernization and binding.

The returned tree and upgrade inputs are internal adapter state. They are not
the editable PCB document and must not be returned by the public import API.
"""
from dataclasses import dataclass, replace

from ....common.model import Element
from ....common.library_codec import CachedDefinitionInput
from .binary import DipError, Header
from .read import Reader
from .preamble import InitialState, read_initial_sections
from .components import ComponentUpgrade, read_base_components
from ..assembly.routing_inputs import NetInput, TraceInput
from .nets import read_connections, read_base_nets
from .drawings import DrawingUpgrade, read_base_drawings, read_board_dimensions
from .sheet import read_groups, read_sheet_layout
from .tables import read_base_tables
from .pours import PourUpgrade, read_base_pours
from .settings import (DisplayUpgrade, read_display_settings, read_rule_settings,
                       read_camera_extension, read_grid_extension)
from .results import read_initial_results
from .metadata import read_metadata_extensions
from .cache import read_cache
from .differential_pairs import read_initial_pairs, read_routing_extensions
from .layer_stack import read_layer_stack
from .length_rules import read_length_rules
from .meanders import read_meanders
from .masks import read_mask_extensions
from .modern import read_drawing_extensions, read_pin_rotations
from .teardrops import read_teardrops
from .project import read_project_extensions
from .suppliers import read_suppliers
from .paths import read_variable_paths, read_column_titles
from .routing_session import read_routing_session
from .recent import read_recent_extensions


@dataclass(frozen=True)
class UpgradeInputs:
    """Temporary older representations consumed by import modernization."""
    initial: InitialState
    components: tuple[ComponentUpgrade, ...]
    nets: tuple[NetInput, ...]
    drawings: tuple[DrawingUpgrade, ...]
    pours: tuple[PourUpgrade, ...]
    display: DisplayUpgrade
    cached_definitions: tuple[CachedDefinitionInput, ...]
    separate_traces: tuple[TraceInput, ...]


@dataclass(frozen=True)
class DecodedBoard:
    root: Element
    header: Header
    upgrades: UpgradeInputs

    @property
    def requires_pair_refresh(self):
        """This input revision requires automatic pair-member modernization."""
        return self.header.version == 40

    def prepare(self, context):
        """Apply DIP-specific normalization before common identity binding."""
        # Raw upgrade inputs also describe deleted slots. They have no current
        # geometry to modernize after the core selected the active records.
        components = tuple(item for item in self.upgrades.components if item.component['Enabled'])
        if len(components) != len(self.upgrades.components):
            self = replace(self, upgrades=replace(self.upgrades, components=components))
        from .rule_defaults import modernize_rules
        from .property_defaults import modernize_properties
        from .geometry import modernize_drawings
        from .table_model import modernize_tables
        modernize_rules(self)
        modernize_properties(self)
        modernize_drawings(self, text_layout=context.layout)
        modernize_tables(self)
        from .pictures import modernize_picture_sources
        modernize_picture_sources(self)
        from ..assembly.object_kinds import normalize_objects
        from ..assembly.graphic_colors import normalize_graphic_colors
        normalize_objects(self.board)
        normalize_graphic_colors(self, context)

    @property
    def board(self):
        return self.root.one('Board')


def decode(data, *, source=None, ansi_encoding='cp1252'):
    """Decode one supplied stream, rejecting unread or unimplemented content."""
    reader = Reader(data, source=source, ansi_encoding=ansi_encoding)
    root = Element('')
    initial = read_initial_sections(reader, root)
    board = root.one('Board')
    components = read_base_components(reader, board, initial.component_count)
    read_connections(reader, board)
    nets = read_base_nets(reader, board)
    drawings = read_base_drawings(reader, board)
    read_groups(reader, board)
    read_sheet_layout(reader, board)
    read_base_tables(reader, board)
    pours = read_base_pours(reader, board)
    read_board_dimensions(reader, board)
    display = read_display_settings(reader, board)
    read_rule_settings(reader, board)
    read_initial_results(reader, board)
    read_metadata_extensions(reader, board)
    definitions = read_cache(reader, board)
    read_initial_pairs(reader, board)
    separate_traces = read_routing_extensions(reader, board)
    read_camera_extension(reader, root)
    read_layer_stack(reader, board)
    read_length_rules(reader, board)
    read_meanders(reader, board)
    read_mask_extensions(reader, board, definitions)
    read_grid_extension(reader, board)
    read_drawing_extensions(reader, board, definitions)
    read_pin_rotations(reader, definitions)
    read_teardrops(reader, board)
    read_project_extensions(reader, board, definitions)
    read_suppliers(reader, board, definitions)
    if read_variable_paths(reader, board):
        read_routing_session(reader)
    read_column_titles(reader, board)
    read_recent_extensions(reader, board, definitions)
    if reader.pos != len(reader.data):
        raise DipError(f'unread DIP content at byte {reader.pos}: '
                       f'{len(reader.data)-reader.pos} bytes remain')
    upgrades = UpgradeInputs(initial, components, nets, drawings, pours,
                             display, definitions, separate_traces)
    return DecodedBoard(root, reader.header, upgrades)
