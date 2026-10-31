"""Explicit ownership of document-level PCB XML output facts."""
from ...model import definitions, markings
from ..errors import PcbError
from ..output_validation import check
from .project_options import PROJECT_LIBRARY_DEFAULTS, ASSEMBLY_CHOICES, DOCUMENT_FIELDS


FIELD_OWNERS = {
    'outline': frozenset('Enabled Selected Locked PanelExclude ShieldGroup'.split()),
    'markings': frozenset(markings.GLOBAL_FIELDS) | frozenset('''CompRotate PatternFontVector
        CompFontMono CompFontName CompFontSize PatternFontWidth PatternFontScale'''.split()),
    'settings': frozenset('''OriginX OriginY RelSchem RelSchem_Variable Toplock Bottomlock
        LockNetStructure SchemNetClasses ProjectDir'''.split()),
    'panel': frozenset('PanelX PanelY PanelDX PanelDY RailShow RailLeft RailRight RailTop RailBottom'.split()),
    'rules': frozenset(('LayerStackName', 'ClassToClass', 'DefaultClass')),
    'library': frozenset(('DesignCache_Count',)),
    'project_paths': frozenset(('ProjectLibs_Sorted',)),
    'project_header': frozenset(PROJECT_LIBRARY_DEFAULTS),
    'document_options': frozenset((*ASSEMBLY_CHOICES, *DOCUMENT_FIELDS)),
}
CHILD_OWNERS = {
    'AssemblyVariants': 'resources', 'Layers': 'resources', 'ViaStyles': 'resources',
    'HierarchySheets': 'resources', 'Groups': 'resources',
    'Ratlines': 'ratlines', 'DesignErrors': 'results',
    'NetClasses': 'classes', 'Nets': 'nets', 'DifferentialPairs': 'pairs', 'RemovedDifferentialPairs': 'pairs',
    'LayerStackItems': 'rules', 'ClassClearances': 'rules', 'DRC': 'rules', 'LastDRC': 'rules',
    'MainLengthRule': 'lengths', 'LengthRules': 'lengths',
    'Points': 'outline', 'NonSignals': 'non_signals', 'Shapes': 'drawings',
    'CopperPours': 'pours', 'Tables': 'tables', 'Dimensions': 'dimensions',
    'Components': 'components', 'Settings': 'settings', 'SheetSettings': 'sheet', 'Panel': 'panel',
    'ConnectivityCheck': 'connectivity', 'CacheLib': 'library', 'DesignCache_Links': 'library',
    'ProjectLibs_Folders': 'project_paths', 'ProjectLibs_Libs': 'project_paths', 'Userfields_Global': 'markings',
}
def validate_document(document):
    if document.representation != 'pcb':
        raise PcbError('PCB XML projection requires the editable PCB model')
    check(document.root, definitions.DOCUMENT, destination='DIPXML')
    board = document.one('/Board')
    check(board, definitions.BOARD, destination='DIPXML')
    fields = frozenset().union(*FIELD_OWNERS.values())
    for name in definitions.BOARD.fields:
        if name in board and name not in fields:
            raise PcbError(f'{board.path}: {name} needs a PCB XML output mapping')
    for child in board.children():
        if child.kind not in definitions.BOARD.fields and child.kind not in CHILD_OWNERS:
            raise PcbError(f'{child.path}: section needs a PCB XML output mapping')
    return board
