"""Detached ASC board drawings, outlines, groups and supplied copper fill."""
import math

from ....common.conversion import warn
from ....common.model import Element
from ....common.picture_sources import prepare_picture_sources
from ....common.units import square_root_area
from ...model import graphic_records as model
from ..errors import PcbError
from .footprint_projection import points as project_points
from .projection import check, collection, fields, flag, rows, value


_PICTURE_NAMES = {'Picture'+name: 'Picture_'+name for name in
                  ('Raster', 'Transparent', 'Width', 'Height', 'Proportions')}


def _omissions(source, report, names, rule):
    omitted = [name for name in names if value(source, name) != source.schema.fields[name].default]
    if omitted:
        warn(report, rule, 'asc', 'PCB ASC omits '+', '.join(omitted), (source,))


def _vector(source, output):
    picture = source.child('PictureVector')
    if picture is None:
        output.add('Vector_Width', 0)
        output.add('Vector_Height', 0)
        output.add('Vector_Polygons')
        return
    check(picture, model.VECTOR)
    output.add('Vector_Width', value(picture, 'Width'))
    output.add('Vector_Height', value(picture, 'Height'))
    polygons = output.add('Vector_Polygons')
    for polygon in collection(picture, 'Polygons', model.VECTOR_POLYGONS, model.VECTOR_POLYGON):
        target = polygons.add('Vector_Polygon').add('Points')
        for point in rows(polygon.one('Points'), model.VECTOR_POINTS, model.VECTOR_POINT):
            target.add('pt', point['X'], point['Y'])


def project_shape(source, *, report=None, legacy_picture_files=None):
    check(source, model.SHAPE)
    if model.layer_scope(source) is not None and source['LayerTarget'] is None:
        raise PcbError(f'{source.path}: select a drawing layer before export')
    output = Element('Shape')
    fields(source, output, exclude=('ShieldGroup', 'PictureFlipped', 'FontMono'),
           names={**_PICTURE_NAMES, 'Layer': 'Type', 'Type': 'ShapeType'})
    output.add('Layer', source['LayId'])
    output.add('OldNumber', source['Id'])
    output.add('Group', source['GroupId'])
    output.add('NetNumber', source['NetNumber'])
    output.add('Orientation', round(float(value(source, 'TextAngle'))/(math.pi/2)))
    lines = collection(source, 'TextLine', model.TEXT_LINES, model.TEXT_LINE)
    output.add('Name', lines[0]['Text'] if lines else '')
    text = output.add('TextLines')
    for line in lines:
        text.add('TextLine', line['Text'])
    _vector(source, output)
    geometry = source.child('Points')
    output.append(Element('Points') if geometry is None else project_points(geometry))
    output.add('RasterIndex', -1)
    prepare_picture_sources((output,), destination='asc', keep_legacy_indices=True,
                            filenames=legacy_picture_files, report=report)
    _omissions(source, report, ('ShieldGroup', 'PictureFlipped', 'FontMono'), 'board-drawing-options')
    return output


def _fill(source, output, *, report=None):
    fill = source.child('Fill')
    if fill is None:
        return False  # Omit optional lists to represent unavailable fill data.
    check(fill, model.FILL)
    for name, width in (('Lines', False), ('SpokeLine', True)):
        actual = collection(fill, name, model.FILL_SPOKES if width else model.FILL_LINES,
                            model.FILL_SPOKE if width else model.FILL_LINE)
        target = output.add(name)
        names = ('X1', 'Y1', 'X2', 'Y2') + (('Width',) if width else ()) + ('RegionId',)
        for line in actual:
            target.add('pt', *(value(line, field) for field in names))
    polygons = output.add('Polygons')
    for polygon in collection(fill, 'Polygons', model.FILL_POLYGONS, model.FILL_POLYGON):
        region = value(polygon, 'RegionId')
        target = polygons.add('Poly', region)
        for point in rows(polygon.one('Points'), model.POINTS, model.POINT):
            target.add('pt', point['X'], point['Y'])
    from ..pour_classification import available
    return available(fill, destination='asc', report=report)


def project_pour(source, *, report=None):
    check(source, model.POUR)
    if source['Layer'] is None:
        raise PcbError(f'{source.path}: select a copper layer before export')
    output = Element('CopperPour')
    fields(source, output, exclude=('MinimumArea', 'RatlineMode', 'ShieldGroup', 'TraceShieldGroup'))
    try:
        output.add('MinimumArea', square_root_area(value(source, 'MinimumArea')))
    except (TypeError, ValueError) as error:
        raise PcbError(f'{source.path}: {error}') from error
    output.add('Group', source['GroupId'])
    output.add('Layer', source['Lay'])
    output.add('NetNumber', source['NetNumber'])
    output.add('OldNumber', source['Id'])
    geometry = source.child('Points')
    output.append(Element('Points') if geometry is None else project_points(geometry))
    output.add('Regions_Counted', flag(_fill(source, output, report=report)))
    _omissions(source, report, ('RatlineMode', 'ShieldGroup', 'TraceShieldGroup'), 'copper-pour-options')
    return output


def project_graphics(board, *, report=None, legacy_picture_files=None):
    """Write board geometry sections; layer-panel visibility is written elsewhere."""
    output = Element('Board')
    output.add('Enabled', flag(value(board, 'Enabled')))
    outline = board.child('Points')
    output.append(Element('Points') if outline is None else project_points(
        outline, schema=model.OUTLINE_POINTS, member=model.OUTLINE_POINT))
    groups = output.add('Groups')
    for group in collection(board, 'Groups', model.COLLECTIONS['Groups'], model.GROUP):
        groups.add('Group', group['Id'], value(group, 'X'), value(group, 'Y'),
                   flag(value(group, 'Enabled')), flag(value(group, 'Selected')), 'N')
    non_signals = output.add('NonSignals')
    for layer in collection(board, 'NonSignals', model.COLLECTIONS['NonSignals'], model.NON_SIGNAL):
        non_signals.add('NonSignal', value(layer, 'Name'), value(layer, 'Color'), layer['Id'], value(layer, 'Side'))
    shapes = output.add('Shapes')
    for shape in collection(board, 'Shapes', model.COLLECTIONS['Shapes'], model.SHAPE):
        shapes.append(project_shape(shape, report=report, legacy_picture_files=legacy_picture_files))
    pours = output.add('CopperPours')
    for pour in collection(board, 'CopperPours', model.COLLECTIONS['CopperPours'], model.POUR):
        pours.append(project_pour(pour, report=report))
    return output
