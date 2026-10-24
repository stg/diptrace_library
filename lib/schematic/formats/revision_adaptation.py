"""Destination revision choices applied only to detached export views."""
from ...common.conversion import (warn)
from ..model.fonts import (all_fonts, complete_fonts, compatibility_size)
from ..model.simulation import (OPTION_FIELDS, complete_options, argument_values)


def prepare_revisions(schematic, *, destination, version=46, report=None):
    complete_fonts(schematic)
    simulator = schematic.one('ssimulator')
    complete_options(simulator)
    ascii_output = destination == 'asc'
    fractional = ascii_output or version >= 52
    mono_supported = not ascii_output and version >= 52
    rounded, mono = [], []
    for node, size, choice in all_fonts(schematic):
        field = node.child(size)
        if field is not None and not fractional:
            value = field.values[0]
            result = compatibility_size(value)
            if result != value:
                rounded.append(field)
                field.set_values(result)
        if choice and node.scalar(choice, False):
            if not mono_supported:
                mono.append(node.one(choice))
                node.set_field(choice, False)
        if ascii_output and choice:
            node.one(choice).detach()
    if rounded:
        warn(report, 'fractional-font-size', destination,
             'destination font sizes are rounded to integral values', rounded)
    if mono:
        warn(report, 'monospaced-font', destination,
             'destination omits monospaced vector-font selection', mono)
    if ascii_output or version < 49:
        font = schematic.one('Settings/NetNameFontSize')
        if font.values[0] != 4:
            warn(report, 'net-name-font', destination,
                 'destination omits the global net-name font size; its default is 4', [font])
        if ascii_output:
            font.detach()
    if ascii_output or version < 50:
        changed = [simulator.one(group+'/'+name) for group, name, kind, default in OPTION_FIELDS
                   if simulator.one(group).scalar(name) != default]
        rows = simulator.one('sim_digital')
        if [value.value for value in argument_values(rows)] != ['#', '#', '#', '-']:
            changed.append(rows)
        if changed:
            warn(report, 'simulator-options', destination,
                 'destination omits digital simulation arguments and advanced simulator options', changed)
        if not ascii_output and simulator.scalar('tp') == 10:
            warn(report, 'digital-simulation', destination,
                 'digital simulation is disabled for a destination schema below 50', [simulator.one('tp')])
            simulator.set_field('tp', 0)
        if ascii_output:
            for name in ('sim_digital', *dict.fromkeys(group for group, *_ in OPTION_FIELDS)):
                simulator.one(name).detach()
    elif destination == 'dchxml' and version < 52:
        rows = simulator.one('sim_digital')
        if [value.value for value in argument_values(rows)] != ['#', '#', '#', '-']:
            warn(report, 'dchxml-reader-digital-arguments', destination,
                 '5.2 XML readers reset digital simulation arguments even though they are written in the file', [rows],
                 recoverability='the XML file and authoring model retain the arguments; use a current reader to load them')
    picture_flip_supported = ((destination == 'dch' and version >= 51)
                              or (destination == 'dchxml' and version >= 52))
    if not picture_flip_supported:
        flipped = [shape.one('PictureFlipped') for shape in schematic.select('Shapes/Shape')
                   if shape.scalar('PictureFlipped', False)]
        if flipped:
            warn(report, 'picture-flipped', destination,
                 'destination omits the drawing picture-flip setting', flipped)
        if ascii_output:
            for shape in schematic.select('Shapes/Shape'):
                shape.one('PictureFlipped').detach()
