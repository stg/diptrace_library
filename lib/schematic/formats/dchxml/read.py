"""Normalize recognized public XML data into the searchable shared schematic.

Public keys become identities and current array indices. Missing binary facts
receive explicit own authoring defaults. The original XML document is untouched;
its raw adapter remains available for syntax fidelity or unsupported resources.
"""
from .import_components import (read_component)
from .import_graphics import (read_drawings)
from .import_library import (read_library)
from .import_nets import (read_nets, read_pairs, read_buses, read_groups)
from .import_project import (read_project)
from .import_settings import (read_sheets, read_settings, read_erc, read_classes)
from .import_tables import (read_tables)
from ....common.xml_records import (XmlRecord, replace_rows)
from ....common.units import XmlUnits
from ....common.model import (Value)
from ....common.references import (References)
from ...model.new import (new_schematic)


def import_schematic(document):
    if document.representation != 'dchxml':
        raise ValueError('public DCHXML input is required')
    document.rebuild(force=False)
    source = XmlRecord(document.one('/Source'))
    if source.text('Type') != 'DipTrace-Schematic':
        raise ValueError('expected a public XML schematic')
    version = source.text('Version', '')
    units = XmlUnits(source.text('Units', 'mm'))
    view = new_schematic()
    view._automatic_structure = False
    schematic = view.one('/Schematic')
    public = source.take('Schematic', required=True)
    sheets, active = read_sheets(public.take('SheetSettings', required=True), schematic, units=units)
    if not 0 <= active < len(sheets):
        raise ValueError('XML active sheet must identify a current sheet position')
    read_settings(public.take('Settings', required=True), schematic, units=units)
    read_project(public, schematic)
    count = public.take('DesignCache')
    cache_count = 0 if count is None else count.integer('Count', 0)
    if count is not None:
        count.finish()
    library = read_library(source.take('Library'), schematic, units=units, cache_count=cache_count)
    classes = read_classes(public, schematic, units=units) or {0: 0}
    erc = public.take('ERC')
    if erc is not None:
        read_erc(erc, schematic)
    parts, keys = [], set()
    for record in public.rows('Components', 'Part'):
        style, variant = record.text('ComponentStyle'), record.integer('ComponentPart', 0)
        if style not in library.definitions or not 0 <= variant < len(library.definitions[style]):
            raise ValueError(f'{record.node.path}: unresolved component style/variant')
        definition = library.definitions[style][variant]
        part = read_component(record, definition.one('Part'), definition.one('Pattern'), units=units, sheets=sheets)
        key = part.scalar('Number')
        if key in keys:
            raise ValueError('duplicate XML component Id')
        keys.add(key)
        parts.append(part)
    replace_rows(schematic, 'Components', parts)
    read_nets(public, schematic, units=units, sheets=sheets, classes=classes)
    read_pairs(public, schematic, classes=classes)
    read_buses(public, schematic, units=units, sheets=sheets)
    read_drawings(public, schematic, units=units, sheets=sheets)
    read_tables(public, schematic, units=units, sheets=sheets)
    read_groups(public, schematic)
    public.finish()
    source.finish()
    from ...model.fonts import (complete_fonts)
    complete_fonts(schematic)
    for flag, label in (('UnitsMM', 'mm'), ('UnitsMIL', 'mil'), ('UnitsINCH', 'inch')):
        schematic.one('Settings').set_field(flag, units.units == label)
    page = schematic.select('Pages/Page')[active]
    schematic.set_field('ActiveSheet', active)
    view.one('/Scale').set_values(Value(page.scalar('PageScale')*100, 'number', '%'))
    for own, public_name in (('Xpos', 'PageXPos'), ('Ypos', 'PageyPos')):
        view.one('/'+own).set_values(*page.one(public_name).arguments)
    view.metadata.update(imported_from='dchxml', xml_source_version=version,
                         missing_data_policy='declared authoring defaults for facts absent from XML',
                         identifier_policy='renumbered by identity; raw XML preserves literal public keys')
    from ...model.schema import (validate_public_content)
    validate_public_content(view, allow_xml_fields=True)
    # The empty constructor's watched collections have been replaced during
    # assembly. Bind the completed owned tree once, before canonicalizing IDs.
    view.references = References(view)
    from ...model.refs import (bind_schematic_references)
    from ...model.user_fields import (modernize_user_field_names)
    modernize_user_field_names(schematic)
    from ...model.drawing_data import (normalize_drawings)
    normalize_drawings(schematic)
    from ....common.cell_text import (modernize_cell_text)
    modernize_cell_text(schematic, paths=('Tables/Table/Cells/Cell', 'Pages/Page/TitleBlocks/TitleBlock/Contents/Content'))
    bind_schematic_references(view)
    from ...model.symbol_text import (refresh_symbol_text)
    refresh_symbol_text(view)
    unexpected = [issue for issue in view.references.issues
                  if not issue.message.startswith(('symbol-pin-pad:', 'symbol-group:', 'pattern-group:', 'marking-user-field:',
                                                   'pattern-dimension-', 'pattern-shape-pad:', 'pattern-internal-pad-'))]
    if unexpected:
        raise ValueError('cannot normalize unresolved XML references: '+unexpected[0].message)
    view.rebuild(force=True)
    from ...editing.route_normalization import (normalize_imported_routes)
    normalize_imported_routes(view)
    for node in view.root.walk(include_self=True):
        node.annotations['requires_asc_projection'] = True
        node._syntax = None
        node._dirty = node._reordered = False
    view._automatic_structure = True
    return view
