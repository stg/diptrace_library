"""Editable public schematic simulator settings."""
from ...common.model import (Element)
from ...common.schema import Field, Record


SIMULATION_TYPES = ('None', 'Small-Signal AC', 'DC Transfer Function', 'None', 'Noise',
                    'None', 'None', 'None', 'None', 'Transient', 'Digital')
SIMULATION_FIELDS = (
    ('sim_ac', 'SmallSignalAC', ('Variation', 'NumberOfPoints', 'StartFrequency', 'StopFrequency')),
    ('sim_dc', 'DCTransferFunc', ('SourceType', 'SourceRefDes', 'StartValue', 'Step', 'StopValue',
                               'SecondSource', 'SecondSourceType', 'SecondSourceRefDes',
                               'SecondStartValue', 'SecondStep', 'SecondStopValue')),
    ('sim_tran', 'Transient', ('StartTime', 'Step', 'StopTime')),
    ('sim_noise', 'Noise', ('OutputNet', 'ReferenceNet', 'Source', 'Variation', 'NumberOfPoints',
                          'StartFrequency', 'StopFrequency', 'PointsPerSummary')),
    ('sim_digital', 'Digital', ('StartTime', 'Step', 'StopTime', 'GroupBuses')),
)
ARGUMENT_SCHEMAS = {
    own: Record(public, {name: Field(name, 'text', description='Simulator expression or selection.')
                         for name in names},
                description='Ordered simulator settings; engineering suffixes and expressions remain text.')
    for own, public, names in SIMULATION_FIELDS
}
ARGUMENT_ITEM = Record('SimulationItem', {'Value': Field('Value', 'text', required=True)}, ('Value',),
                       'An additional simulator argument with no established public field name.')
SIMULATOR = Record('Simulator', {
    'tp': Field('tp', 'integer', required=True, default=0, description='Simulation type code.'),
    'gndnum': Field('gndnum', 'integer', required=True, default=-1,
                    description='Managed ground-net index; -1 means no ground net.'),
    'gndname': Field('gndname', 'text', required=True, default='', description='Ground net display name.'),
})
SIGNAL = Record('SimulationSignal', {
    name: Field(name, kind, required=True) for name, kind in (
        ('signal_tp', 'integer'), ('signal_num', 'integer'), ('signal_display_name', 'text'),
        ('signal_plotted', 'boolean'), ('signal_visible', 'boolean'), ('signal_color', 'integer'))
})


# Values containing engineering suffixes and expressions are editable strings.
OPTION_FIELDS = (
    ('OptionsGeneral', 'NoPrintStat', 'boolean', True),
    ('OptionsGeneral', 'NoPrintModelParams', 'boolean', True),
    ('OptionsGeneral', 'Temp', 'text', '27.0'),
    ('OptionsGeneral', 'TempNomMeasure', 'text', '27.0'),
    ('OptionsDC', 'AbsCurrentTolerance', 'text', '1p'),
    ('OptionsDC', 'MinConductance', 'text', '1p'),
    ('OptionsDC', 'ConductanceSteps', 'integer', 25),
    ('OptionsDC', 'SkipConductanceStepping', 'boolean', False),
    ('OptionsDC', 'Iteration', 'integer', 100),
    ('OptionsDC', 'TransferCurveIteration', 'integer', 50),
    ('OptionsDC', 'StartFromConductanceStepping', 'boolean', False),
    ('OptionsDC', 'PivotRation', 'text', '1e-3'),
    ('OptionsDC', 'PivotTolerance', 'text', '1e-13'),
    ('OptionsDC', 'RelativeError', 'text', '1e-3'),
    ('OptionsDC', 'GroundResistor', 'text', '1T'),
    ('OptionsDC', 'VoltageError', 'text', '1u'),
    ('OptionsAC', 'NoOPAnalysis', 'boolean', True),
    ('OptionsTransient', 'ChargeTolerance', 'text', '1e-14'),
    ('OptionsTransient', 'LowIteration', 'integer', 4),
    ('OptionsTransient', 'PointIteration', 'integer', 10),
    ('OptionsTransient', 'TotalIteration', 'integer', 5000),
    ('OptionsTransient', 'SourceStepping', 'integer', 25),
    ('OptionsTransient', 'MethodMaxOrder', 'integer', 2),
    ('OptionsTransient', 'Method', 'integer', 1),
    ('OptionsTransient', 'SourceSteppingChange', 'text', '0'),
    ('OptionsTransient', 'ErrorTolerance', 'text', '1'),
    ('OptionsTransient', 'TrapezoidalDampingFactor', 'text', '0.5'),
)
OPTION_SCHEMAS = {
    group: Record(group, {name: Field(name, kind, required=True, default=default)
                          for owner, name, kind, default in OPTION_FIELDS if owner == group})
    for group in dict.fromkeys(group for group, *_ in OPTION_FIELDS)
}


def modernize_arguments(schematic):
    """Replace serialized argument rows with current named settings once on import."""
    simulator = schematic.child('ssimulator')
    if simulator is None:
        return
    signals = simulator.child('signals')
    if signals is not None:
        signals.set_values()
    for own, _, names in SIMULATION_FIELDS:
        group = simulator.child(own)
        if group is None:
            continue
        for index, row in enumerate(group.children('pt')):
            row.kind = names[index] if index < len(names) else 'Item'
        group.set_values()


def argument_values(group):
    """Project a named settings group to its public positional argument sequence."""
    names = tuple(ARGUMENT_SCHEMAS[group.kind].fields)
    values, absent = [], False
    for name in names:
        field = group.child(name)
        if field is None:
            absent = True
        elif absent:
            raise ValueError(f'{group.path}: {name} follows a missing simulator argument')
        else:
            values.append(field.arguments[0])
    extra = group.children('Item')
    if extra and absent:
        raise ValueError(f'{group.path}: additional simulator arguments require the named prefix')
    values.extend(row.arguments[0] for row in extra)
    return tuple(values)


def complete_options(simulator):
    """Supply current defaults for settings absent from an older document."""
    if simulator.child('sim_digital') is None:
        settings = simulator.add('sim_digital')
        for name, value in zip(ARGUMENT_SCHEMAS['sim_digital'].fields, ('#', '#', '#', '-')):
            settings.add(name, value)
    for group, name, kind, default in OPTION_FIELDS:
        owner = simulator.child(group)
        if owner is None:
            owner = simulator.add(group)
        if owner.child(name) is None:
            owner.add(name, default)


def default_simulator():
    """Construct current named settings without file-format counts or row slots."""
    result = Element('ssimulator')
    result.add('tp', 0)
    result.add('signals')
    for own, _, names in SIMULATION_FIELDS:
        if own == 'sim_digital':
            continue
        settings = result.add(own)
        for name in names:
            settings.add(name, '-' if name == 'SecondSource' else '#')
    result.add('gndnum', -1)
    result.add('gndname', '')
    complete_options(result)
    return result
