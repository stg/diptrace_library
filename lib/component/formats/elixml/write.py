"""Standalone component XML using shared symbol and physical projections."""
import secrets

from ....common.conversion import export_diagnostics, info, warn
from ....common.font_codec import compatibility_size
from ....common.library_versions import LibraryApplicationVersion
from ....common.library_output_keys import PhysicalKeys, GroupKeys
from ....common.library_link_projection import check_issues
from ....common.library_catalogue import ROLES as CATALOGUE_ROLES
from ....common.units import XmlUnits
from ....common.xml import dumps_plan, set_attribute
from ....common.xml_catalog import CategoryCatalog, StylePlans
from ....common.xml_library_output import project_subfolders
from ....common.xml_library_physical import project_pattern
from ....common.xml_plan import XmlBuilder, XmlPlan
from ....common.library_group_bounds import coordinates as group_coordinates
from ....common.xml_symbol_output import project_symbol, project_symbol_pin, project_symbol_drawing
from ..export_view import prepare_export
from ..revisions import XML_WRITE_VERSIONS
from .syntax import DIALECT


def _adapt_symbols(component, profile, report):
    for part in component.select('Parts/Part'):
        for shape in part.select('Shapes/Shape'):
            if shape['Type'] != 10 and shape.select('TextLine/pt'):
                warn(report, 'non-text-drawing-content', 'elixml',
                     'XML omits text attached to a non-text drawing', (shape,))
        if profile.current_fields:
            continue
        sizes = [(pin, 'NameFontSize', 'NameFontMono') for pin in part.select('Pins/Pin')]
        sizes.extend((shape, 'FontSize', 'FontMono') for shape in part.select('Shapes/Shape'))
        for owner, size, mono in sizes:
            rounded = compatibility_size(owner[size])
            if owner[size] != rounded:
                owner[size] = rounded
                warn(report, 'fractional-font-size', 'elixml',
                     'Destination font sizes are rounded to integral values', (owner,))
            if owner.get(mono, False):
                owner[mono] = False
                warn(report, 'monospaced-font', 'elixml',
                     'Destination omits monospaced vector-font selection', (owner,))
    supplier = component.child('Suppliers')
    if supplier is not None and (supplier.get('SourceLocator') or supplier.get('MainSupplier')
                                 or supplier.select('Prices/Quote')):
        warn(report, 'supplier-details', 'elixml',
             'XML omits supplier source, primary choice and price breaks', (supplier,))


def _part(part, component, *, primary, units, profile, pattern_style, report, keys, text_layout):
    groups = GroupKeys(part, 'Groups', (*part.select('Pins/Pin'), *part.select('Shapes/Shape')),
                       destination='elixml', report=report)
    pins = (project_symbol_pin(pin, units=units,
                pad_id=max(0, keys.pad_selection(pin)), group=groups.selection(pin),
                fractional_font=profile.current_fields, physical_font_width=profile.physical_font_width,
                _factory=XmlBuilder) for pin in part.select('Pins/Pin'))
    drawings = (project_symbol_drawing(shape, units=units, group=groups.selection(shape),
                    fractional_font=profile.current_fields, physical_font_width=profile.physical_font_width,
                    _factory=XmlBuilder) for shape in part.select('Shapes/Shape'))
    layout = text_layout if text_layout is not None else profile.text_layout()
    group_rows = ((groups.key(group), *group_coordinates(group, layout=layout))
                  for group in part.select('Groups/pt') if group['Enabled'])
    pattern = component.child('Pattern') if primary else None
    connections = tuple(keys.connection(pair) for pair in pattern.select('InternalConnections/IntCon')) if pattern is not None else ()
    return project_symbol(part, description=component, include_resources=primary,
        units=units, destination='elixml', pins=pins, drawings=drawings, groups=group_rows,
        connections=connections, pattern_style=pattern_style if primary else None,
        group_tag='Group', group_enabled=profile.current_fields, include_empty_folder=not profile.current_fields,
        report=report, _factory=XmlBuilder)


@export_diagnostics('elixml')
def project_document(document, *, version=None, units='mm', report=None, text_layout=None):
    profile = LibraryApplicationVersion.select(version, family='component', format='elixml', applications=XML_WRITE_VERSIONS)
    view = prepare_export(document, destination='elixml', report=report)
    from ...model import symbols
    from ...model.text_fields import ROLE as USER_FIELD_ROLE
    check_issues(view, roles=(symbols.GROUP_ROLE, symbols.PAD_ROLE, USER_FIELD_ROLE, *CATALOGUE_ROLES))
    scale = XmlUnits(units)
    library = view.one('/Library')
    if profile.current_fields:
        organized = library.select('Subfolders/Folder')
        organized.extend(component for component in library.select('Components/Component') if component['SubfolderIndex'] >= 0)
        if organized:
            warn(report, 'receiver-library-folders', 'elixml',
                 'This editor version ignores component-library folder organization in XML.', organized,
                 recoverability='the XML and this library retain folder names and selections; binary and ASC retain them in that editor')
        keys = []
        for category_index, category in enumerate(library.select('Categories/Category')):
            if category['Index'] != category_index:
                keys.append(category)
            for type_index, kind in enumerate(category.children('Type')):
                if kind['Index'] != type_index:
                    keys.append(kind)
                keys.extend(subtype for index, subtype in enumerate(kind.children('Subtype')) if subtype['Index'] != index)
        if keys:
            info(report, 'receiver-category-keys', 'elixml',
                 'This editor version regenerates ordinal catalogue keys when importing XML.', keys,
                 recoverability='classification names and selections remain; this library retains declared XML keys')
    target = XmlBuilder('Library')
    for name, value in (('Type', 'DipTrace-ComponentLibrary'), ('Version', profile.text),
                        ('Name', library['Name']), ('Hint', library['Hint']), ('Units', scale.units)):
        set_attribute(target, name, value)
    if profile.current_fields:
        set_attribute(target, 'UID32', secrets.randbits(32))
    catalog = CategoryCatalog()
    catalog.seed(library.child('Categories'))
    target.append(XmlPlan.from_element(catalog.element))
    if (folders := project_subfolders(library)) is not None:
        target.append(XmlPlan.from_element(folders))
    physical = target.add('Library')
    for name, value in (('Type', 'DipTrace-PatternLibrary'), ('Version', profile.text), ('Units', scale.units)):
        set_attribute(physical, name, value)
    physical.append(XmlPlan('Categories'))
    styles = StylePlans('PadStyles', 'PadStyle', 'Name', 'Pad')
    patterns = StylePlans('Patterns', 'Pattern', 'PatternStyle', 'Physical')
    keys, local_keys = {}, {}
    components = library.select('Components/Component')
    for component in components:
        _adapt_symbols(component, profile, report)
        pattern = component.child('Pattern')
        local_keys[component] = PhysicalKeys(pattern, pins=component.select('Parts/Part/Pins/Pin'),
                                             destination='elixml', report=report)
        if pattern is not None:
            plan = project_pattern(pattern, styles=styles, units=scale, profile=profile,
                                   destination='elixml', report=report, keys=local_keys[component], text_layout=text_layout)
            keys[component] = patterns.include_plan(plan)
    physical.append(styles.plan)
    physical.append(patterns.plan)
    entries = target.add('Components')
    for index, component in enumerate(components):
        entry = entries.add('Component')
        set_attribute(entry, 'Id', index)
        for ordinal, part in enumerate(component.select('Parts/Part')):
            entry.append(_part(part, component, primary=ordinal==0, units=scale, profile=profile,
                               pattern_style=keys.get(component), report=report, keys=local_keys[component], text_layout=text_layout))
    return target.freeze()


@export_diagnostics('elixml')
def dumps(document, *, version=None, units='mm', report=None, text_layout=None):
    return dumps_plan(project_document(document, version=version, units=units, report=report,
                                      text_layout=text_layout), dialect=DIALECT)
