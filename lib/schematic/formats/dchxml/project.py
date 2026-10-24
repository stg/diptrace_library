"""Public XML project paths and simulator settings."""
from .syntax import (set_attribute)
from .settings import (enum_text, field)
from ....common.model import (Element)
from ...model.simulation import (SIMULATION_TYPES, SIMULATION_FIELDS, argument_values)


def project_simulator(schematic, *, version=46):
    source = schematic.one('ssimulator')
    mode = source.scalar('tp')
    if mode <= 0 and version < 50:
        return None
    result = Element('Simulator')
    set_attribute(result, 'Type', str(mode) if mode == 10 and version < 52 else enum_text(mode, SIMULATION_TYPES))
    signals = source.select('signals/signal')
    if signals:
        target = result.add('Signals')
        for signal in signals:
            item = target.add('Signal')
            set_attribute(item, 'Type', enum_text(signal.scalar('signal_tp'), ('Current', 'Voltage')))
            set_attribute(item, 'Id', signal.scalar('signal_num'))
            field(item, 'DisplayName', signal.scalar('signal_display_name'))
            for public, own in (('Plotted', 'signal_plotted'), ('Visible', 'signal_visible'), ('Color', 'signal_color')):
                set_attribute(item, public, signal.scalar(own))
    for own, public, names in SIMULATION_FIELDS:
        if own == 'sim_digital' and version < 50:
            continue
        if own == 'sim_digital' and version < 52:
            names = names[:3]
        values = argument_values(source.one(own))
        if values:
            target = result.add(public)
            for index, value in enumerate(values):
                field(target, names[index] if index < len(names) else 'Item', value)
    if version >= 50:
        from ...model.simulation import (OPTION_FIELDS)
        groups = {}
        for group, name, kind, default in OPTION_FIELDS:
            if group not in groups:
                groups[group] = result.add(group)
            target = groups[group]
            value = source.one(group).scalar(name, default)
            (field if kind == 'text' else set_attribute)(target, name, value)
    set_attribute(result, 'GndNetId', source.scalar('gndnum'))
    field(result, 'GndNetName', source.scalar('gndname'))
    return result


def project_libraries(schematic):
    result = Element('ProjectLibs')
    for own, public, record in (('ProjectLibs_Folders', 'Folders', 'Folder'), ('ProjectLibs_Libs', 'Libs', 'Lib')):
        paths = schematic.select(own+'/'+record)
        if paths:
            target = result.add(public)
            for path in paths:
                item = target.add(record)
                field(item, 'Path', path.arguments[0])
                variable = path.scalar('VariablePath', '')
                field(item, 'Var', variable if variable.replace(' ', '') else path.arguments[0])
    set_attribute(result, 'Sorted', schematic.scalar('ProjectLibs_Sorted'))
    return result
