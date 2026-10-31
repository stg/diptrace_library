"""PCB model units, pour connection display and component classifications."""
from ....common.catalog_codec import read_category_types, read_possible_names


def read_metadata_extensions(reader, board):
    components = board.one('Components').children('Component')
    pours = board.one('CopperPours').children('CopperPour')
    for component in components:
        model = component.one('Pattern/Model3D')
        if reader.header.version > 35:
            reader.field(model, 'Units', 'integer')
        else:
            model.add('Units', -1)
    for pour in pours:
        if reader.header.version > 36:
            reader.field(pour, 'RatlineMode', 'integer')
        else:
            pour.add('RatlineMode', 0)
    if reader.header.version <= 37:
        # These named settings did not exist in the older serialization.
        # Their current unassigned values match canonical modernization.
        for component in components:
            pattern = component.one('Pattern')
            for name in ('Datasheet', 'Manufacturer', 'Component_CategoryName'):
                component.add(name, '')
            component.add('Component_CategoryIndex', -1)
            component.add('Component_CategoryTypes')
            pattern.add('Mounting', -1)
            pattern.add('Pattern_CategoryName', '')
            pattern.add('Pattern_CategoryIndex', -1)
            pattern.add('Pattern_CategoryTypes')
            pattern.add('PossibleNames')
        return
    for component in components:
        pattern = component.one('Pattern')
        reader.field(pattern, 'Mounting', 'integer')
        reader.field(component, 'Datasheet', 'text')
        reader.field(component, 'Manufacturer', 'text')
        reader.field(pattern, 'Pattern_CategoryName', 'text')
        reader.field(pattern, 'Pattern_CategoryIndex', 'integer')
        read_category_types(reader, pattern, 'Pattern_CategoryTypes')
        reader.field(component, 'Component_CategoryName', 'text')
        reader.field(component, 'Component_CategoryIndex', 'integer')
        read_category_types(reader, component, 'Component_CategoryTypes')
        read_possible_names(reader, pattern)
