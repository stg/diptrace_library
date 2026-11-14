"""Detached authoring data for pattern serialization."""
from ...common.conversion import warn
from ...common.library_link_projection import prepare_positional_links, report_xml_catalogue_projection
from ...common.library_catalogue import ROLES as CATALOGUE_ROLES
from ...common.library_export import check_fields
from ...common.footprint_objects import new_pattern_drawing
from ..model.document import Document
from ..model.schema import establish_records
from ...common.footprint_text import supply_text_slots
from ...common.unplaced_footprint_frame import normalize_frame


def prepare_export(document, *, destination, report=None):
    if not isinstance(document,Document) or document.representation != 'pattern':
        raise TypeError('pattern output requires an owned pattern-library document')
    document.validate()
    view=document.clone()
    establish_records(view.root)
    view.validate()
    check_fields(view, family='pattern')
    if destination == 'libxml':
        report_xml_catalogue_projection(view, destination=destination, report=report)
    for pattern in view.select('/Library/Patterns/Pattern'):
        pairs = pattern.select('InternalConnections/IntCon')
        if pairs:
            warn(report, 'pattern-internal-connections', destination,
                 'Standalone pattern formats omit electrical internal connections.', pairs,
                 recoverability='the source connections remain; component-library output can retain them')
            for pair in pairs:
                for issue in tuple(view.references._source_issues(pair)):
                    view.references.discard_issue(issue)
                for reference in tuple(view.references.outgoing(pair)):
                    view.references.discard(reference)
                pair.detach()
    if destination in ('lib', 'asc'):
        prepare_positional_links(view, destination=destination, report=report, retained_roles=CATALOGUE_ROLES)
    for pattern in view.select('/Library/Patterns/Pattern'):
        normalize_frame(pattern)
        defaults=new_pattern_drawing()
        for shape in pattern.select('Shapes/Shape'):
            supply_text_slots(shape,defaults)
    return view


def library_omissions(library, *, destination, report=None):
    """Report independently meaningful text-model facts without native slots."""
    for pattern in library.select('Patterns/Pattern'):
        if pattern.get('Sided',False):
            warn(report,'default-pad-side',destination,f'{destination.upper()} does not store a bottom side for the default pad style',
                 (pattern,),recoverability='individual pad sides are retained')
        supplier=pattern.child('Suppliers')
        if supplier is not None:
            extra=[supplier.one(name) for name in ('SourceLocator','MainSupplier') if supplier.get(name)]
            extra.extend(supplier.select('Prices/Quote'))
            if extra:
                warn(report,'supplier-details',destination,f'{destination.upper()} omits supplier source, primary choice and price breaks',extra,
                     recoverability='part number, manufacturer, pattern, supplier and currency are retained')
