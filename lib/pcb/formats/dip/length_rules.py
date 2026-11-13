"""Authored length-matching rules and their saved check results."""
from .preamble import _fields


def _rules(reader, owner):
    rules = reader.add(owner, 'Rules')
    for index in range(reader.count('length matching connections')):
        rule = reader.add(rules, 'Rule', index)
        _fields(reader, rule, 'integer', 'NetId Comp1 Pad1 Comp2 Pad2')
        reader.field_into(rule, 'Length', 'number')
        reader.field_into(rule, 'Error', 'boolean')
    return rules


def _parameters(reader, rule):
    reader.field_into(rule, 'Name', 'text')
    _fields(reader, rule, 'number', 'FixedLength Delta')
    reader.field_into(rule, 'AnyError', 'boolean')
    reader.boolean()  # Reconstructable check-display snapshot of AnyError.
    _fields(reader, rule, 'integer', 'NetClass Type')
    _rules(reader, rule)


def read_length_rules(reader, board):
    if reader.header.version <= 42:
        return None
    _parameters(reader, reader.add(board, 'MainLengthRule'))
    rules = reader.add(board, 'LengthRules')
    for index in range(reader.count('length matching rules')):
        _parameters(reader, reader.add(rules, 'LengthRule', index))
    for net_class in board.select('NetClasses/NetClass'):
        _fields(reader, net_class, 'number', 'LengthDelta FixedLength')
    for net in board.select('Nets/Net'):
        reader.field_into(net, 'Highlighted', 'boolean')
    for table in board.select('Tables/Table'):
        _fields(reader, table, 'integer', 'DocType DocUnits')
    return rules
