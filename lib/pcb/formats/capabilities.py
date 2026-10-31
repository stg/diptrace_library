"""PCB revision policy shared by adapters and capability queries."""
from ...common.capabilities import FormatCapabilities
from ...common.errors import UnsupportedFileError


# The current reader covers these historical schemas. Output starts with the
# verified 4.3 dialect; subsequent revisions add independent tail sections.
DIP = FormatCapabilities('dip', 'pcb', tuple(range(31, 63)), tuple(range(54, 63)), 62)
ASC = FormatCapabilities('asc', 'pcb', (53,), (53,), 53)
XML_APPLICATION_VERSIONS = {54: '4.3.0.5', 58: '4.9.5.0', 60: '5.2.0.1', 62: '5.3.5.1'}
DIPXML = FormatCapabilities('dipxml', 'pcb', ('4.3', '4.9', '5.2', '5.3'),
                            tuple(XML_APPLICATION_VERSIONS), 62)
FORMATS = {item.format: item for item in (DIP, ASC, DIPXML)}


def format_capabilities(format):
    """Return the same revision declaration used by the format adapter."""
    key = format.lower().lstrip('.')
    try:
        return FORMATS[key]
    except KeyError:
        raise UnsupportedFileError(format=key, family='pcb') from None
