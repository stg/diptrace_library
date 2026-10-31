"""PCB ASC's cached physical dialect, with generated boundary entries."""
from ....common.conversion import info, warn
from ....common.model import Element
from ....common import drawing_records, footprint_records as physical, library_metadata
from ....common.footprint_objects import new_pad, new_pattern_drawing
from ...model import library_records as model, internal_connections
from ..errors import PcbError
from .cache_values import prefix, groups, classifications, user_field_rows
from .footprint_projection import project_terminals, project_model, points
from .projection import check, collection, fields, flag, value
from ..local_group_projection import selection as group_selection


_PAD_NAMES = {'PadWidth_New':'PadWidth','PadHeight_New':'PadHeight','PadShape_New':'PadShape',
    'DisableTopMask':'TopMask_State','DisableBottomMask':'BotMask_State',
    'DisableTopPaste':'TopPaste_State','DisableBottomPaste':'BotPaste_State'}


def _boundary(source, schema):
    """Construct an output-only neutral entry using our own ordinary defaults."""
    result = Element(source.kind, *source.arguments)
    for child in source.children():
        field = schema.fields.get(child.kind)
        if (child.kind in source.schema.fields and child.kind not in ('Number_New','Group')
                and field is not None and field.getter is None):
            result.append(child.clone())
    return result.bind_schema(schema)


def _pad(pad, *, index, boundary=False, report=None):
    check(pad, model.PAD)
    if pad.child('UnresolvedKeys') is not None:
        raise PcbError(f'{pad.path}: unresolved cached pad extensions need an ASC mapping')
    output = Element('Pad', index, pad['StringNumber'], pad['Name'], pad['X'], pad['Y'])
    fields(pad, output, exclude=(*pad.schema.parameters, 'Id', 'UnresolvedGroupId'), names=_PAD_NAMES)
    output.add('Number', -1 if boundary else index)
    output.add('Group', group_selection(pad, destination='asc', report=report))
    output.add('CustomSwell', value(pad,'CustomSwell_New'))
    output.add('CustomShrink', value(pad,'CustomShrink_New'))
    output.append(project_terminals(pad))
    for name in ('PadPoints_New','PadMask_TopSegments','PadMask_BotSegments'):
        source = pad.child(name)
        if source is not None:
            paste = name != 'PadPoints_New'
            output.append(points(source, kind=name if paste else 'Point',
                schema=physical.PASTE_SEGMENTS if paste else drawing_records.POINTS,
                member=physical.PASTE_SEGMENT if paste else drawing_records.POINT))
    if pad.child('Id') is not None:
        warn(report,'pad-persistent-key','asc','ASC generates positional pad keys',(pad,))
    return output


def _drawing(shape, report):
    check(shape, model.PATTERN_DRAWING)
    if shape.child('UnresolvedKeys') is not None:
        raise PcbError(f'{shape.path}: unresolved cached footprint drawing needs an ASC mapping')
    lines = collection(shape,'TextLine',drawing_records.TEXT_LINES,drawing_records.TEXT_LINE)
    output = Element('Shape', shape['Type'],flag(shape['Locked']),shape['Layer'],
        0,0,0,0,0,0,lines[0]['Text'] if lines else '',shape['FontName'],flag(shape['VectorFont']),
        shape['FontSize'],shape['FontScale'],shape['FontWidth'],shape['TextAngle'],shape['Width'],shape['TextShow'])
    fields(shape,output,exclude=(*shape.schema.parameters,'Type','Locked','Layer','FontName','VectorFont',
        'FontSize','FontScale','FontWidth','TextAngle','Width','TextShow','PadId','ShieldGroup','FontMono','UnresolvedGroupId'))
    output.add('Group',group_selection(shape, destination='asc', report=report))
    geometry = shape.child('Points_New')
    output.append(points(geometry,kind='Point') if geometry is not None else Element('Point'))
    text = output.add('TextLines')
    for line in lines:
        text.add('TextLine',line['Text'])
    if value(shape,'ShieldGroup') != -1 or value(shape,'FontMono') or value(shape,'PadId') != -1:
        warn(report,'cached-footprint-drawing-options','asc',
             'ASC omits cached drawing shield, monospace or pad-association settings',(shape,))
    return output


def project_pattern(pattern, *, datasheet='', report=None):
    check(pattern,model.PATTERN)
    output = Element('Pattern',pattern['Name'])
    fields(pattern,output,exclude=('Name','Value','Datasheet','RefDes','Sided'), names={
        'Pattern_Manufacturer':'Manufacturer','Pattern_CategoryName':'CategoryName',
        'Pattern_CategoryIndex':'CategoryIndex'})
    output.add('Datasheet',datasheet)
    output.append(classifications(pattern,'Pattern'))
    output.append(user_field_rows(pattern))
    output.append(groups(pattern,'Pattern_Groups'))
    output.append(project_terminals(pattern))
    for name in ('PadPoints','PadMask_TopSegments','PadMask_BotSegments'):
        source = pattern.child(name)
        if source is not None:
            paste = name != 'PadPoints'
            output.append(points(source,schema=physical.PASTE_SEGMENTS if paste else drawing_records.POINTS,
                                 member=physical.PASTE_SEGMENT if paste else drawing_records.POINT))
    pads = collection(pattern,'Pads',model.PADS,model.PAD)
    target = output.add('Pads')
    boundary = _boundary(new_pad(),model.PAD)
    target.append(_pad(boundary,index=0,boundary=True))
    for index,pad in enumerate(pads,1):
        target.append(_pad(pad,index=index,report=report))
    target.append(_pad(boundary,index=len(pads)+1,boundary=True))
    shapes = output.add('Shapes')
    boundary = _boundary(new_pattern_drawing(),model.PATTERN_DRAWING)
    for shape in (boundary,*collection(pattern,'Shapes',model.PATTERN_COLLECTIONS['Shapes'],model.PATTERN_DRAWING),boundary):
        row = _drawing(shape,report)
        children = tuple(row.children())
        for child in children:
            child.detach()
        shapes.append(row)
        for child in children:
            shapes.append(child)
    holes = output.add('Holes')
    holes.add('Hole','N','N',0,0,0,0,-1)
    for hole in collection(pattern,'Holes',model.PATTERN_COLLECTIONS['Holes'],model.HOLE):
        if hole.child('UnresolvedKeys') is not None:
            raise PcbError(f'{hole.path}: unresolved cached hole extensions need an ASC mapping')
        holes.add('Hole',flag(hole['Enabled']),flag(hole['Locked']),hole['X'],hole['Y'],hole['Diam'],hole['HoleDiam'],
                  group_selection(hole, destination='asc', report=report))
    holes.add('Hole','N','N',0,0,0,0,-1)
    dimensions = output.add('Dimensions')
    for dimension in collection(pattern,'Dimensions',model.PATTERN_COLLECTIONS['Dimensions'],model.DIMENSION):
        if dimension.child('UnresolvedKeys') is not None:
            raise PcbError(f'{dimension.path}: unresolved cached dimension extensions need an ASC mapping')
        row = dimensions.add('Dimension')
        fields(dimension,row,exclude=('FontMono','UnresolvedGroupId'))
        row.add('Group',group_selection(dimension, destination='asc', report=report))
        if value(dimension,'FontMono'):
            warn(report,'dimension-font-monospace','asc','ASC omits dimension monospaced-font settings',(dimension,))
        document = dimension._owner()
        if document is not None and any(document.references.unresolved_slot(dimension.one(name+side))
                for side in ('1','2') for name in ('Object','SubObject','Point')):
            warn(report,'unresolved-dimension-attachment','asc','Cached dimension attachment is unavailable',(dimension,),
                 recoverability='coordinates and explicit unresolved selectors remain')
    connections = output.add('InternalConnections')
    for pair in collection(pattern,'InternalConnections',model.CONNECTIONS,internal_connections.PAIR):
        if pair['Pad1'] is None or pair['Pad2'] is None:
            raise PcbError(f'{pair.path}: assign both internal-connection pads before export')
        connections.add('IntCon',pair['Pad1']._ordinal()+1,pair['Pad2']._ordinal()+1)
    names = collection(pattern,'PossibleNames',library_metadata.POSSIBLE_NAMES,library_metadata.POSSIBLE_NAME)
    target = output.add('PossibleNames',len(names))
    for name in names:
        target.add('PossibleName',name['Name'])
    output.append(project_model(pattern.one('Model3D')))
    omitted = [name for name in ('Value','Datasheet','RefDes','Sided') if pattern.get(name)]
    if omitted:
        warn(report,'cached-pattern-metadata','asc','ASC omits independent footprint '+', '.join(omitted),(pattern,))
    defaults = [name for name in ('Value','Datasheet','RefDes','Sided')
                if pattern.child(name) is not None and not pattern.get(name)]
    if defaults:
        info(report,'cached-pattern-default-metadata','asc','ASC omits empty/default footprint '+', '.join(defaults),(pattern,))
    return prefix(output)
