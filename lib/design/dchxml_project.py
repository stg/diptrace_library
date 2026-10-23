"""Public XML project paths and simulator settings."""
from .dchxml import set_attribute
from .dchxml_settings import enum_text, field
from .model import Element


SIMULATION_TYPES = ('None', 'Small-Signal AC', 'DC Transfer Function', 'None', 'Noise',
                    'None', 'None', 'None', 'None', 'Transient')
SIMULATION_FIELDS = (
    ('sim_ac', 'SmallSignalAC', ('Variation', 'NumberOfPoints', 'StartFrequency', 'StopFrequency')),
    ('sim_dc', 'DCTransferFunc', ('SourceType', 'SourceRefDes', 'StartValue', 'Step', 'StopValue',
                               'SecondSource', 'SecondSourceType', 'SecondSourceRefDes',
                               'SecondStartValue', 'SecondStep', 'SecondStopValue')),
    ('sim_tran', 'Transient', ('StartTime', 'Step', 'StopTime')),
    ('sim_noise', 'Noise', ('OutputNet', 'ReferenceNet', 'Source', 'Variation', 'NumberOfPoints',
                          'StartFrequency', 'StopFrequency', 'PointsPerSummary')),
)


def project_simulator(schematic):
    source = schematic.one('ssimulator')
    mode = source.scalar('tp')
    if mode <= 0:
        return None
    result = Element('Simulator')
    set_attribute(result, 'Type', enum_text(mode, SIMULATION_TYPES))
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
        rows = source.select(own+'/pt')
        if rows:
            target = result.add(public)
            for index, row in enumerate(rows):
                field(target, names[index] if index < len(names) else 'Item', row.arguments[0])
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
