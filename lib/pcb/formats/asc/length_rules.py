"""ASC length policies and selected connections into named import records."""
from ...model.length_matching import POLICY
from ..errors import PcbError
from .values import boolean, numeric_row


def _policy(record):
    values = list(record.arguments)
    if len(values) != 7 or not isinstance(values[0].value, str):
        raise PcbError(f'{record.path}: expected a length-rule name and six settings')
    for index in (3, 4):
        values[index] = boolean(values[index], record.path)
    for index in (1, 2, 5, 6):
        value = values[index]
        if value.kind != 'number' or value.unit or index in (5, 6) and type(value.value) is not int:
            raise PcbError(f'{record.path}: invalid length-rule value at column {index+1}')
    if values[6].value not in (0, 1):
        raise PcbError(f'{record.path}: unknown length-rule type {values[6].value}')
    for name, index in (('Name', 0), ('FixedLength', 1), ('Delta', 2)):
        POLICY.fields[name].validate(values[index].value)
    rows = tuple(record.children())
    if any(row.kind != 'pt' for row in rows):
        raise PcbError(f'{record.path}: expected selected length connections')
    record.set_values()
    for name, index in (('Name', 0), ('FixedLength', 1), ('Delta', 2), ('AnyError', 3),
                         ('NetClass', 5), ('Type', 6)):
        record.add(name, values[index])
    # Column five is a prior check-display snapshot. The current AnyError is
    # authoritative; XML import and output can regenerate the repeated flag.
    connections = record.add('Rules')
    for index, row in enumerate(rows):
        values = numeric_row(row, 7, flags=(6,), integers=(0, 1, 2, 3, 4))
        row.kind = 'Rule'
        row.set_values(index)
        for name, value in zip(('NetId', 'Comp1', 'Pad1', 'Comp2', 'Pad2', 'Length', 'Error'), values):
            row.add(name, value)
        row.move_to(connections)


def unpack_length_rules(board):
    if (main := board.child('MainLengthRule')) is not None:
        _policy(main)
    if (rules := board.child('LengthRules')) is not None:
        if rules.arguments or any(row.kind != 'LengthRule' for row in rules.children()):
            raise PcbError(f'{rules.path}: expected named length rules')
        for rule in rules.children():
            _policy(rule)
