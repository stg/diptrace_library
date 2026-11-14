"""Standalone ASC physical geometry shared by library-family writers."""
import math
from decimal import Decimal

from . import footprint_objects, footprint_records
from .asc_footprints import model3d_arguments, project_terminals
from .asc_pad_geometry import PadContour, legacy_pad_contour
from .conversion import info, warn
from .model import Element, Value
from .pad_masks import MASK_FIELDS
from .text.vector_layout import pattern_vector_text_bounds
from .library_group_bounds import rows as group_rows


def scalar(value):
    return 'Y' if value is True else 'N' if value is False else value


def fields(source, target, names):
    for name in names.split():
        target.add(name, scalar(source[name]))


def project_points(source, name, *, counted=False):
    members = source.children('pt') if source is not None else ()
    result = Element(name, *((len(members),) if counted else ()))
    for member in members:
        result.add('pt', *member.values)
    return result


def _masks(source, target):
    fields(source, target, 'PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
    for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
        target.append(project_points(source.child(name), name, counted=True))


def project_pad(pad, index, report):
    result = Element('Pad', index, pad['StringNumber'], pad['Name'], pad['X'], pad['Y'])
    kind, angle = pad['PadShape_New'], float(pad['PadAngle'])
    inverted = abs(angle) >= .001 and abs(angle-math.pi) >= .001
    modern = tuple(row.values for row in pad.select('PadPoints_New/pt'))
    if round(math.degrees(angle)) % 90 or kind >= 3 or kind == 2 and pad['PadCorner'] != 0:
        legacy = legacy_pad_contour(kind, pad['PadWidth_New'], pad['PadHeight_New'],
            pad['PadCorner'], modern, angle-math.pi/2 if inverted else angle)
    else:
        legacy = PadContour(kind, pad['PadWidth_New'], pad['PadHeight_New'], modern)
    result.add('Number', -1 if kind == 20 else index)
    result.add('Number_New', index)
    result.add('Inverted', scalar(inverted))
    fields(pad, result, 'Locked Sided')
    for name in MASK_FIELDS:
        state = pad[name]
        values = (True, 2) if state == 2 else (False, state if state < 3 else 0, state)
        result.add(name, *map(scalar, values))
    for old, new, states in (('CustomSwell', 'CustomSwell_New', MASK_FIELDS[:2]),
                              ('CustomShrink', 'CustomShrink_New', MASK_FIELDS[2:])):
        result.add(old, -1000 if any(pad[name] == 3 for name in states) else pad[new])
    fields(pad, result, 'CustomSwell_New CustomShrink_New')
    result.add('PadWidth', legacy.width)
    result.add('PadHeight', legacy.height)
    fields(pad, result, 'PadHole PadHoleH PadHoleType SurfacePad')
    result.add('PadShape', legacy.shape)
    fields(pad, result, 'PadShape_New PadAngle PadShape_X PadShape_Y PadCorner PadWidth_New PadHeight_New')
    result.add('Group', pad.get('GroupId', -1))
    standard = pad['Standard'] and abs(angle) < .001
    result.add('Standard', scalar(standard))
    if standard != pad['Standard']:
        info(report, 'rotated-default-pad', 'asc',
             'ASC represents a rotated default pad with its explicit physical settings', (pad,),
             recoverability='binary loading can reconstruct default-style membership from these settings')
    points = result.add('Points')
    for point in legacy.points:
        points.add('pt', *point)
    # Always include the authoritative contour, avoiding dependence on a
    # receiver's comparison of redundant legacy polygon coordinates.
    result.append(project_points(pad.child('PadPoints_New'), 'PadPoints_New'))
    result.append(project_terminals(pad, convert=lambda value: Value.of(scalar(value.value))))
    _masks(pad, result)
    return result


def project_drawing(shape, pattern, *, line_width, layout, angle_header=False):
    kind, layer = shape['Type'], shape['Layer']
    points = tuple(point.values for point in shape.select('Points_New/pt'))
    if kind == 7:
        corners = tuple(pattern_vector_text_bounds(shape, font=getattr(layout, 'vector_metrics', None))
                        if shape['VectorFont'] else layout.pattern_bounds(shape))
    else:
        corners = points[:3] if len(points) > 1 else ()
    scales = pattern['Width'], pattern['Height']
    compatibility = [0.]*6
    for index, point in enumerate(corners):
        compatibility[index*2:index*2+2] = [value/scale for value, scale in zip(point, scales)]
    legacy_layer = (1 if layer in (16, 18, 20) else 6 if layer in (17, 19, 21)
                    else 1 if layer > 14 else layer)
    width = line_width(layer) if shape['Width'] < 0 else shape['Width']
    if (isinstance(width, bool) or not isinstance(width, (int, float, Decimal))
            or not math.isfinite(float(width)) or width < 0):
        raise ValueError('ASC fallback line width requires a finite nonnegative number')
    text = shape.select('TextLine/pt')
    header = (kind, scalar(shape['Locked']), legacy_layer, *compatibility,
        text[0]['Text'] if text else '', shape['FontName'], scalar(shape['VectorFont']),
        shape['FontSize'], shape['FontScale'], shape['FontWidth'],
        shape['TextAngle'] if angle_header else round(float(shape['TextAngle'])/(math.pi/2)), width, shape['TextShow'])
    result = [Element('Shape', *header)]
    if points:
        normalized = Element('Points')
        for point in points:
            normalized.add('pt', *(value/scale for value, scale in zip(point, scales)))
        result.append(normalized)
    for name in ('Width', 'Layer', 'TextHorz', 'TextVert', 'TextAlign', 'LineSpacing', 'TextAngle'):
        result.append(Element(name, scalar(shape[name])))
    if points:
        result.append(project_points(shape.child('Points_New'), 'Points_New'))
    if text:
        lines = Element('TextLines', len(text))
        for line in text:
            lines.add('pt', line['Text'])
        result.append(lines)
    result.extend((Element('AllLayers', scalar(shape['AllLayers'])), Element('Group', shape.get('GroupId', -1))))
    return result


def project_pattern(pattern, *, line_width, layout, report, pad_boundaries=False, angle_header=False):
    result = Element('Pattern', pattern['Name'])
    fields(pattern, result, '''VariableParameter1 VariableParameter2 VariableParameter3 VariableParameter4
Width Height Spacing1 Spacing2 VariableParameter5 Spacing3 LockProperties PatternOrientation
Number1 Number2 Type PadWidth PadHeight PadShape SurfacePad PadHole PadHoleH PadHoleType''')
    result.append(project_points(pattern.child('PadPoints'), 'PadPoints'))
    result.add('PadShape_New', pattern['PadShape'])
    result.add('PadAngle', 0)
    fields(pattern, result, 'PadShape_X PadShape_Y PadCorner')
    result.add('PadWidth_New', pattern['PadWidth'])
    result.add('PadHeight_New', pattern['PadHeight'])
    result.append(project_terminals(pattern, convert=lambda value: Value.of(scalar(value.value))))
    fields(pattern, result, '''PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide
TopMask_State BotMask_State TopPaste_State BotPaste_State CustomSwell_New CustomShrink_New''')
    for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
        result.append(project_points(pattern.child(name), name, counted=True))
    pads = result.add('Pads')
    members = pattern.select('Pads/Pad')
    boundary = footprint_objects.new_pad()
    for index, pad in enumerate((boundary, *members, boundary) if pad_boundaries else members, 0 if pad_boundaries else 1):
        number = -1 if pad_boundaries and index in (0, len(members)+1) else index
        row = project_pad(pad, number, report)
        row.set_argument(0, index)
        pads.append(row)
    shapes = result.add('Shapes')
    boundary = footprint_objects.new_pattern_drawing()
    for shape in (boundary, *pattern.select('Shapes/Shape'), boundary):
        for node in project_drawing(shape, pattern, line_width=line_width, layout=layout, angle_header=angle_header):
            shapes.append(node)
    holes = result.add('Holes')
    holes.add('Hole', 'N', 'N', 0, 0, 0, 0, -1)
    for hole in pattern.select('Holes/Hole'):
        holes.add('Hole', *(scalar(hole[name]) for name in ('Enabled', 'Locked', 'X', 'Y', 'Diam', 'HoleDiam', 'GroupId')))
    holes.add('Hole', 'N', 'N', 0, 0, 0, 0, -1)
    fields(pattern, result, '''OriginX OriginY OriginCross OriginCircle OriginCommon OriginCourtyard
Name_Description Name_Unique RecoveryCode RecoveryCode_Generator RecoveryCode_Model''')
    result.add('Manufacturer', pattern['Pattern_Manufacturer'])
    groups = result.add('Pattern_Groups')
    for row in group_rows(pattern.one('Pattern_Groups'), layout=layout):
        groups.add('pt', *map(scalar, row))
    layers = result.add('Layers')
    for number, name, members in ((0, 'Pads', pattern.select('Pads/Pad')),
                                  (1, 'Shapes', pattern.select('Shapes/Shape')),
                                  (2, 'Holes', pattern.select('Holes/Hole'))):
        layer = layers.add('Layer')
        layer.add('Enabled', 'Y')
        layer.add('Number', number)
        for collection in (('Pads', 'Shapes', 'Holes') if number < 2 else ('Holes',)):
            rows = layer.add(collection)
            if collection == name:
                for index in range(1, len(members)+1):
                    rows.add('pt', index)
    users = result.add('UserFields')
    for user in pattern.select('UserFields/UserField'):
        users.add('UserField', user['Name'], user['Value'], user['Type'])
    dimensions = result.add('Dimensions')
    for dimension in pattern.select('Dimensions/Dimension'):
        row = dimensions.add('Dimension')
        for name in footprint_records.DIMENSION.fields:
            if name not in ('Index', 'FontMono', 'Group'):
                row.add(name, scalar(dimension[name]))
        row.add('Group', dimension['GroupId'])
    model = pattern.one('Model3D')
    target = result.add('Model3D')
    fields(model, target, 'Model3DFile Model3DFile_Variable')
    target.add('pt', *(scalar(value.value) for value in model3d_arguments(model)))
    fields(pattern, result, 'Mounting')
    result.add('CategoryName', pattern['Pattern_CategoryName'])
    result.add('CategoryIndex', pattern['Pattern_CategoryIndex'])
    rows = pattern.select('Pattern_CategoryTypes/CategoryType')
    categories = result.add('CategoryTypes', len(rows))
    for row in rows:
        categories.add('CategoryTypeType', *row.values)
    names = pattern.select('PossibleNames/PossibleName')
    possible = result.add('PossibleNames', len(names))
    for name in names:
        possible.add('PossibleName', name['Name'])
    omitted = [shape for shape in pattern.select('Shapes/Shape') if shape['PadId'] >= 0]
    if omitted:
        warn(report, 'drawing-pad-reference', 'asc', 'ASC omits drawing-to-pad associations', omitted)
    mono = [owner for owner in (*pattern.select('Shapes/Shape'), *pattern.select('Dimensions/Dimension'))
            if owner.get('FontMono', False)]
    if mono:
        warn(report, 'monospaced-font', 'asc', 'ASC omits monospaced vector-font selection', mono)
    return result
