"""Schematic XML symbol selection and key policy over the shared serializer."""
from ....common import xml_symbol_output
from ...model.pad_keys import project_pad_id
from ...model.local_keys import project_key, public_keys, reserved_keys
from .fonts import uses_physical_width


def project_symbol_pin(pin, *, units, pad_keys=None, group_keys=None, version=46):
    return xml_symbol_output.project_symbol_pin(
        pin, units=units, pad_id=project_pad_id(pin, pad_keys),
        group=project_key(pin, 'Group', pin.scalar('Group'), group_keys),
        fractional_font=version >= 52, physical_font_width=uses_physical_width(version))


def project_symbol_drawing(shape, *, units, group_keys=None, version=46):
    return xml_symbol_output.project_symbol_drawing(
        shape, units=units, group=project_key(shape, 'Group', shape.scalar('Group'), group_keys),
        fractional_font=version >= 52, physical_font_width=uses_physical_width(version))


def project_symbol(part, *, units, pattern=None, pattern_style=None, datasheet='', pad_keys=None, version=46):
    """Select current content without inferring instance geometry."""
    groups = part.select('Groups/pt')
    group_keys = public_keys(groups, reserved_keys(
        [*part.select('Pins/Pin'), *part.select('Shapes/Shape')], ('Group',)))
    pins = (project_symbol_pin(pin, units=units, pad_keys=pad_keys, group_keys=group_keys, version=version)
            for pin in part.select('Pins/Pin') if pin.scalar('Enabled'))
    drawings = (project_symbol_drawing(shape, units=units, group_keys=group_keys, version=version)
                for shape in part.select('Shapes/Shape')
                if shape.scalar('Enabled'))
    connections = pattern.select('InternalConnections/IntCon') if pattern is not None else ()
    return xml_symbol_output.project_symbol(
        part, units=units, destination='dchxml', pins=pins, drawings=drawings,
        groups=((group_keys[index], *group.arguments[-2:])
                for index, group in enumerate(groups) if group.values[0]),
        connections=(tuple(project_key(connection, name, value.value, pad_keys)
                           for name, value in zip(('X', 'Y'), connection.arguments))
                     for connection in connections),
        pattern_style=pattern_style, datasheet=datasheet)
