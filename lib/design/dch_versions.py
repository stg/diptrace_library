"""Recent schematic revisions mapped directly to editable public facts."""
from .schematic_fonts import binary_fonts, complete_fonts, compatibility_size
from .simulation import OPTION_FIELDS, complete_options


def xml_application_version(version):
    """A verified XML dialect capable of the selected feature subset."""
    if version not in range(46, 53):
        raise ValueError('XML output supports target schemas 46 through 52')
    if version == 46:
        return '4.3.0.5'
    if version < 49:
        return '4.9.5.0'
    return '5.2.0.1' if version < 52 else '5.3.5.1'


def read_extensions(reader, schematic):
    complete_fonts(schematic)
    simulator = schematic.one('ssimulator')
    complete_options(simulator)
    version = reader.header.version
    if version >= 49:
        reader.field(schematic.one('Settings'), 'NetNameFontSize', 'integer', replace=True)
    if version >= 50:
        rows = simulator.one('sim_digital')
        for row in list(rows.children()):
            row.detach()
        count = reader.count('digital simulation arguments')
        rows.set_values(count)
        for _ in range(count):
            rows.add('pt', reader.argument('text'))
        for group, name, kind, default in OPTION_FIELDS:
            reader.field(simulator.one(group), name, kind, replace=True)
    if version >= 51:
        for shape in schematic.select('Shapes/Shape'):
            reader.field(shape, 'PictureFlipped', 'boolean', replace=True)
    if version >= 52:
        for node, size, mono in binary_fonts(schematic):
            if mono:
                reader.field(node, mono, 'boolean', replace=True)
            reader.field(node, size, 'number', replace=True)


def write_extensions(writer, schematic):
    if writer.version >= 49:
        writer.integer(compatibility_size(schematic.one('Settings').scalar('NetNameFontSize', 4)))
    if writer.version >= 50:
        simulator = schematic.one('ssimulator')
        writer.rows(simulator.one('sim_digital'), 'pt', 'text')
        for group, name, kind, default in OPTION_FIELDS:
            writer.field(simulator.one(group), name, kind)
    if writer.version >= 51:
        for shape in schematic.select('Shapes/Shape'):
            writer.boolean(shape.scalar('PictureFlipped', False))
    if writer.version >= 52:
        for node, size, mono in binary_fonts(schematic):
            if mono:
                writer.boolean(node.scalar(mono, False))
            writer.field(node, size, 'number')
