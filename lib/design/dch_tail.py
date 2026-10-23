"""Project settings, external resources and simulation extension records."""
from .dch_records import placed_components, cached_definitions, symbols, footprints


def _suppliers(r, part, *, prices):
    suppliers = part.add("Suppliers")
    for name in ("PartNumber", "Manufacturer", "Pattern", "Supplier", "SourceLocator", "Currency"):
        node = r.field(suppliers, name, "text")
        if name == "SourceLocator":
            node.annotations["asc_omit"] = "stored supplier locator is not emitted by format schematic ASC"
    if prices:
        quotes = suppliers.add("Prices")
        quotes.annotations["asc_omit"] = "stored price breaks are not emitted by format schematic ASC"
        for _ in range(r.count("supplier price breaks")):
            quotes.add("Quote", r.argument('integer'), r.argument('number'))


def read_project_extensions(r, schematic):
    parts = placed_components(schematic)
    definitions = tuple(cached_definitions(schematic))
    if r.header.version >= 41:
        settings = schematic.child("Settings")
        r.field(settings, "PartFontSize", "integer")
        r.field(settings, "PartFontColor", "color")
        r.field(settings, "UsePartFontColor", "boolean")
        for part in symbols(schematic):
            for pin in part.child("Pins").children("Pin"):
                for name in ("PinNameRotate", "PinNumRotate"):
                    r.field(pin, name, "integer")
    else:
        for part in symbols(schematic):
            for pin in part.child("Pins").children("Pin"):
                for name in ("PinNameRotate", "PinNumRotate"):
                    pin.add(name, 0).annotations["default_for_version"] = r.header.version
    if r.header.version >= 42:
        for shape in schematic.child("Shapes").children("Shape"):
            for name in ("Picture_Width", "Picture_Height", "Picture_Transparent"):
                r.field(shape, name, "number")
            r.field(shape, "Picture_File", "text")
            r.field(shape, "Picture_Proportions", "boolean")
        for pattern in footprints(schematic):
            r.field(pattern.child('Model3D'), 'KeepPins', 'boolean')
    else:
        
        # Their source bitmap index is separate retained data, not a filename.
        for shape in schematic.child('Shapes').children('Shape'):
            for name, value in (('Picture_Width', 1), ('Picture_Height', 1),
                                ('Picture_Transparent', 0), ('Picture_File', ''),
                                ('Picture_Proportions', False)):
                shape.add(name, value).annotations['default_for_version'] = r.header.version
        for pattern in footprints(schematic):
            pattern.child('Model3D').add('KeepPins', False).annotations['default_for_version'] = r.header.version
    if r.header.version >= 43:
        for part in parts:
            _suppliers(r, part, prices=True)
        for definition in definitions:
            _suppliers(r, definition.child("Part"), prices=False)
    else:
        for part in (*parts, *(definition.child('Part') for definition in definitions)):
            part.add('Suppliers').annotations['default_for_version'] = r.header.version
    if r.header.version >= 44:
        for part in parts:
            r.field(part.child("Suppliers"), "MainSupplier", "boolean")
    if r.header.version >= 45:
        for part in parts:
            r.field(part, "LibPath_Variable", "text")
            r.field(part.child("Pattern").child("Model3D"), "Model3DFile_Variable", "text")
        for shape in schematic.child("Shapes").children("Shape"):
            r.field(shape, "Picture_File_Variable", "text")
        for name, item in (("ProjectLibs_Folders", "Folder"), ("ProjectLibs_Libs", "Lib")):
            for node in schematic.child(name).children(item):
                r.field(node, "VariablePath", "text")
        cache = schematic.child("CacheLib")
        if cache:
            for slot in cache.child("Slots").children("Slot"):
                # format stores these paths on the first variant in a slot.
                # Preserve them at the slot as well so empty slots remain
                # inspectable without inventing a definition.
                path, model_path = r.argument('text'), r.argument('text')
                slot.add("VariablePath", path)
                variants = slot.children("Definition")
                if variants:
                    variants[0].child("Pattern").child("Model3D").add("Model3DFile_Variable", model_path)
                else:
                    slot.add("Model3DFile_Variable", model_path)
        r.field(schematic, "ProjectDir", "text")
    if r.header.version >= 46:
        simulation = schematic.add("ssimulator")
        mode = r.field(simulation, "tp", "integer")
        mode.set_values(mode.values[0] & 255)  # format truncates the integer to a byte.
        count = r.count("simulation signals")
        signals = simulation.add("signals", count)
        for _ in range(count):
            signal = signals.add("signal")
            for name in ("signal_tp", "signal_num"):
                r.field(signal, name, "integer")
            r.field(signal, "signal_display_name", "text")
            for name in ("signal_plotted", "signal_visible"):
                r.field(signal, name, "boolean")
            r.field(signal, "signal_color", "color")
        for name in ("sim_ac", "sim_dc", "sim_tran", "sim_noise"):
            count = r.count("simulation settings")
            node = simulation.add(name, count)
            for _ in range(count):
                node.add("pt", r.argument('text'))
        r.field(simulation, "gndnum", "integer")
        r.field(simulation, "gndname", "text")
    else:
        from .simulation import default_simulator
        simulation=schematic.append(default_simulator())
        simulation.annotations['default_for_version']=r.header.version
