"""Binary project choices, resource paths and later current-property records."""
from itertools import chain

from ....common.font_codec import write_font_properties
from ....common.supplier_codec import write_supplier
from ...model import markings, assembly_variants, board_records
from ..output_validation import check_tree
from .write_cache import (write_cache_model_options, write_cache_suppliers, write_cache_paths,
                          write_cache_shields, cache_font_records)
from .write_components import component_font_records
from .write_document import write_table_settings, document_font_records
from .write_graphics import write_picture_sources, board_font_records


def write_global_markings(writer, board):
    for name in markings.NAMES:
        for side in markings.SIDES:
            writer.fields(board, 'integer', f'{name}_Global_{side}Show {name}_Global_{side}Align')
    if (source := board.child('Userfields_Global')) is not None:
        check_tree(source, markings.GLOBAL_USER_FIELDS, destination='DIP')
    fields = board.select('Userfields_Global/UserField')
    writer.integer(len(fields))
    for field in fields:
        writer.fields(field, 'text', 'Name Value')
        writer.fields(field, 'integer', 'SilkShow SilkAlign AssyShow AssyAlign')


def write_project(writer, board, outputs, cached, *, legacy_picture_files=None):
    if (variants := board.child('AssemblyVariants')) is not None:
        check_tree(variants, assembly_variants.VARIANTS, destination='DIP')
    writer.rows(board.child('AssemblyVariants'), 'AssemblyVariant', 'text')
    for output in outputs:
        writer.rows(output.component.child('AssemblyExclude'), 'Item', 'integer')
    for table in board.select('Tables/Table'):
        write_table_settings(writer, table)
    write_picture_sources(writer, board, legacy_picture_files=legacy_picture_files)
    writer.scalar(board, 'CompRotate', 'boolean', default=True)
    panel = board.one('Panel')
    check_tree(panel, board_records.PANEL, destination='DIP')
    writer.field(panel, 'Type', 'integer')
    writer.fields(panel, 'number', 'TabWidth TabRadius TabStep HoleDiam HoleStep HoleInset HoleKeepout')
    writer.field(panel, 'TabsDone', 'boolean')
    for name in ('HorzTabsX', 'VertTabsY'):
        writer.rows(panel.child(name), 'Item', 'number')
    writer.field(panel, 'CombinedRadius', 'number')
    writer.field(panel, 'KeepMaterial', 'boolean')
    writer.field(panel, 'BorderTabs', 'integer')
    for output in outputs:
        writer.field(output.pattern.one('Model3D'), 'KeepPins', 'boolean')
    write_cache_model_options(writer, cached)


def write_suppliers(writer, board, outputs, cached):
    for output in outputs:
        write_supplier(writer, output.component, prices=True)
    write_cache_suppliers(writer, cached)
    for table in board.select('Tables/Table'):
        writer.scalar(table, 'Supplier', 'text', default='')
    for output in outputs:
        supplier = output.component.child('Suppliers')
        writer.boolean(supplier.get('MainSupplier', False) if supplier is not None else False)


def write_variable_paths(writer, board, outputs):
    writer.scalar(board, 'RelSchem_Variable', 'text', default='')
    for output in outputs:
        writer.scalar(output.component, 'LibPath_Variable', 'text', default='')
        writer.scalar(output.pattern.one('Model3D'), 'Model3DFile_Variable', 'text', default='')
    for shape in board.select('Shapes/Shape'):
        writer.scalar(shape, 'Picture_File_Variable', 'text', default='')
    for container, kind in (('ProjectLibs_Folders', 'Folder'), ('ProjectLibs_Libs', 'Lib')):
        for path in board.select(container+'/'+kind):
            writer.scalar(path, 'VariablePath', 'text', default='')
    write_cache_paths(writer, board)
    writer.scalar(board, 'ProjectDir', 'text', default='')
    writer.field(board.one('Panel'), 'PanelizeSingle', 'boolean')
    writer.boolean(False)  # Ordinary document saving clears interactive routing state.


def _pair_shields(pair):
    for center in pair.select('Segments/Segment/CenterPoints/CenterPoint'):
        for name in ('PosShieldGroup', 'NegShieldGroup'):
            yield center, name
        for side in ('Pos', 'Neg'):
            for point in center.select(side+'Points/'+side+'Point'):
                yield point, 'ShieldGroup'
    for side in ('Pos', 'Neg'):
        for point in pair.select(side+'SeparateTraces/'+side+'Trace/Points/Point'):
            yield point, 'ShieldGroup'


def _shield_records(board, outputs):
    for output in outputs:
        yield output.component, 'ShieldGroup'
        for node in chain(output.pads, output.drawings):
            yield node, 'ShieldGroup'
    for point in board.select('Nets/Net/Traces/Trace/Points/Point'):
        yield point, 'ShieldGroup'
    for pair in board.select('DifferentialPairs/DifferentialPair'):
        yield from _pair_shields(pair)
    for pair in board.select('RemovedDifferentialPairs/RemovedDifferentialPair'):
        yield from _pair_shields(pair)
    for pour in board.select('CopperPours/CopperPour'):
        yield pour, 'ShieldGroup'


def _shields(writer, board, outputs, cached):
    for node, name in _shield_records(board, outputs):
        writer.field(node, name, 'integer')
    writer.field(board, 'ShieldGroup', 'integer')
    write_cache_shields(writer, cached)


def write_recent(writer, board, outputs, cached):
    if writer.version >= 55:
        writer.fields(board.one('Panel'), 'number', 'LeftGap RightGap TopGap BottomGap')
    if writer.version >= 56:
        for net in board.select('Nets/Net'):
            writer.field(net, 'HiddenId', 'integer')
    if writer.version >= 57:
        _shields(writer, board, outputs, cached)
    if writer.version >= 58:
        for pour in board.select('CopperPours/CopperPour'):
            writer.field(pour, 'TraceShieldGroup', 'integer')
    if writer.version >= 59:
        for shape in board.select('Shapes/Shape'):
            writer.field(shape, 'PictureFlipped', 'boolean')
    if writer.version >= 60:
        writer.scalar(board, 'SchemNetClasses', 'boolean', default=False)
    if writer.version >= 61:
        write_font_properties(writer, chain(component_font_records(outputs), board_font_records(board),
                                           document_font_records(board), cache_font_records(cached)))
    if writer.version >= 62:
        for net in board.select('Nets/Net'):
            writer.field(net, 'AllowLoops', 'boolean')
