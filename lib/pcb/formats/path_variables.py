"""Resource-path scopes owned by a PCB, without external resource lookup."""


def variable_paths(board):
    """Yield each applicable owner, variable field and literal path value."""
    yield board, 'RelSchem_Variable', board.get('RelSchem', '')
    for component in board.select('Components/Component'):
        if component.get('Enabled', True):
            yield component, 'LibPath_Variable', component.get('LibPath', '')
            if (model := component.one('Pattern').child('Model3D')) is not None:
                yield model, 'Model3DFile_Variable', model.get('Model3DFile', '')
    for shape in board.select('Shapes/Shape'):
        if shape.get('Enabled', True):
            yield shape, 'Picture_File_Variable', shape.get('Picture_File', '')
    if board.get('ProjectLibs_Type', 0) == 2:
        for container, kind in (('ProjectLibs_Folders', 'Folder'), ('ProjectLibs_Libs', 'Lib')):
            for path in board.select(container+'/'+kind):
                yield path, 'VariablePath', path.values[0]
    for slot in board.select('CacheLib/Slots/Slot'):
        if slot.children('Definition'):
            yield slot, 'VariablePath', slot.values[1]


def prepare_variable_paths(board, choices, *, project_dir):
    """Apply explicit caller choices to a detached output view."""
    for owner, name, literal in variable_paths(board):
        owner[name] = choices.select(owner.get(name, ''), literal, project_dir=project_dir)
