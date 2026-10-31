"""Supported-version DIP composition with detached defaults for absent settings."""
from ..output_indices import OutputIndices
from ....common.conversion import info, warn
from ..export_view import prepare_export
from ..revision_adaptation import prepare_binary_revision
from .writer import Writer
from .frame_projection import project_frames
from .write_initial import write_initial_sections
from .write_components import component_outputs, write_base_components, write_pad_mask_overrides, write_placed_extensions
from .write_nets import write_connections, write_base_nets
from .write_graphics import (write_base_drawings, write_groups, write_base_pours,
                            write_board_dimensions, write_board_drawing_extensions)
from .write_document import (write_sheet_layout, write_base_tables, write_document_spacing,
                             write_table_document_options, write_column_titles)
from .write_settings import (write_display_settings, write_rule_settings, write_mask_settings,
                             write_grid_extension, write_display_extensions)
from .write_results import write_initial_results
from .write_cache import (definition_outputs, write_cache, write_cache_masks,
                          write_cache_extensions, write_cache_pin_rotations)
from .write_pairs import write_initial_pairs, write_routing_extensions, write_meanders
from .write_electrical import write_metadata, write_layer_stack, write_length_rules, write_teardrops
from .write_project import (write_global_markings, write_project, write_suppliers,
                            write_variable_paths, write_recent)


def encode(document, *, version=None, context=None, report=None, legacy_picture_files=None):
    """Build a complete supported stream, failing on unmapped/invalid model data."""
    writer = Writer(version, report=report)
    document, context = prepare_export(document, context=context, report=report)
    prepare_binary_revision(document, version=writer.version, report=report)
    board = document.one('/Board')
    project_frames(board, report=report)
    if legacy_picture_files is None:
        legacy_picture_files = context.legacy_picture_files
    settings = board.one('Settings')
    preferences = [name for name in ('GridSnap', 'AssemblyWidth', 'CompOutlineWidth', 'CourtyardWidth')
                   if settings.child(name) is not None]
    if preferences:
        warn(report, 'application-preferences', 'dip',
             'DIP does not store these application preferences: '+', '.join(preferences),
             (settings,), recoverability='ASC and DIPXML retain the supplied choices; '
             'opening DIP uses the destination application preferences')
    if board.get('Selected', False):
        info(report, 'board-selection', 'dip', 'DIP omits board selection state', (board,),
             recoverability='the outline and its authored data remain')
    indices = OutputIndices(board)
    outputs, cached = component_outputs(board), definition_outputs(board)
    write_initial_sections(writer, document, indices=indices)
    write_base_components(writer, outputs)
    write_connections(writer, board)
    write_base_nets(writer, board, indices=indices)
    write_base_drawings(writer, board)
    write_groups(writer, board)
    write_sheet_layout(writer, board)
    write_base_tables(writer, board)
    write_base_pours(writer, board)
    write_board_dimensions(writer, board)
    write_display_settings(writer, document)
    write_rule_settings(writer, board)
    write_initial_results(writer, board, indices=indices)
    write_metadata(writer, board, outputs)
    write_cache(writer, board, cached)
    write_initial_pairs(writer, board, indices=indices)
    write_routing_extensions(writer, board)
    writer.fields(document.root, 'number', 'Xpos Ypos')
    write_layer_stack(writer, board, outputs)
    write_length_rules(writer, board, indices=indices)
    write_table_document_options(writer, board)
    write_meanders(writer, board)
    write_mask_settings(writer, board)
    write_pad_mask_overrides(writer, outputs)
    write_cache_masks(writer, cached)
    write_grid_extension(writer, board)
    write_global_markings(writer, board)
    for output in outputs:
        write_placed_extensions(writer, output)
    write_board_drawing_extensions(writer, board)
    write_document_spacing(writer, board)
    write_cache_extensions(writer, cached)
    write_display_extensions(writer, board)
    write_cache_pin_rotations(writer, cached)
    write_teardrops(writer, board, outputs)
    write_project(writer, board, outputs, cached, legacy_picture_files=legacy_picture_files)
    write_suppliers(writer, board, outputs, cached)
    write_variable_paths(writer, board, outputs)
    write_column_titles(writer, board)
    write_recent(writer, board, outputs, cached)
    return bytes(writer.buffer)
