"""Standalone symbol/physical-library XML vocabulary over the shared codec."""
from ....common import xml
from ....common.xml_library_syntax import NUMBERS, FLAGS

DIALECT = xml.XmlDialect(format='elixml', source_type='DipTrace-ComponentLibrary',
    root_tag='Library',
    number_attributes=NUMBERS | frozenset('''SubFolderIndex Length Size Scale SignalDelay
        NumXShift NumYShift NameXShift NameYShift NumOrientation NameOrientation'''.split()),
    boolean_attributes=FLAGS | {'ShowName'},
    number_text=frozenset((parent, 'Index') for parent in ('Category', 'Type', 'SubType')))


def loads(data, *, source=None, retain_source=False):
    return xml.loads(data, source=source, dialect=DIALECT, retain_source=retain_source)
