"""Editable public schematic simulator settings."""
from .model import Element


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


def complete_options(simulator):
    """Supply current defaults for settings absent from an older document."""
    if simulator.child('sim_digital') is None:
        rows = simulator.add('sim_digital', 4)
        for value in ('#', '#', '#', '-'):
            rows.add('pt', value)
    for group, name, kind, default in OPTION_FIELDS:
        owner = simulator.child(group)
        if owner is None:
            owner = simulator.add(group)
        if owner.child(name) is None:
            owner.add(name, default)


def default_simulator():
    """Default simulator."""
    result=Element('ssimulator')
    result.add('tp',0)
    result.add('signals',0)
    for name,count in [('sim_ac',4),('sim_dc',11),('sim_tran',3),('sim_noise',8)]:
        values=result.add(name,count)
        for index in range(count):
            values.add('pt','-' if name=='sim_dc' and index==5 else '#')
    result.add('gndnum',-1)
    result.add('gndname','')
    complete_options(result)
    return result
