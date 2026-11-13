"""PCB model units, pour connection display and component classifications."""
from ....common.catalog_codec import read_category_types, read_possible_names


def read_metadata_extensions(reader, board):
    components = board.one('Components').children('Component')
    pours = board.one('CopperPours').children('CopperPour')
    for component in components:
        model = component.one('Pattern/Model3D')
        if reader.header.version > 35:
            reader.field_into(model, 'Units', 'integer')
        else:
            reader.add_into(model, 'Units', -1)
    for pour in pours:
        if reader.header.version > 36:
            reader.field_into(pour, 'RatlineMode', 'integer')
        else:
            reader.add_into(pour, 'RatlineMode', 0)
    if reader.header.version <= 37:
        # These named settings did not exist in the older serialization.
        # Their current unassigned values match canonical modernization.
        for component in components:
            pattern = component.one('Pattern')
            for name in ('Datasheet', 'Manufacturer', 'Component_CategoryName'):
                reader.add_into(component, name, '')
            reader.add_into(component, 'Component_CategoryIndex', -1)
            reader.add_into(component, 'Component_CategoryTypes')
            reader.add_into(pattern, 'Mounting', -1)
            reader.add_into(pattern, 'Pattern_CategoryName', '')
            reader.add_into(pattern, 'Pattern_CategoryIndex', -1)
            reader.add_into(pattern, 'Pattern_CategoryTypes')
            reader.add_into(pattern, 'PossibleNames')
        return
    for component in components:
        pattern = component.one('Pattern')
        reader.field_into(pattern, 'Mounting', 'integer')
        reader.field_into(component, 'Datasheet', 'text')
        reader.field_into(component, 'Manufacturer', 'text')
        reader.field_into(pattern, 'Pattern_CategoryName', 'text')
        reader.field_into(pattern, 'Pattern_CategoryIndex', 'integer')
        read_category_types(reader, pattern, 'Pattern_CategoryTypes')
        reader.field_into(component, 'Component_CategoryName', 'text')
        reader.field_into(component, 'Component_CategoryIndex', 'integer')
        read_category_types(reader, component, 'Component_CategoryTypes')
        read_possible_names(reader, pattern)
