"""Explicit resource paths stored in the document; no companion discovery."""
from ....common.conversion import import_notice
from ..path_variables import variable_paths


def _legacy_variable_paths(board):
    """Express older literal-only paths in the current path vocabulary."""
    changed = []

    def complete(owner, variable, literal):
        if owner.child(variable) is None:
            owner.add(variable, literal)
            if literal:
                changed.append(owner)

    for owner, variable, literal in variable_paths(board):
        complete(owner, variable, literal)
    if changed:
        import_notice('info', 'legacy-literal-paths',
                      'Initialized current variable paths from the stored literal paths.', changed,
                      recoverability='literal strings remain; no external files or path variables were consulted')


def read_variable_paths(reader, board):
    """Read schema-53 paths and return its following conditional-section switch."""
    if reader.header.version <= 52:
        _legacy_variable_paths(board)
        return False
    reader.field(board, 'RelSchem_Variable', 'text')
    for component in board.select('Components/Component'):
        reader.field(component, 'LibPath_Variable', 'text')
        reader.field(component.one('Pattern/Model3D'), 'Model3DFile_Variable', 'text')
    for shape in board.select('Shapes/Shape'):
        reader.field(shape, 'Picture_File_Variable', 'text')
    for container, kind in (('ProjectLibs_Folders', 'Folder'), ('ProjectLibs_Libs', 'Lib')):
        for path in board.select(container+'/'+kind):
            reader.field(path, 'VariablePath', 'text')
    for slot in board.select('CacheLib/Slots/Slot'):
        reader.field(slot, 'VariablePath', 'text')
        definitions = slot.children('Definition')
        owner = definitions[0].one('Pattern/Model3D') if definitions else slot
        reader.field(owner, 'Model3DFile_Variable', 'text')
    reader.field(board, 'ProjectDir', 'text')
    reader.field(board.one('Panel'), 'PanelizeSingle', 'boolean')
    return reader.boolean()


def read_column_titles(reader, board):
    if reader.header.version > 53:
        for column in board.select('Tables/Table/AutoUpdate/Columns/Column'):
            reader.field(column, 'Title', 'text')
