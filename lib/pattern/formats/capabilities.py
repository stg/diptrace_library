"""Standalone pattern support from the same declarations as its adapters."""
from ...common.capabilities import FormatCapabilities
from ...common.errors import UnsupportedFileError
from .revisions import (BINARY_READ_VERSIONS, BINARY_WRITE_VERSIONS,
    BINARY_DEFAULT_WRITE_VERSION, ASCII_READ_VERSIONS, ASCII_WRITE_VERSIONS,
    XML_READ_FAMILIES, APPLICATION_VERSIONS)


LIB = FormatCapabilities('lib', 'pattern', BINARY_READ_VERSIONS,
                        BINARY_WRITE_VERSIONS, BINARY_DEFAULT_WRITE_VERSION)
ASC = FormatCapabilities('asc', 'pattern', ASCII_READ_VERSIONS,
                        ASCII_WRITE_VERSIONS, ASCII_WRITE_VERSIONS[-1])
LIBXML = FormatCapabilities('libxml', 'pattern',
    tuple('.'.join(map(str, family)) for family in XML_READ_FAMILIES),
    APPLICATION_VERSIONS, APPLICATION_VERSIONS[-1])
FORMATS = {item.format: item for item in (LIB, ASC, LIBXML)}


def format_capabilities(format):
    """Return exact adapter versions; XML output versions are declarations."""
    key = format.lower().lstrip('.')
    try:
        return FORMATS[key]
    except KeyError:
        raise UnsupportedFileError(format=key, family='pattern') from None
