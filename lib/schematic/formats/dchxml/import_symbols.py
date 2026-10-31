"""Schematic symbol XML policy over the shared definition reader."""
from ....common import xml_symbols
from ...model.objects import new_symbol, new_symbol_shape, new_pin
from ...model.local_keys import map_key


POLICY = xml_symbols.SymbolImportPolicy(lambda name, reference: new_symbol(name, reference, placed=False),
    lambda index: new_pin(index, placed=False), new_symbol_shape, map_key)


def read_symbol_pin(record, *, index, units, groups):
    return xml_symbols.read_symbol_pin(record, index=index, units=units, groups=groups, policy=POLICY)


def read_symbol_drawing(record, *, index, units, groups):
    return xml_symbols.read_symbol_drawing(record, index=index, units=units, groups=groups, policy=POLICY)


def read_symbol(record, *, units, physical_font_width=True):
    return xml_symbols.read_symbol(record, units=units, policy=POLICY, physical_font_width=physical_font_width)
