"""Schematic policy for shared physical footprint XML import."""
from ....common.xml_footprints import PatternImportPolicy
from ....common.xml_footprints import read_pattern as _read_pattern, _dimension as _read_dimension
from ...model.pads import empty_pad
from ...model.objects import new_pattern, new_pattern_shape
from ...model.local_keys import map_key


POLICY = PatternImportPolicy(new_pattern, empty_pad, new_pattern_shape, map_key)


def read_pattern(record, *, units, styles, physical_font_width=True):
    return _read_pattern(record, units=units, styles=styles, policy=POLICY, physical_font_width=physical_font_width)


def _dimension(record, *, index, units, groups, objects):
    return _read_dimension(record, index=index, units=units, groups=groups, objects=objects, policy=POLICY)
