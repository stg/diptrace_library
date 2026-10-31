"""PCB XML check snapshots; source object IDs end at the import boundary."""
from ....common.xml_records import enum_value, length, point
from ...model import drc_results as model
from .keys import position


ERROR_TYPES = ('Clearance', 'MinTrace', 'MinHole', 'MinRing', 'MaxRing', 'MaxPlatedHole',
    'MaxNonPlatedHole', 'ShiftedVia', '8', 'Drill', 'TraceLength', 'TraceLength',
    'HiddenPad', 'PrimaryGap', 'UncoupledLength', 'LengthTolerance', 'PhaseTolerance',
    'MaxNeckLength', 'DiffPairLoopback')
OBJECT_TYPES = ('Trace', 'BoardOutline', 'Shape', 'Via', 'Pad', 'MtHoleKeepout',
    'PlanePad', 'CopperPour', 'BoardCutout', 'StaticVia', 'PadHole', 'MtHole', 'ViaHole',
    'SMD', 'Silk', 'RouteKeepout', 'JumperWire', 'DiffPair', 'LengthMatch', 'Courtyard',
    'FiducialKeepout', 'Teardrop', 'PanelHoleKeepout', 'PanelHole', 'PausedTrace',
    'PausedJumperWire', 'PausedVia', 'PausedViaHole')
RULE_TYPES = ('DesignRules', 'NetClass1', 'NetClassDetails1', 'NetClass2',
              'NetClassDetails2', 'ClassToClass')


def read_results(record, board, *, units, placements, classes, layers):
    collection = board.add('DesignErrors')
    for index, source in enumerate(record.rows('DesignErrors', 'DesignError')):
        source.integer('Id', index)  # An output counter, not an object identity.
        error = collection.add('DesignError', index)
        error.add('Enabled', source.boolean('Enabled', True))
        for axis, value in zip(('X', 'Y'), point(source, units, default=0)):
            error.add(axis, value)
        for name in ('Value', 'Rule'):
            error.add(name, length(source.number(name, 0), units))
        error.add('Type', enum_value(source.value('Type', 0), ERROR_TYPES))
        error.add('RuleType', enum_value(source.value('RuleType', -1), RULE_TYPES))
        selected = source.integer('RuleLay', -1)
        error.add('RuleLay', position(selected, layers, label='design-check layer', path=source.node.path))
        for side in ('1', '2'):
            mode = enum_value(source.value('ObjectType'+side, 0), OBJECT_TYPES)
            values = {name: source.integer(name+side, 0 if name == 'Object' else -1)
                      for name in ('Object', 'SubObject', 'Point', 'ExtObject')}
            # XML selects pads/holes by their definition IDs. The shared input
            # assembler selects the placement's current source positions.
            if mode in (*model.PAD_TYPES, *model.HOLE_TYPES):
                placed = placements.get(values['Object'])
                choices = (placed.pad_positions if mode in model.PAD_TYPES else placed.hole_positions) if placed else {}
                values['SubObject'] = choices.get(values['SubObject'], -1)
            error.add('ObjectType'+side, mode)
            for name, value in values.items():
                error.add(name+side, value)
            selected = source.integer('ObjectNetClass'+side, -1)
            error.add('ObjectNetClass'+side, position(selected, classes,
                label='design-check net class', path=source.node.path))
        mask = error.add('Lays')
        for flag in source.rows('Lays', 'Item'):
            value = flag.content()
            if value.kind != 'boolean':
                raise ValueError(f'{flag.node.path}: expected boolean Y or N')
            mask.add('Item', value)
            flag.finish(allow_text=True)
        source.finish()
