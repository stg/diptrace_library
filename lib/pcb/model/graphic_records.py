"""PCB drawings, copper pours and groups over the common editable tree."""
from dataclasses import replace

from ...common.schema import Child, Field, Record
from ...common.drawing_records import POINT, TEXT_LINE, POINTS, TEXT_LINES
from ...common import footprint_records
from .relationships import reference_field, index_field, linked
from . import pour_regions
from .non_signal_layers import SELECTION_FIELDS


COPPER_LAYER_FAMILY = 3
NON_SIGNAL_LAYER_FAMILY = 15


def _fields(kind, names, default):
    return {name: Field(name, kind, default=default) for name in names.split()}


def _order(name='Id'):
    return Field(name, 'integer', getter=lambda node: node._ordinal(), ordinal_dependencies=lambda node: (node,))


GROUP_FIELDS = {'Group': reference_field('Group', 'pcb-group'), 'GroupId': index_field('GroupId', 'pcb-group')}
NET_FIELDS = {'Net': reference_field('Net', 'graphic-net'), 'NetId': index_field('NetId', 'graphic-net'),
              'NetNumber': index_field('NetNumber', 'graphic-net')}
GROUP = Record('PcbGroup', {
    'Id': _order(), **_fields('boolean', 'Enabled Selected', False),
    **{name: Field(name, 'number', default=0, unit='shared length') for name in ('X', 'Y')},
}, parameters=('Id', 'X', 'Y'))
NON_SIGNAL = Record('PcbNonSignalLayer', {
    'Name': Field('Name', 'text', default=''), 'Id': _order(),
    'Color': Field('Color', 'integer', default=0), 'Side': Field('Side', 'integer', default=0),
    'Visible': Field('Visible', 'boolean', description='Optional layer-panel visibility supplied by the document.'),
}, parameters=('Name',))


def layer_scope(shape):
    """Only copper and custom non-signal families have a target selector."""
    return {COPPER_LAYER_FAMILY: 'Layers', NON_SIGNAL_LAYER_FAMILY: 'NonSignals'}.get(shape.get('Layer', 0))


SHAPE = Record('PcbBoardDrawing', {
    'Id': _order(), **GROUP_FIELDS, **NET_FIELDS,
    'LayerTarget': reference_field('LayerTarget', 'drawing-layer'),
    'LayId': Field('LayId', 'integer',
        getter=lambda shape: layer._ordinal() if (layer := linked(shape, 'drawing-layer')) is not None
            else -1 if layer_scope(shape) is not None else 0,
        reference_dependencies=lambda shape: ((shape, 'drawing-layer', 'outgoing'),),
        ordinal_dependencies=lambda shape: (layer,) if (layer := linked(shape, 'drawing-layer')) is not None else (),
        value_dependencies=lambda shape: ((shape, 'Layer'),)),
    **_fields('boolean', 'Enabled Selected AllLayers Locked VectorFont PanelExclude Inverted '
                         'PictureProportions PictureRaster PictureFlipped FontMono', False),
    **_fields('integer', 'Layer Type Color BrushColor FontColor TextHorz TextVert TextAlign', 0),
    'ShieldGroup': Field('ShieldGroup', 'integer', default=-1),
    **_fields('number', 'PenWidth FontSize FontWidth FontScale LineSpacing TextAngle PictureWidth PictureHeight '
                        'PictureTransparent', 0),
    **_fields('text', 'FontName Picture_File Picture_File_Variable', ''),
    'BitmapIndex': Field('BitmapIndex', 'integer', default=-1,
        description='Unresolved external companion-table reference; -1 when file-backed or unassigned.'),
}, parameters=('Id',), children={
    'Points': Child('Points', POINTS.name),
    'TextLine': Child('TextLine', TEXT_LINES.name), 'PictureVector': Child('PictureVector', 'PcbVectorPicture'),
})
POUR = Record('PcbCopperPour', {
    'Id': _order(), **GROUP_FIELDS, **NET_FIELDS,
    'Layer': reference_field('Layer', 'copper-layer'), 'Lay': index_field('Lay', 'copper-layer'),
    **_fields('boolean', 'Enabled Selected Poured UseNetClearance Locked SnapToBoard IslandRegion '
                         'IslandInternal IslandConnection ViaDirect SMD_Separate PanelExclude', False),
    **_fields('integer', 'Type Spoke SMD_Spoke Priority RatlineMode', 0),
    **_fields('integer', 'ShieldGroup TraceShieldGroup', -1),
    **{name: Field(name, 'number', default=0, unit='shared length') for name in
       ('LineWidth', 'Clearance', 'LineSpacing', 'SpokeWidth', 'BoardClearance', 'SMD_SpokeWidth')},
    'MinimumArea': Field('MinimumArea', 'number', default=0, unit='shared length squared'),
}, parameters=('Id',), children={
    'Points': Child('Points', POINTS.name), 'Fill': Child('Fill', 'PcbPourFill'),
})
FILL_LINE = Record('PcbFillLine', {
    **{name: Field(name, 'number', default=0, unit='shared length') for name in ('X1', 'Y1', 'X2', 'Y2')},
    **pour_regions.FIELDS,
})
FILL_SPOKE = replace(FILL_LINE, name='PcbSpokeLine', fields={**FILL_LINE.fields,
    'Width': Field('Width', 'number', default=0, unit='shared length')})
FILL_POLYGON = Record('PcbFillPolygon', pour_regions.FIELDS, children={
    'Points': Child('Points', POINTS.name),
})
FILL = Record('PcbPourFill', {}, children={
    'Lines': Child('Lines', 'PcbFillLines'), 'SpokeLine': Child('SpokeLine', 'PcbSpokeLines'),
    'Polygons': Child('Polygons', 'PcbFillPolygons'),
    'Regions': Child('Regions', pour_regions.REGIONS.name),
})
HOLE = footprint_records.HOLE
PATTERN_DIMENSION = replace(footprint_records.DIMENSION, name='PcbPatternDimension')
DIMENSION = replace(footprint_records.DIMENSION, name='PcbDimension',
    fields={**footprint_records.DIMENSION.fields, **GROUP_FIELDS,
            **_fields('boolean', 'Selected PanelExclude', False), **SELECTION_FIELDS})
VECTOR_POINT = Record('PcbVectorPoint', {'Id': _order(), **POINT.fields}, parameters=('Id',))
VECTOR_POLYGON = Record('PcbVectorPolygon', {'Id': _order()}, parameters=('Id',), children={
    'Points': Child('Points', 'PcbVectorPoints'),
})
VECTOR = Record('PcbVectorPicture', _fields('number', 'Width Height', 0), children={
    'Polygons': Child('Polygons', 'PcbVectorPolygons'),
})
OUTLINE_POINT = replace(POINT, name='PcbOutlinePoint',
    fields={**POINT.fields, 'Arc': Field('Arc', 'boolean', required=True, default=False)},
    parameters=('X', 'Y', 'Arc'))
OUTLINE_POINTS = Record('PcbOutlinePoints', {}, children={
    'pt': Child('pt', OUTLINE_POINT.name, maximum=None)})


def _collection(name, kind, record):
    return Record(name, {}, children={kind: Child(kind, record.name, maximum=None)})


COLLECTIONS = {
    'Points': OUTLINE_POINTS,
    'Groups': _collection('PcbGroups', 'Group', GROUP),
    'NonSignals': _collection('PcbNonSignalLayers', 'NonSignal', NON_SIGNAL),
    'Shapes': _collection('PcbBoardDrawings', 'Shape', SHAPE),
    'CopperPours': _collection('PcbCopperPours', 'CopperPour', POUR),
    'Tables': Record('PcbTables', {}, children={'Table': Child('Table', 'PcbTable', maximum=None)}),
    'Dimensions': _collection('PcbDimensions', 'Dimension', DIMENSION),
    'Holes': _collection('PcbHoles', 'Hole', HOLE),
}
PATTERN_DIMENSIONS = _collection('PcbPatternDimensions', 'Dimension', PATTERN_DIMENSION)
FILL_LINES = _collection('PcbFillLines', 'Line', FILL_LINE)
FILL_SPOKES = _collection('PcbSpokeLines', 'Line', FILL_SPOKE)
FILL_POLYGONS = _collection('PcbFillPolygons', 'Poly', FILL_POLYGON)
VECTOR_POINTS = _collection('PcbVectorPoints', 'Item', VECTOR_POINT)
VECTOR_POLYGONS = _collection('PcbVectorPolygons', 'Polygon', VECTOR_POLYGON)


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    owner = parent.parent
    if parent.kind == 'Board':
        return COLLECTIONS.get(node.kind)
    if owner is not None and owner.kind == 'Board':
        return {('Groups', 'Group'): GROUP, ('NonSignals', 'NonSignal'): NON_SIGNAL,
                ('Points', 'pt'): OUTLINE_POINT,
                ('Shapes', 'Shape'): SHAPE, ('CopperPours', 'CopperPour'): POUR,
                ('Dimensions', 'Dimension'): DIMENSION}.get((parent.kind, node.kind))
    if parent.kind == 'Pattern' and parent.parent is not None and parent.parent.kind == 'Component':
        return COLLECTIONS['Holes'] if node.kind == 'Holes' else PATTERN_DIMENSIONS if node.kind == 'Dimensions' else None
    if (parent.kind in ('Holes', 'Dimensions') and owner is not None and owner.kind == 'Pattern'
            and owner.parent is not None and owner.parent.kind == 'Component'):
        return HOLE if node.kind == 'Hole' else PATTERN_DIMENSION if node.kind == 'Dimension' else None
    if parent.kind == 'CopperPour' and node.kind == 'Fill':
        return FILL
    if parent.kind == 'Fill':
        return {'Lines': FILL_LINES, 'SpokeLine': FILL_SPOKES, 'Polygons': FILL_POLYGONS,
                'Regions': pour_regions.REGIONS}.get(node.kind)
    if owner is not None and owner.kind == 'Fill':
        if parent.kind == 'Regions' and node.kind == 'Region':
            return pour_regions.REGION
        if node.kind == 'Line':
            return FILL_SPOKE if parent.kind == 'SpokeLine' else FILL_LINE
        return FILL_POLYGON if node.kind == 'Poly' else None
    if node.kind in ('Points', 'Points_New') and parent.kind in ('Shape', 'CopperPour', 'Poly'):
        return POINTS
    if node.kind == 'pt' and parent.schema is POINTS:
        return POINT
    if node.kind == 'TextLine' and parent.kind == 'Shape':
        return TEXT_LINES
    if node.kind == 'pt' and parent.schema is TEXT_LINES:
        return TEXT_LINE
    if node.kind == 'PictureVector' and parent.kind == 'Shape':
        return VECTOR
    if node.kind == 'Polygons' and parent.kind == 'PictureVector':
        return VECTOR_POLYGONS
    if node.kind == 'Polygon' and parent.schema is VECTOR_POLYGONS:
        return VECTOR_POLYGON
    if node.kind == 'Points' and parent.schema is VECTOR_POLYGON:
        return VECTOR_POINTS
    if node.kind == 'Item' and parent.schema is VECTOR_POINTS:
        return VECTOR_POINT
    return None
