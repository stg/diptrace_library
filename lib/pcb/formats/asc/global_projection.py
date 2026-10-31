"""Current board choices, marking defaults and schematic hierarchy for ASC."""
from ....common.conversion import info, warn
from ....common.model import Element
from ...model import board_records, markings, hierarchy_records, assembly_variants
from .document_settings import BOARD_ALIASES
from .projection import collection, fields, value


CACHE_FIELDS = frozenset(('ProjectLibs_Name', 'ProjectLibs_Type', 'ProjectLibs_Content',
                         'ProjectLibs_Sorted', 'DesignCache_Count'))
BOARD_FIELDS = frozenset(board_records.BOARD_FIELDS)-CACHE_FIELDS-{'CompFontMono', 'SchemNetClasses'}


def project_globals(board, *, report=None):
    """Generate this section only; geometry, rules and cache have their own views."""
    output = Element('Board')
    fields(board, output, exclude=board.schema.fields.keys()-BOARD_FIELDS,
           names={current: saved for saved, current in BOARD_ALIASES.items()})
    user_fields = output.add('Userfields_Global')
    for field in collection(board, 'Userfields_Global', markings.GLOBAL_USER_FIELDS, markings.GLOBAL_USER_FIELD):
        row = user_fields.add('Userfield')
        fields(field, row)
        row.add('Value', field['Value'])
    variants = output.add('AssemblyVariants')
    for variant in collection(board, 'AssemblyVariants', assembly_variants.VARIANTS, assembly_variants.VARIANT):
        variants.add('AssemblyVariant', variant['Name'])
    sheets = output.add('Hierarchy_Sheets')
    for sheet in collection(board, 'HierarchySheets', hierarchy_records.SHEETS, hierarchy_records.SHEET):
        record = sheets.add('HSheet', sheet['Name'], sheet['Number'])
        for block in collection(sheet, 'UpdateIds', hierarchy_records.BLOCKS, hierarchy_records.BLOCK):
            record.add('pt', block['Id'], block['Name'])
    for name, baseline in (('CompFontMono', False), ('SchemNetClasses', False), ('ShieldGroup', -1)):
        if board.get(name, baseline) != baseline:
            warn(report, 'board-'+name.lower(), 'asc', 'PCB ASC omits board '+name, (board,))
        elif name in ('CompFontMono', 'SchemNetClasses') and board.child(name) is not None:
            info(report, 'board-default-options', 'asc', 'PCB ASC omits the default board '+name, (board,))
    if value(board, 'Selected'):
        info(report, 'board-selection', 'asc', 'ASC omits board selection state', (board,),
             recoverability='board data and outline geometry are retained')
    return output
