"""PCB footprint XML policy over the shared physical definition reader."""
from ....common.footprint_objects import new_pattern, new_pad, new_pattern_drawing
from ....common.xml_footprints import PatternImportPolicy, read_pattern
from ....common.xml_footprint_vocabulary import PATTERN_TYPES
from ....common.local_keys import map_key
from ....common.conversion import import_notice
from ..errors import PcbError
from .versions import XmlVersion
from ...model.definitions import PATTERN


PCB_PATTERN_TYPES = (*PATTERN_TYPES, '11', '12', '13', 'Pad', 'MtHole', 'Via', '17', '18', '19', 'Fiducial')


def _key(owner, field, number, choices):
    if field == 'Group':
        return map_key(owner, field, number, choices)
    if number < 0:
        return number
    try:
        return choices[number]
    except KeyError:
        if field == 'PadId' and owner.kind == 'Shape':
            import_notice('info', 'unavailable-drawing-pad',
                f'Detached a footprint drawing from unavailable pad key {number}; geometry remains.',
                recoverability='the missing pad has no assignment; drawing geometry remains editable')
            return -1
        raise PcbError(f'{owner.path}: unresolved footprint {field} key {number}') from None


def _defaults(record):
    # These belong to the PCB component template, not physical pad geometry.
    return {name: record.text(name, '') for name in ('RefDes', 'Value', 'Manufacturer', 'Datasheet')}


def _pattern(name):
    pattern = new_pattern(name)
    pattern.one('Pattern_Manufacturer').detach()
    return pattern.bind_schema(PATTERN)


POLICY = PatternImportPolicy(_pattern, lambda index: new_pad(index=index), new_pattern_drawing,
                            _key, PCB_PATTERN_TYPES, _defaults)


def read_patterns(library, *, units):
    """Read a pattern library; return temporary style-keyed definition inputs."""
    physical_width = XmlVersion.parse(library.text('Version','')).physical_font_width
    styles, patterns = {}, {}
    for record in library.rows('PadStyles', 'PadStyle'):
        name = record.text('Name')
        if name in styles:
            raise PcbError(f'{record.node.path}: duplicate pad style {name!r}')
        styles[name] = record.node
    for record in library.rows('Patterns', 'Pattern'):
        key, definition = read_pattern(record, units=units, styles=styles, policy=POLICY, physical_font_width=physical_width)
        if key in patterns:
            raise PcbError(f'{record.node.path}: duplicate footprint style {key!r}')
        patterns[key] = definition
    return patterns, styles
