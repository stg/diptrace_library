"""Resolve public PCB font-stroke conventions at the import boundary."""
from ....common.xml_font_import import read_width as _read_width


def read_width(record, *, units, version, default=-2):
    return _read_width(record,units=units,physical=version.physical_font_width,default=default)
