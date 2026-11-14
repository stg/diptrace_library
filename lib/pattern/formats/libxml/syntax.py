"""Standalone library XML vocabulary over the shared lexical codec."""
from ....common import xml


from ....common.xml_library_syntax import NUMBERS, FLAGS


DIALECT = xml.XmlDialect(format='libxml', source_type='DipTrace-PatternLibrary',
    root_tag='Library',
    number_attributes=NUMBERS, boolean_attributes=FLAGS,
    number_text=frozenset((parent, 'Index') for parent in ('Category', 'Type', 'SubType')))


def loads(data, *, source=None, retain_source=False):
    return xml.loads(data, source=source, dialect=DIALECT, retain_source=retain_source)
