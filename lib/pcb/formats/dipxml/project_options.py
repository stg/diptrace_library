"""Project-library header defaults and independent document option projection."""
from ....common import library_metadata
from ....common.conversion import info, warn
from ....common.xml import set_attribute
from ....common.xml_library_output import project_project_libraries
from ..output_validation import check_tree


# Canonical XML imports initialize this browser header rather than reading it.
# Ordinary ASC/XML conversions expose these default values independently of
# the actual project search paths and cached component definitions.
PROJECT_LIBRARY_DEFAULTS = {'ProjectLibs_Name': 'Project Libraries', 'ProjectLibs_Type': 2, 'ProjectLibs_Content': 0}
ASSEMBLY_CHOICES = ('AssyObjSilk', 'AssyObjBorders', 'AssyObjMarking', 'AssyObjBoard', 'AssyObjPads')
DOCUMENT_FIELDS = ('UserField1', 'UserField2')


def project_paths(board, *, report=None):
    for name, schema in (('ProjectLibs_Folders', library_metadata.PROJECT_FOLDERS),
                         ('ProjectLibs_Libs', library_metadata.PROJECT_LIBRARIES)):
        if (source := board.child(name)) is not None:
            check_tree(source, schema, destination='DIPXML')
    result = project_project_libraries(board)
    supplied = [board.one(name) for name in PROJECT_LIBRARY_DEFAULTS if name in board]
    if supplied:
        if result.child('Sorted') is None:
            set_attribute(result, 'Sorted', False)
            info(report, 'project-library-sort-default', 'dipxml',
                 'XML initializes an unavailable project-library sorting choice to false', (board,))
        defaults, changed = [], []
        for source in supplied:
            (defaults if board[source.kind] == PROJECT_LIBRARY_DEFAULTS[source.kind] else changed).append(source)
        if defaults:
            info(report, 'project-library-header-default', 'dipxml',
                 'XML regenerates the standard project-library browser header', defaults)
        if changed:
            warn(report, 'project-library-header', 'dipxml',
                 'XML replaces independent project-library header values with its standard header', changed)
    return result


def report_document_options(board, *, report=None):
    choices = [board.one(name) for name in ASSEMBLY_CHOICES if name in board]
    if choices:
        warn(report, 'assembly-object-choices', 'dipxml',
             'XML omits independent assembly-object choices; assembly display settings remain', choices)
    supplied = [board.one(name) for name in DOCUMENT_FIELDS if name in board]
    empty = [node for node in supplied if not board[node.kind]]
    content = [node for node in supplied if board[node.kind]]
    if empty:
        info(report, 'empty-document-fields', 'dipxml', 'XML omits empty legacy document fields', empty)
    if content:
        warn(report, 'document-fields', 'dipxml', 'XML omits the two independent legacy document text fields', content)
