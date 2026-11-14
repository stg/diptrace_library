"""Generate standalone ASC from current pattern objects and explicit defaults."""
from ....common.asc_library_physical import scalar as _scalar, fields as _fields, project_pattern
from ....common.asc_text import project_text
from ....common.conversion import export_diagnostics
from ....common.errors import UnsupportedFileError
from ....common.library_font_projection import round_sizes
from ....common.library_versions import LibraryApplicationVersion
from ....common.model import Document, Element
from ..export_view import prepare_export, library_omissions
from .syntax import dumps as render
from ..revisions import APPLICATION_VERSIONS, ASCII_WRITE_VERSIONS


def _pattern(pattern, *, line_width, layout, report):
    result = project_pattern(pattern, line_width=line_width, layout=layout, report=report)
    result.set_values(pattern['Name'], pattern.get('RefDes', ''))
    result.insert(Element('Value', pattern.get('Value', '')), 0)
    result.insert(Element('Datasheet', pattern.get('Datasheet', '')),
                  result.children().index(result.one('CategoryName')))
    result.add('Verification', *map(_scalar, pattern['Verification']))
    supplier = pattern.child('Suppliers')
    target = result.add('Suppliers')
    for name in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency'):
        target.add(name, supplier.get(name, '') if supplier is not None else '')
    return result


@export_diagnostics('asc')
def project_document(document, *, version=None, report=None, encoding='cp1252', line_width=None, text_layout=None,
                     target_application=None):
    if version is not None and version not in ASCII_WRITE_VERSIONS:
        raise UnsupportedFileError(family='pattern', format='asc', version=version, reason='version')
    document = prepare_export(document, destination='asc', report=report)
    profile = LibraryApplicationVersion.select(target_application, family='pattern', format='asc', applications=APPLICATION_VERSIONS)
    if not profile.current_fields:
        sizes = ((node, 'FontSize') for path in ('Shapes/Shape', 'Dimensions/Dimension')
                 for node in document.select('/Library/Patterns/Pattern/'+path))
        round_sizes(sizes, destination='asc', report=report)
    library = document.one('/Library')
    library_omissions(library, destination='asc', report=report)
    result = Document(representation='asc')
    result.root.add('Source', 'DipTrace-ComLibrary', ASCII_WRITE_VERSIONS[-1])
    target = result.root.add('Library')
    patterns = library.select('Patterns/Pattern')
    target.add('Size', len(patterns))
    _fields(library, target, 'Name Hint')
    entries = library.select('Categories/Category')
    categories = target.add('Categories', len(entries))
    for category in entries:
        kinds = category.children('Type')
        row = categories.add('Category', category['Name'], category['Index'], len(kinds))
        for kind in kinds:
            subtypes = kind.children('Subtype')
            nested = row.add('Type', kind['Name'], kind['Index'], len(subtypes))
            for subtype in subtypes:
                nested.add('SubType', subtype['Name'], subtype['Index'])
    target_patterns = target.add('Patterns')
    layout = text_layout if text_layout is not None else profile.text_layout()
    pen = line_width if line_width is not None else lambda layer: .3
    for pattern in patterns:
        target_patterns.append(_pattern(pattern, line_width=pen, layout=layout, report=report))
    project_text(result, encoding=encoding, report=report)
    return result


@export_diagnostics('asc')
def dumps(document, *, version=None, report=None, encoding='cp1252', line_width=None, text_layout=None,
          target_application=None):
    projected = project_document(document, version=version, report=report, encoding=encoding,
                                 line_width=line_width, text_layout=text_layout, target_application=target_application)
    return render(projected)
