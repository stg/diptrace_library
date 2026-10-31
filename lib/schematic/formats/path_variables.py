"""Apply shared path-variable choices to a detached schematic export view."""
from ...common.path_variables import PathVariables


def prepare_variable_paths(schematic, choices, *, project_dir):
    """Refresh the format export path pairs on an already detached view."""
    def update(parent, variable_name, actual):
        previous = parent.scalar(variable_name, '')
        parent.set_field(variable_name, choices.select(previous, actual, project_dir=project_dir))
    for part in schematic.select('Components/Part'):
        if part.scalar('Enabled') not in (False, 'N'):
            update(part, 'LibPath_Variable', part.scalar('LibPath'))
            model = part.one('Pattern/Model3D')
            update(model, 'Model3DFile_Variable', model.scalar('Model3DFile'))
    for shape in schematic.select('Shapes/Shape'):
        if shape.scalar('Enabled') not in (False, 'N'):
            update(shape, 'Picture_File_Variable', shape.scalar('Picture_File'))
    if schematic.scalar('ProjectLibs_Type') == 2:
        for name, kind in (('ProjectLibs_Folders', 'Folder'), ('ProjectLibs_Libs', 'Lib')):
            for record in schematic.select(name+'/'+kind):
                update(record, 'VariablePath', record.values[0])
    for slot in schematic.select('CacheLib/Slots/Slot'):
        if slot.children('Definition'):
            update(slot, 'VariablePath', slot.values[1])
