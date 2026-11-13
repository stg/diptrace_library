"""Project settings, external resources and simulation extension records."""
from ...model.traversal import (placed_components, cached_definitions, symbols, footprints)
from ...model.simulation import ARGUMENT_SCHEMAS
from ....common.supplier_codec import read_supplier


def read_simulation_arguments(reader, group):
    names = tuple(ARGUMENT_SCHEMAS[group.kind].fields)
    for index in range(reader.count('simulation arguments')):
        reader.add_into(group, names[index] if index < len(names) else 'Item', reader.argument('text'))


def _suppliers(r, part, *, prices):
    read_supplier(r, part, prices=prices)


def read_project_extensions(r, schematic):
    parts = placed_components(schematic)
    definitions = tuple(cached_definitions(schematic))
    if r.header.version >= 41:
        settings = schematic.child("Settings")
        r.field_into(settings, "PartFontSize", "integer")
        r.field_into(settings, "PartFontColor", "color")
        r.field_into(settings, "UsePartFontColor", "boolean")
        for part in symbols(schematic):
            for pin in part.child("Pins").children("Pin"):
                for name in ("PinNameRotate", "PinNumRotate"):
                    r.field_into(pin, name, "integer")
    else:
        for part in symbols(schematic):
            for pin in part.child("Pins").children("Pin"):
                for name in ("PinNameRotate", "PinNumRotate"):
                    r.add_into(pin, name, 0)
    if r.header.version >= 42:
        for shape in schematic.child("Shapes").children("Shape"):
            for name in ("Picture_Width", "Picture_Height", "Picture_Transparent"):
                r.field_into(shape, name, "number")
            r.field_into(shape, "Picture_File", "text")
            r.field_into(shape, "Picture_Proportions", "boolean")
        for pattern in footprints(schematic):
            r.field_into(pattern.child('Model3D'), 'KeepPins', 'boolean')
    else:

        # Their source bitmap index is separate retained data, not a filename.
        for shape in schematic.child('Shapes').children('Shape'):
            for name, value in (('Picture_Width', 1), ('Picture_Height', 1),
                                ('Picture_Transparent', 0), ('Picture_File', ''),
                                ('Picture_Proportions', False)):
                r.add_into(shape, name, value)
        for pattern in footprints(schematic):
            r.add_into(pattern.child('Model3D'), 'KeepPins', False)
    if r.header.version >= 43:
        for part in parts:
            _suppliers(r, part, prices=True)
        for definition in definitions:
            _suppliers(r, definition.child("Part"), prices=False)
    else:
        for part in (*parts, *(definition.child('Part') for definition in definitions)):
            r.add_into(part, 'Suppliers')
    if r.header.version >= 44:
        for part in parts:
            r.field_into(part.child("Suppliers"), "MainSupplier", "boolean")
    if r.header.version >= 45:
        for part in parts:
            r.field_into(part, "LibPath_Variable", "text")
            r.field_into(part.child("Pattern").child("Model3D"), "Model3DFile_Variable", "text")
        for shape in schematic.child("Shapes").children("Shape"):
            r.field_into(shape, "Picture_File_Variable", "text")
        for name, item in (("ProjectLibs_Folders", "Folder"), ("ProjectLibs_Libs", "Lib")):
            for node in schematic.child(name).children(item):
                r.field_into(node, "VariablePath", "text")
        cache = schematic.child("CacheLib")
        if cache:
            for slot in cache.child("Slots").children("Slot"):
                # format stores these paths on the first variant in a slot.
                # Preserve them at the slot as well so empty slots remain
                # inspectable without inventing a definition.
                path, model_path = r.argument('text'), r.argument('text')
                r.add_into(slot, "VariablePath", path)
                variants = slot.children("Definition")
                if variants:
                    r.add_into(variants[0].child("Pattern").child("Model3D"), "Model3DFile_Variable", model_path)
                else:
                    r.add_into(slot, "Model3DFile_Variable", model_path)
        r.field_into(schematic, "ProjectDir", "text")
    if r.header.version >= 46:
        simulation = r.add(schematic, "ssimulator")
        mode = r.field(simulation, "tp", "integer")
        mode.set_values(mode.values[0] & 255)  # format truncates the integer to a byte.
        count = r.count("simulation signals")
        signals = r.add(simulation, "signals")
        for _ in range(count):
            signal = r.add(signals, "signal")
            for name in ("signal_tp", "signal_num"):
                r.field_into(signal, name, "integer")
            r.field_into(signal, "signal_display_name", "text")
            for name in ("signal_plotted", "signal_visible"):
                r.field_into(signal, name, "boolean")
            r.field_into(signal, "signal_color", "color")
        for name in ("sim_ac", "sim_dc", "sim_tran", "sim_noise"):
            read_simulation_arguments(r, r.add(simulation, name))
        r.field_into(simulation, "gndnum", "integer")
        r.field_into(simulation, "gndname", "text")
    else:
        from ...model.simulation import (default_simulator)
        simulation=schematic.append(default_simulator())
