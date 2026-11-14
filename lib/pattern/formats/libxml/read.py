"""Standalone XML to the same owned pattern model used by other adapters."""
from ....common import footprint_objects
from ....common.conversion import import_notice, import_diagnostics
from ....common.local_keys import map_key
from ....common.structural_edits import assembly
from ....common.units import XmlUnits
from ....common.xml_records import XmlRecord, application_version
from ....common.xml_footprints import PatternImportPolicy, read_pattern
from ....common.xml_pads import read_pad_style
from ....common.xml_library_values import read_catalog, modernize_library_category, read_supplier
from ....common.errors import UnsupportedFileError
from ....common.font_codec import PHYSICAL_XML_WIDTH_SINCE
from ...model import new_library
from ..import_patterns import normalize, finish
from .syntax import loads
from ..revisions import XML_READ_FAMILIES


def template_values(record):
    result = {'Verification': (False,)*4}
    if record.has('Value'):
        result['Value'] = record.text('Value')
    if (supplier := read_supplier(record.take('Suppliers'))) is not None:
        result['Suppliers'] = supplier
    return result


def incoming_pad(index):
    return footprint_objects.new_pad(index=index)


POLICY = PatternImportPolicy(footprint_objects.new_pattern, incoming_pad,
    footprint_objects.new_pattern_drawing, map_key, read_defaults=template_values,
    style_attribute=None, unassigned_drawing_pad_keys=(0,))


@import_diagnostics('libxml')
def parse(data, *, source=None):
    syntax = loads(data, source=source)
    record = XmlRecord(syntax.root.one('Library'))
    if record.text('Type') != 'DipTrace-PatternLibrary':
        raise ValueError('expected a standalone pattern library')
    declaration = record.text('Version')
    version = application_version(declaration, default=(4, 3, 0, 5))
    if version[:2] not in XML_READ_FAMILIES:
        raise UnsupportedFileError(format='libxml', family='pattern', version=declaration, reason='version')
    units = XmlUnits(record.text('Units', 'mm'))
    document = new_library(record.text('Name', ''), hint=record.text('Hint', ''))
    library = document.one('/Library')
    if record.has('UID32'):
        # Each save/export replaces this serialization token; it is not an
        # authored identity and does not belong to the editing model.
        record.integer('UID32')
    with assembly(document):
        library.one('Categories').detach()
        library.append(read_catalog(record, key='Number'))
    styles = {}
    for row in record.rows('PadStyles', 'PadStyle'):
        name = row.text('Name')
        if name in styles:
            raise ValueError('duplicate pad style name: ' + name)
        styles[name] = row.node
    used, inputs = set(), []
    for row in record.rows('Patterns', 'Pattern'):
        _, imported = read_pattern(row, units=units, styles=styles, policy=POLICY,
                                   physical_font_width=version >= PHYSICAL_XML_WIDTH_SINCE)
        normalized = normalize(imported.element, pad_indices=imported.pad_ids.values(),
            shape_indices=imported.shape_ids.values(), hole_indices=imported.hole_ids.values(),
            defaults=imported.defaults)
        pattern = normalized.element
        with assembly(document):
            library.one('Patterns').append(pattern)
            modernize_library_category(pattern, library.one('Categories'))
        inputs.append(normalized)
        used.update(imported.used_styles)
    unused = [(name, node) for name, node in styles.items() if name not in used]
    if unused:
        for name, node in unused:
            # Validate the declaration without inventing an authoring object
            # for a serialization resource the editor does not retain.
            read_pad_style(XmlRecord(node), footprint_objects.new_pattern(), units=units)
        import_notice('info', 'unused-pad-styles', 'Removed unused XML pad-style declarations',
                      (node for _, node in unused), recoverability='all current pad and default properties retained')
    record.finish()
    return finish(document, inputs)
