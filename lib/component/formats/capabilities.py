"""Standalone component support from the same declarations as its adapters."""
from ...common.capabilities import FormatCapabilities
from ...common.errors import UnsupportedFileError
from .revisions import (BINARY_READ_VERSIONS, BINARY_WRITE_VERSIONS,
    BINARY_DEFAULT_WRITE_VERSION, ASCII_READ_VERSIONS, ASCII_WRITE_VERSIONS,
    XML_READ_FAMILIES, XML_WRITE_VERSIONS)


ELI = FormatCapabilities('eli', 'component', BINARY_READ_VERSIONS,
                        BINARY_WRITE_VERSIONS, BINARY_DEFAULT_WRITE_VERSION)
ASC = FormatCapabilities('asc', 'component', ASCII_READ_VERSIONS,
                        ASCII_WRITE_VERSIONS, ASCII_WRITE_VERSIONS[-1])
ELIXML = FormatCapabilities('elixml', 'component',
    tuple('.'.join(map(str, family)) for family in XML_READ_FAMILIES),
    XML_WRITE_VERSIONS, XML_WRITE_VERSIONS[-1])
FORMATS = {item.format: item for item in (ELI, ASC, ELIXML)}


def format_capabilities(format):
    """Return exact adapter versions; XML output versions are declarations."""
    key = format.lower().lstrip('.')
    try:
        return FORMATS[key]
    except KeyError:
        raise UnsupportedFileError(format=key, family='component') from None
