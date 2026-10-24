"""Single version policy used by schematic adapters and the public query."""
from ...common.capabilities import FormatCapabilities
from dataclasses import dataclass


# Each writable revision declares its XML dialect here as well. Adding a row
# extends the readers, writers and public query together; read-only historical
# schemas remain distinct. Feature-specific gates still belong to the adapters.
@dataclass(frozen=True)
class SchematicRevision:
    binary_output: bool = False
    xml_application: str | None = None


REVISIONS = {
    **dict.fromkeys(range(29, 46), SchematicRevision()),
    46: SchematicRevision(True, '4.3.0.5'),
    47: SchematicRevision(True, '4.9.5.0'),
    48: SchematicRevision(True, '4.9.5.0'),
    49: SchematicRevision(True, '5.2.0.1'),
    50: SchematicRevision(True, '5.2.0.1'),
    51: SchematicRevision(True, '5.2.0.1'),
    52: SchematicRevision(True, '5.3.5.1'),
}
XML_APPLICATION_VERSIONS = {v: revision.xml_application for v, revision in REVISIONS.items()
                            if revision.xml_application is not None}
_BINARY_OUTPUT = tuple(v for v, revision in REVISIONS.items() if revision.binary_output)
DCH = FormatCapabilities('dch', 'schematic', tuple(REVISIONS), _BINARY_OUTPUT, min(_BINARY_OUTPUT))
ASC = FormatCapabilities('asc', 'schematic', (46,), (46,), 46)
DCHXML = FormatCapabilities('dchxml', 'schematic',
                            tuple(dict.fromkeys('.'.join(v.split('.')[:2]) for v in XML_APPLICATION_VERSIONS.values())),
                            tuple(XML_APPLICATION_VERSIONS), min(XML_APPLICATION_VERSIONS))
FORMATS = {item.format: item for item in (DCH, ASC, DCHXML)}


def format_capabilities(format):
    """Return immutable adapter capabilities; names may have a leading dot."""
    key = format.lower().lstrip('.')
    try:
        return FORMATS[key]
    except KeyError:
        raise ValueError(f'no capabilities registered for {key!r}') from None
