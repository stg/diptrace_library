"""Read standalone component XML through the shared symbol/physical codecs."""
from ....common import footprint_objects, symbol_objects
from ....common.conversion import import_diagnostics, import_notice
from ....common.errors import UnsupportedFileError
from ....common.font_codec import PHYSICAL_XML_WIDTH_SINCE
from ....common.local_keys import map_key
from ....common.model import Element
from ....common.units import XmlUnits
from ....common.xml_footprints import PatternImportPolicy, read_pattern
from ....common.xml_library_values import (read_catalog, read_subfolders, resolve_category,
                                         modernize_library_category)
from ....common.xml_pads import read_pad_style
from ....common.xml_records import XmlRecord, application_version
from ....common.xml_symbols import SymbolImportPolicy, read_symbol
from ..import_components import construct_library
from ..revisions import XML_READ_FAMILIES
from .syntax import loads


SYMBOL_POLICY = SymbolImportPolicy(symbol_objects.new_symbol, symbol_objects.new_pin,
    symbol_objects.new_drawing, map_key, user_field_choices=False)
PATTERN_POLICY = PatternImportPolicy(footprint_objects.new_pattern,
    lambda index: footprint_objects.new_pad(index=index),
    footprint_objects.new_pattern_drawing, map_key, unassigned_drawing_pad_keys=(0,))


def _header(record, *, kind, default_version, default_units):
    if record.text('Type', 'DipTrace-'+kind+'Library') != 'DipTrace-'+kind+'Library':
        raise ValueError('expected a '+kind.lower()+' library')
    declaration = record.text('Version', default_version)
    version = application_version(declaration, default=(4, 3, 0, 5))
    if version[:2] not in XML_READ_FAMILIES:
        raise UnsupportedFileError(format='elixml', family='component', version=declaration, reason='version')
    units = XmlUnits(record.text('Units', default_units))
    name, hint = record.text('Name', ''), record.text('Hint', '')
    if record.has('UID32'):
        record.integer('UID32')
    return declaration, units, version >= PHYSICAL_XML_WIDTH_SINCE, name, hint


def _patterns(record, *, version, units):
    _, units, physical_width, _, _ = _header(record, kind='Pattern',
        default_version=version, default_units=units.units)
    categories = read_catalog(record, key='Number')
    styles = {}
    for source in record.rows('PadStyles', 'PadStyle'):
        key = source.text('Name')
        if key in styles:
            raise ValueError('duplicate XML pad style: '+key)
        styles[key] = source.node
    patterns, used_styles = {}, set()
    for source in record.rows('Patterns', 'Pattern'):
        key, imported = read_pattern(source, units=units, styles=styles,
            policy=PATTERN_POLICY, physical_font_width=physical_width)
        if key in patterns:
            raise ValueError('duplicate XML pattern style: '+key)
        resolve_category(imported.element, categories)
        patterns[key] = imported
        used_styles.update(imported.used_styles)
    for key, node in styles.items():
        if key not in used_styles:
            read_pad_style(XmlRecord(node), footprint_objects.new_pattern(), units=units)
            import_notice('info', 'unused-pad-styles', 'Consumed an unused XML pad-style declaration.', (node,),
                          recoverability='all attached pad and default properties are retained')
    if categories.children():
        import_notice('info', 'component-physical-catalogue',
            'Resolved physical classifications from the XML catalogue.', (categories,),
            recoverability='classification labels and selected keys belong to the attached footprint')
    record.finish()
    return patterns


def _map_pad_selections(part, connections, mapping):
    for connection in connections:
        for argument, name in enumerate(('X', 'Y')):
            connection.set_argument(argument, map_key(connection, name, connection.values[argument], mapping))
    for pin in part.select('Pins/Pin'):
        # Zero is the component-library unassigned selector, even when the
        # supplied physical catalogue also happens to declare a zero public key.
        if pin['Number'] != 0:
            pin['Number'] = map_key(pin, 'PadId', pin['Number'], mapping)


@import_diagnostics('elixml')
def parse(data, *, source=None):
    syntax = loads(data, source=source)
    record = XmlRecord(syntax.root.one('Library'))
    version, units, physical_width, name, hint = _header(record, kind='Component',
        default_version='4.3.0.5', default_units='mm')
    incoming = Element('Library')
    categories = read_catalog(record, key='Index')
    incoming.append(categories)
    folders = read_subfolders(record)
    incoming.append(folders if folders is not None else Element('Subfolders'))
    nested = record.take('Library')
    patterns = _patterns(nested, version=version, units=units) if nested is not None else {}
    used = set()
    components = incoming.add('Components')
    for index, source_component in enumerate(record.rows('Components', 'Component')):
        source_component.integer('Id', index)
        component = components.add('Component')
        parts = component.add('Parts')
        primary = None
        for ordinal, source_part in enumerate(source_component.children('Part')):
            part, key, connections = read_symbol(source_part, units=units,
                policy=SYMBOL_POLICY, physical_font_width=physical_width)
            if key is not None and key not in patterns:
                raise ValueError('unresolved XML pattern style: '+key)
            if ordinal == 0:
                primary = patterns[key] if key is not None else None
                pattern = primary.element.clone() if primary is not None else footprint_objects.new_pattern()
                part.append(pattern)
                for connection in connections:
                    if all(key > 0 for key in connection.values):
                        pattern.one('InternalConnections').append(connection)
                    else:
                        import_notice('info', 'unassigned-internal-connection',
                            'Removed an internal connection with an unassigned endpoint.', (connection,),
                            recoverability='a connection requires two physical pads')
                if key is not None:
                    used.add(key)
            elif connections:
                import_notice('warning', 'secondary-internal-connections',
                    'Removed internal connections from an inactive secondary footprint.', connections,
                    recoverability='the component owns its physical definition on its primary part')
            _map_pad_selections(part, connections, primary.pad_ids if primary is not None else {})
            parts.append(part)
            modernize_library_category(part, categories)
        if not parts.children():
            raise ValueError('component library entry has no parts')
        source_component.finish()
    for key, imported in patterns.items():
        if key not in used:
            import_notice('info', 'unused-component-pattern',
                'Consumed an unused XML footprint resource.', (imported.element,),
                recoverability='attached footprint definitions are retained')
    record.finish()
    return construct_library(incoming, name=name, hint=hint)
