"""Standalone component ASC from current symbol and attachment data."""
import math

from ....common import footprint_objects
from ....common.asc_library_output import dumps as render
from ....common.asc_library_physical import fields, scalar, project_points, project_pattern
from ....common.asc_model_body import project_model_body
from ....common.asc_text import project_text
from ....common.conversion import export_diagnostics, warn
from ....common.errors import UnsupportedFileError
from ....common.library_font_projection import round_sizes
from ....common.library_versions import LibraryApplicationVersion
from ....common.library_group_bounds import rows as group_rows
from ....common.model import Document, Element
from ..export_view import prepare_export, library_omissions
from ..revisions import ASCII_WRITE_VERSIONS, APPLICATION_VERSIONS


COLLECTIONS = frozenset('''Library Categories Subfolders Components Component Part Pattern
Pins Shapes Groups Layers Pads Holes InternalConnections ModelBody UserFields Dimensions
Pattern_Groups PadPoints Points Point Points_New PadPoints_New PadTerminalCount ShapePoints
PadMask_TopSegments PadMask_BotSegments CategoryTypes PossibleNames TextLines'''.split())

PATTERN_FIELDS = '''Type VariableParameter1 VariableParameter2 VariableParameter3 VariableParameter4
InternalConnections Number1 Number2 Spacing1 Spacing2 VariableParameter5 Spacing3 LockProperties
PatternOrientation Width Height PadWidth PadHeight PadShape SurfacePad PadHole PadHoleH PadHoleType
PadPoints PadPoints_New PadShape_New PadAngle PadShape_X PadShape_Y PadCorner PadWidth_New PadHeight_New
PadTerminalCount TopMask_State BotMask_State TopPaste_State BotPaste_State CustomSwell_New CustomShrink_New
PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide PadMask_TopSegments PadMask_BotSegments
OriginX OriginY Origin_Cross Origin_Circle Origin_Common Origin_Courtyard Name_Description Name_Unique
RecoveryCode RecoveryCode_Generator RecoveryCode_Model Manufacturer Pattern_Groups Pads Shapes Holes Layers
UserFields Dimensions Model3D Mounting CategoryName CategoryIndex CategoryTypes PossibleNames'''.split()


def _pin(pin, index):
    result = Element('Pin', index, pin['X'], pin['Y'])
    fields(pin, result, '''Enabled Locked ModelSig Type Orientation Number Length Name StringNumber
ShowName PinNumXShift PinNumYShift PinNameXShift PinNameYShift ElectricType NameFontSize
NameFontWidth NameFontScale''')
    result.one('PinNameXShift').kind = 'PinNamexShift'
    result.add('SignalDelay', pin.get('SignalDelay', 0))
    result.add('Group', pin['GroupId'])
    fields(pin, result, 'PinNumRotate PinNameRotate')
    return result


def _shape(shape, index, layout):
    result = Element('Shape', index)
    fields(shape, result, 'Enabled Locked VectorFont FontWidth FontScale')
    result.add('Orientation', round(float(shape['TextAngle'])/(math.pi/2)))
    fields(shape, result, 'Type FontSize FontColor FontType FontName')
    lines = shape.select('TextLine/pt')
    result.add('Name', lines[0]['Text'] if lines else '')
    result.add('Width', shape['PenWidth'])
    if shape['Type'] == 10:
        geometry = result.add('Points')
        for point in layout.symbol_bounds(shape):
            geometry.add('pt', *point)
    else:
        result.append(project_points(shape.child('Points_New'), 'Points'))
    fields(shape, result, 'TextAngle TextHorz TextVert TextAlign LineSpacing')
    result.add('Group', shape['GroupId'])
    if shape.select('Points_New/pt'):
        result.append(project_points(shape.one('Points_New'), 'Points_New'))
    if lines:
        text = result.add('TextLines')
        for line in lines:
            text.add('pt', line['Text'])
    return result


def _part(part, component, *, primary, layout):
    result = Element('Part', component['Name'], component['RefDes'])
    fields(part, result, '''Enabled PartType PartName ShowNumbers Type Number1 Number2
Width Height Value LockProperties''')
    result.add('OriginX', part['Origin_X'])
    result.add('OriginY', part['Origin_Y'])
    fields(component, result, 'Datasheet')
    fields(part, result, 'ModelType ModelString')
    result.append(project_model_body(part.one('ModelBody')))
    fields(component, result, 'Manufacturer')
    result.add('CategoryName', component['Component_CategoryName'])
    result.add('CategoryIndex', component['Component_CategoryIndex'])
    classes = component.select('Component_CategoryTypes/CategoryType') if primary else ()
    types = result.add('CategoryTypes', len(classes))
    for row in classes:
        types.add('CategoryType', *row.values)
    fields(component, result, 'SubfolderIndex')
    result.add('Verification', *map(scalar, part['Verification']))
    supplier = component.child('Suppliers') if primary else None
    target = result.add('Suppliers')
    for name in ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency'):
        target.add(name, supplier.get(name, '') if supplier is not None else '')
    pins = result.add('Pins')
    for index, pin in enumerate(part.select('Pins/Pin')):
        pins.append(_pin(pin, index))
    drawings = result.add('Shapes')
    for index, shape in enumerate(part.select('Shapes/Shape')):
        drawings.append(_shape(shape, index, layout))
    groups = result.add('Groups')
    for row in group_rows(part.one('Groups'), layout=layout):
        groups.add('pt', *map(scalar, row))
    layers = result.add('Layers')
    for number in (0, 1):
        layer = layers.add('Layer')
        layer.add('Enabled', 'Y')
        layer.add('Number', number)
        layer.add('Pins')
        layer.add('Shapes')
    users = result.add('UserFields')
    for user in component.select('UserFields/UserField') if primary else ():
        users.add('UserField', user['Name'], user['Value'], user['Type'])
    return result


def _pattern(pattern, *, line_width, layout, report):
    result = project_pattern(pattern, line_width=line_width, layout=layout, report=report,
                             pad_boundaries=True, angle_header=True)
    for suffix in ('Cross', 'Circle', 'Common', 'Courtyard'):
        result.one('Origin'+suffix).kind = 'Origin_'+suffix
    for node in result.select('Pads/Pad/Points') + result.select('Shapes/Points'):
        node.kind = 'Point'
    for node in result.select('CategoryTypes/CategoryTypeType'):
        node.kind = 'CategoryType'
    result.append(project_points(pattern.child('PadPoints'), 'PadPoints_New'))
    for pad in result.select('Pads/Pad'):
        if pad.scalar('Number_New') == -1 and not pad.one('PadPoints_New').children():
            pad.one('PadPoints_New').detach()
    connections = result.add('InternalConnections')
    for pair in pattern.select('InternalConnections/IntCon'):
        connections.add('IntCon', *pair.values)
    for name in PATTERN_FIELDS:
        result.one(name).move_to(result)
    return result


@export_diagnostics('asc')
def project_document(document, *, version=None, report=None, encoding='cp1252', line_width=None, text_layout=None,
                     target_application=None):
    if version is not None and version not in ASCII_WRITE_VERSIONS:
        raise UnsupportedFileError(family='component', format='asc', version=version, reason='version')
    view = prepare_export(document, destination='asc', report=report)
    profile = LibraryApplicationVersion.select(target_application, family='component', format='asc', applications=APPLICATION_VERSIONS)
    if not profile.current_fields:
        sizes = [(pin, 'NameFontSize') for pin in view.select('/Library/Components/Component/Parts/Part/Pins/Pin')]
        sizes.extend((shape, 'FontSize') for shape in view.select('/Library/Components/Component/Parts/Part/Shapes/Shape'))
        sizes.extend((node, 'FontSize') for path in ('Shapes/Shape', 'Dimensions/Dimension')
                     for node in view.select('/Library/Components/Component/Pattern/'+path))
        round_sizes(sizes, destination='asc', report=report)
    library_omissions(view, destination='asc', report=report)
    library = view.one('/Library')
    result = Document(representation='asc')
    result.root.add('Source', 'DipTrace-ElementLibrary', ASCII_WRITE_VERSIONS[-1])
    target = result.root.add('Library')
    fields(library, target, 'Name Hint')
    folders = target.add('Subfolders')
    for folder in library.select('Subfolders/Folder'):
        folders.add('Subfolder', folder['Name'])
    categories = library.select('Categories/Category')
    catalog = target.add('Categories', len(categories))
    for category in categories:
        types = category.children('Type')
        row = catalog.add('Category', category['Name'], category['Index'], len(types))
        for kind in types:
            subtypes = kind.children('Subtype')
            nested = row.add('Type', kind['Name'], kind['Index'], len(subtypes))
            for subtype in subtypes:
                nested.add('SubType', subtype['Name'], subtype['Index'])
    layout = text_layout if text_layout is not None else profile.text_layout()
    pen = line_width if line_width is not None else lambda layer: .3
    entries = target.add('Components')
    for component in library.select('Components/Component'):
        entry = entries.add('Component')
        for index, part in enumerate(component.select('Parts/Part')):
            entry.append(_part(part, component, primary=index==0, layout=layout))
        pattern = component.child('Pattern')
        entry.append(_pattern(pattern if pattern is not None else footprint_objects.new_pattern(),
                              line_width=pen, layout=layout, report=report))
        mono = [pin for pin in component.select('Parts/Part/Pins/Pin') if pin.get('NameFontMono', False)]
        mono.extend(shape for shape in component.select('Parts/Part/Shapes/Shape') if shape.get('FontMono', False))
        if mono:
            warn(report, 'monospaced-font', 'asc', 'ASC omits monospaced vector-font selection', mono)
    project_text(result, encoding=encoding, report=report)
    return result


@export_diagnostics('asc')
def dumps(document, *, version=None, report=None, encoding='cp1252', line_width=None, text_layout=None,
          target_application=None):
    projected = project_document(document, version=version, report=report, encoding=encoding,
                                 line_width=line_width, text_layout=text_layout, target_application=target_application)
    return render(projected, collections=COLLECTIONS)
