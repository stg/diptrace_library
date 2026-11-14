"""Detached current component data for destination-specific serialization."""
from ...common import footprint_objects, symbol_objects
from ...common.conversion import warn
from ...common.library_link_projection import prepare_positional_links, report_xml_catalogue_projection
from ...common.library_catalogue import ROLES as CATALOGUE_ROLES
from ...common.library_export import check_fields
from ...common.footprint_text import supply_text_slots as supply_physical_text
from ...common.symbol_text_style import supply_text_slots as supply_symbol_text
from ...common.unplaced_footprint_frame import normalize_frame as normalize_physical_frame
from ...common.unplaced_symbol_frame import normalize_frame as normalize_symbol_frame
from ..model.document import Document
from ..model.schema import establish_records
from ..model.metadata import FOLDER_ROLE
from ..model.text_fields import ROLE as USER_FIELD_ROLE


def prepare_export(document, *, destination=None, report=None):
    if not isinstance(document, Document) or document.representation != 'component':
        raise TypeError('component output requires an owned component-library document')
    document.validate()
    view = document.clone()
    establish_records(view.root)
    check_fields(view, family='component')
    if destination == 'elixml':
        report_xml_catalogue_projection(view, destination=destination, report=report)
    if destination is not None:
        for issue in tuple(view.references.issues):
            if issue.message.startswith(FOLDER_ROLE+':'):
                issue.source['Folder'] = None
                warn(report, 'unresolved-library-folder', destination,
                     'An unavailable library folder exports as unassigned.', (issue.source,),
                     recoverability='the missing folder selection remains editable in the source model')
    if destination in ('eli', 'asc'):
        from ..model import symbols
        prepare_positional_links(view, destination=destination, report=report,
                                 roles={symbols.GROUP_ROLE: 'Group', symbols.PAD_ROLE: 'Pad'},
                                 retained_roles=(USER_FIELD_ROLE, *CATALOGUE_ROLES))
    symbol_defaults = symbol_objects.new_drawing()
    physical_defaults = footprint_objects.new_pattern_drawing()
    for component in view.select('/Library/Components/Component'):
        for part in component.select('Parts/Part'):
            normalize_symbol_frame(part)
            for shape in part.select('Shapes/Shape'):
                supply_symbol_text(shape, symbol_defaults)
        if (pattern := component.child('Pattern')) is not None:
            normalize_physical_frame(pattern)
            for shape in pattern.select('Shapes/Shape'):
                supply_physical_text(shape, physical_defaults)
    view.validate()
    return view


def library_omissions(document, *, destination, report):
    for component in document.select('/Library/Components/Component'):
        if (pattern := component.child('Pattern')) is not None:
            for name, rule in (('Datasheet', 'footprint-datasheet'), ('RefDes', 'footprint-default-reference')):
                if pattern.get(name):
                    warn(report, rule, destination, 'This format omits the attached footprint '+name+'.', (pattern,))
            if pattern.get('Sided', False):
                warn(report, 'default-pad-side', destination,
                     'This format omits a bottom side for the default pad style; individual pad sides remain.', (pattern,))
        supplier = component.child('Suppliers')
        if supplier is not None:
            extra = [supplier.one(name) for name in ('SourceLocator', 'MainSupplier') if supplier.get(name)]
            extra.extend(supplier.select('Prices/Quote'))
            if extra:
                warn(report, 'supplier-details', destination,
                     'This format omits supplier source, primary choice and price breaks.', extra)
