"""Current PCB footprint geometry in ASC's flat component dialect."""
from ....common import drawing_records as drawing, footprint_records as physical
from ....common.asc_footprints import model3d_arguments, project_terminals as _terminal_view
from ....common.conversion import warn
from ....common.model import Element, Value
from ...model import definitions as model, graphic_records, pad_records
from ...model.objects import new_pad, new_pattern_drawing
from ..errors import PcbError
from ..output_indices import pad_number
from ..assembly.missing_geometry import DIMENSIONS
from .vocabulary import PAD_FIELD_NAMES
from .projection import check, collection, fields, flag, rows, value
from .teardrops import PARAMETERS
from .dimension_projection import project_dimensions


_PAD_LABELS = {current: saved for saved, current in PAD_FIELD_NAMES.items()}
_TEARDROP_LABELS = {current: saved for saved, current in PARAMETERS.items() if saved != 'TearDrop_Trace'}


def _scalar(argument):
    return Value(flag(argument.value), 'string') if argument.kind == 'boolean' else argument


def points(source, *, kind=None, schema=drawing.POINTS, member=drawing.POINT, counted=False, row_kind='pt'):
    members = rows(source, schema, member)
    output = Element(kind or source.kind, *((len(members),) if counted else ()))
    for point in members:
        output.add(row_kind, *(_scalar(argument) for argument in point.arguments))
    return output


def project_terminals(owner):
    for terminal in owner.children('PadTerminal'):
        check(terminal, physical.TERMINAL)
        if (contour := terminal.child('ShapePoints')) is not None:
            rows(contour, drawing.POINTS, drawing.POINT)
    return _terminal_view(owner, container='PadTerminals', counted=False,
                          points_counted=False, convert=_scalar)


def project_parameters(owner, output):
    if (parameters := owner.child('TeardropParams')) is not None:
        check(parameters, pad_records.TEARDROP)
        fields(parameters, output, names=_TEARDROP_LABELS)


def project_pad(pad, *, index=None, boundary=False, report=None):
    check(pad, model.PAD)
    if value(pad, 'ShieldGroup') != -1:
        warn(report, 'pad-shield-group', 'asc', 'ASC omits pad shield-group membership', (pad,))
    index = pad_number(pad) if index is None else index
    output = Element('Pad', index, pad['StringNumber'], pad['Name'], pad['X'], pad['Y'])
    fields(pad, output, exclude=('StringNumber', 'Name', 'X', 'Y', 'Id', 'ShieldGroup'), names=_PAD_LABELS)
    for name in DIMENSIONS:
        field = output.child(_PAD_LABELS.get(name, name))
        if field is not None and field.values == (None,):
            field.set_values(-1)
    output.add('Number', -1 if boundary else index)
    output.add('NetNumber', pad['NetNumber'])
    output.add('IntOwner', pad['InternalConnection'])
    output.append(project_terminals(pad))
    for name in ('PadPoints_New', 'PadMask_TopSegments', 'PadMask_BotSegments'):
        if (source := pad.child(name)) is not None:
            paste = name != 'PadPoints_New'
            output.append(points(source, kind=_PAD_LABELS.get(name, name),
                schema=physical.PASTE_SEGMENTS if paste else drawing.POINTS,
                member=physical.PASTE_SEGMENT if paste else drawing.POINT))
    for name in ('HideLayer', 'BlindLayer'):
        target = output.add(name)
        for source in collection(pad, name, pad_records.COLLECTIONS[name], pad_records.LAYER_MEMBER):
            target.add('pt', source['Lay'])
    thermals = output.add('CustomSpokes')
    for thermal in collection(pad, 'CustomSpokes', pad_records.COLLECTIONS['CustomSpokes'], pad_records.THERMAL):
        row = thermals.add('CustomSpoke')
        for name, current in (('Layer', thermal['Lay']), ('Type', value(thermal, 'Type')),
                              ('Spoke', value(thermal, 'Spoke')), ('Width', value(thermal, 'Width'))):
            row.add(name, current)
    project_parameters(pad, output)
    if pad.child('UnresolvedKeys') is not None:
        raise PcbError(f'{pad.path}: unresolved pad extensions need an ASC mapping')
    if pad.child('Id') is not None:
        warn(report, 'pad-persistent-key', 'asc', 'ASC generates positional pad keys', [pad],
             recoverability='pad geometry and identity-based connections remain; the independent key is omitted')
    return output


def project_pads(pattern, *, report=None):
    pads = collection(pattern, 'Pads', model.COLLECTIONS['ComponentPads'], model.PAD)
    output = Element('Pads')
    def boundary(index):
        pad = new_pad()
        model.establish_records(pad)
        return project_pad(pad, index=index, boundary=True)
    output.append(boundary(0))
    for pad in pads:
        output.append(project_pad(pad, report=report))
    output.append(boundary(len(pads)+1))
    return output


def project_model(model3d):
    check(model3d, physical.MODEL3D)
    for name, schema in physical.VECTORS.items():
        check(model3d.one(name), schema)
    output = Element('Model3D')
    fields(model3d, output, exclude=('Mirror', 'NoSearch', 'Units'),
           names={'IPC_XOff': 'IPC_X', 'IPC_YOff': 'IPC_Y', 'Type': 'ModelType'})
    output.add('pt', *(_scalar(argument) for argument in model3d_arguments(
        model3d, fields=('Mirror', 'NoSearch', 'Units'))))
    return output


def project_drawing(shape, *, report=None):
    check(shape, model.PATTERN_SHAPE)
    if value(shape, 'ShieldGroup') != -1:
        warn(report, 'pattern-shield-group', 'asc', 'ASC omits drawing shield-group membership', (shape,))
    if value(shape, 'PadId') != -1:
        warn(report, 'placed-drawing-pad', 'asc',
             'ASC omits a placed drawing pad association; geometry remains.', (shape,))
    lines = collection(shape, 'TextLine', drawing.TEXT_LINES, drawing.TEXT_LINE)
    output = Element('Shape', shape['Type'], flag(shape['Locked']), shape['Layer'],
        0, 0, 0, 0, 0, 0, lines[0]['Text'] if lines else '', shape['FontName'],
        flag(shape['VectorFont']), shape['FontSize'], shape['FontScale'], shape['FontWidth'],
        shape['TextAngle'], shape['Width'], shape['TextShow'])
    for name in ('TextHorz', 'TextVert', 'TextAlign', 'LineSpacing', 'AllLayers', 'Group', 'Width'):
        current = shape[name]
        output.add(name, flag(current) if isinstance(current, bool) else current)
    output.add('Marking_Generated', flag(value(shape, 'MarkingGenerated')))
    geometry = shape.child('Points_New')
    output.append(points(geometry, kind='Points') if geometry is not None else Element('Points'))
    text = output.add('TextLines')
    for line in lines:
        text.add('TextLine', line['Text'])
    if value(shape, 'FontMono'):
        warn(report, 'pattern-font-monospace', 'asc', 'ASC omits footprint monospaced-font settings', [shape],
             recoverability='current font, text and geometry remain')
    if shape.child('UnresolvedKeys') is not None:
        raise PcbError(f'{shape.path}: unresolved drawing extensions need an ASC mapping')
    return output


def project_drawings(pattern, *, report=None):
    output = Element('Shapes')
    boundary = new_pattern_drawing()
    model.establish_records(boundary)
    shapes = collection(pattern, 'Shapes', model.COLLECTIONS['PatternShapes'], model.PATTERN_SHAPE)
    for shape in (boundary, *shapes, boundary):
        record = project_drawing(shape, report=report)
        children = tuple(record.children())
        output.append(record)
        for child in children:
            child.move_to(output)
    return output


def project_holes(pattern):
    output = Element('Holes')
    source = pattern.child('Holes')
    if source is not None:
        check(source, graphic_records.COLLECTIONS['Holes'])
    output.add('Hole', 'N', 'N', 0, 0, 0, 0, -1)
    for hole in (() if source is None else source.children()):
        check(hole, physical.HOLE)
        if hole.child('UnresolvedKeys') is not None:
            raise PcbError(f'{hole.path}: unresolved hole extensions need an ASC mapping')
        output.add('Hole', *(_scalar(argument) for argument in hole.arguments))
    output.add('Hole', 'N', 'N', 0, 0, 0, 0, -1)
    return output
