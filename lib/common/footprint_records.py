"""Shared footprint and related record definitions for design documents."""
from .schema import Child, Field, Record
from .drawing_records import POINT, POINTS


TERMINAL_COUNT = Field('PadTerminalCount', 'integer',
    getter=lambda owner: len(owner._child_sequence('PadTerminal')),
    collection_dependencies=lambda owner: ((owner, 'PadTerminal'),),
    description='Calculated number of current terminal records.')

PASTE_SEGMENT = Record('PasteSegment', {
    name: Field(name, 'number', required=True, default=0, unit='shared length')
    for name in ('X1', 'Y1', 'X2', 'Y2')
}, parameters=('X1', 'Y1', 'X2', 'Y2'))
PASTE_SEGMENTS = Record('PasteSegments', {}, description='An ordered collection of PasteSegment records.',
    children={'pt': Child('pt', PASTE_SEGMENT.name, maximum=None)})


PATTERN = Record('Pattern', {
    'Type': Field('Type', 'integer', required=True),
    'VariableParameter1': Field('VariableParameter1', 'boolean', required=True),
    'VariableParameter2': Field('VariableParameter2', 'boolean', required=True),
    'VariableParameter3': Field('VariableParameter3', 'boolean', required=True),
    'VariableParameter4': Field('VariableParameter4', 'boolean', required=True),
    'VariableParameter5': Field('VariableParameter5', 'boolean', required=True),
    'Number1': Field('Number1', 'integer', required=True),
    'Number2': Field('Number2', 'integer', required=True),
    'Spacing1': Field('Spacing1', 'number', required=True),
    'Spacing2': Field('Spacing2', 'number', required=True),
    'Spacing3': Field('Spacing3', 'number', required=True),
    'LockProperties': Field('LockProperties', 'boolean', required=True),
    'PatternOrientation': Field('PatternOrientation', 'number', required=True),
    'Width': Field('Width', 'number', required=True),
    'Height': Field('Height', 'number', required=True),
    'OriginCross': Field('OriginCross', 'boolean', required=True),
    'OriginCircle': Field('OriginCircle', 'boolean', required=True),
    'OriginCommon': Field('OriginCommon', 'integer', required=True),
    'OriginCourtyard': Field('OriginCourtyard', 'integer', required=True),
    'Name_Description': Field('Name_Description', 'text', required=True),
    'Name_Unique': Field('Name_Unique', 'text', required=True),
    'RecoveryCode': Field('RecoveryCode', 'text', required=True),
    'RecoveryCode_Generator': Field('RecoveryCode_Generator', 'boolean', required=True),
    'RecoveryCode_Model': Field('RecoveryCode_Model', 'boolean', required=True),
    'Pattern_Manufacturer': Field('Pattern_Manufacturer', 'text', required=True),
    'PadCorner': Field('PadCorner', 'number', required=True),
    'PadShape_X': Field('PadShape_X', 'number', required=True),
    'PadShape_Y': Field('PadShape_Y', 'number', required=True),
    'PadWidth': Field('PadWidth', 'number', required=True),
    'PadHeight': Field('PadHeight', 'number', required=True),
    'PadShape': Field('PadShape', 'integer|text', required=True,
        description='Shape code or public XML shape label, including empty text.'),
    'SurfacePad': Field('SurfacePad', 'boolean', required=True),
    'PadHole': Field('PadHole', 'number', required=True),
    'PadHoleH': Field('PadHoleH', 'number', required=True),
    'PadHoleType': Field('PadHoleType', 'integer', required=True),
    'PadTerminalCount': TERMINAL_COUNT,
    'TopMask_State': Field('TopMask_State', 'integer', required=True),
    'BotMask_State': Field('BotMask_State', 'integer', required=True),
    'TopPaste_State': Field('TopPaste_State', 'integer', required=True),
    'BotPaste_State': Field('BotPaste_State', 'integer', required=True),
    'CustomSwell_New': Field('CustomSwell_New', 'number', required=True),
    'CustomShrink_New': Field('CustomShrink_New', 'number', required=True),
    'PadMask_Percent': Field('PadMask_Percent', 'number', required=True),
    'PadMask_EdgeGap': Field('PadMask_EdgeGap', 'number', required=True),
    'PadMask_SegmentGap': Field('PadMask_SegmentGap', 'number', required=True),
    'PadMask_SegmentSide': Field('PadMask_SegmentSide', 'integer', required=True),
    'OriginX': Field('OriginX', 'number', required=True),
    'OriginY': Field('OriginY', 'number', required=True),
    'Mounting': Field('Mounting', 'integer', required=True),
    'Pattern_CategoryName': Field('Pattern_CategoryName', 'text', required=True),
    'Pattern_CategoryIndex': Field('Pattern_CategoryIndex', 'integer', required=True),
    'Datasheet': Field('Datasheet', 'text'),
    'Sided': Field('Sided', 'boolean'),
    'RefDes': Field('RefDes', 'text'),
    'Name': Field('Name', 'text', required=True, default=''),
}, parameters=('Name',),
   children={
       'Pattern_CategoryTypes': Child('Pattern_CategoryTypes', 'Classifications'),
       'PossibleNames': Child('PossibleNames', 'PossibleNames'),
       'PadMask_TopSegments': Child('PadMask_TopSegments', 'PasteSegments'),
       'PadMask_BotSegments': Child('PadMask_BotSegments', 'PasteSegments'),
       'Pads': Child('Pads', 'Pads'),
       'Shapes': Child('Shapes', 'PatternDrawings'),
       'Holes': Child('Holes', 'Holes'),
       'Dimensions': Child('Dimensions', 'Dimensions'),
       'UserFields': Child('UserFields', 'UserFields'),
       'Model3D': Child('Model3D', 'Model3D'),
       'Pattern_Groups': Child('Pattern_Groups', 'LocalGroups'),
       'InternalConnections': Child('InternalConnections', 'InternalConnections'),
       'PadPoints': Child('PadPoints', 'Points'),
       'PadTerminal': Child('PadTerminal', 'PadTerminal', maximum=None),
   })


PAD = Record('Pad', {
    'Number_New': Field('Number_New', 'integer', required=True),
    'Locked': Field('Locked', 'boolean', required=True),
    'Sided': Field('Sided', 'boolean', required=True),
    'DisableTopMask': Field('DisableTopMask', 'integer', required=True),
    'DisableBottomMask': Field('DisableBottomMask', 'integer', required=True),
    'DisableTopPaste': Field('DisableTopPaste', 'integer', required=True),
    'DisableBottomPaste': Field('DisableBottomPaste', 'integer', required=True),
    'CustomSwell_New': Field('CustomSwell_New', 'number', required=True),
    'CustomShrink_New': Field('CustomShrink_New', 'number', required=True),
    'PadHole': Field('PadHole', 'number', required=True),
    'PadHoleH': Field('PadHoleH', 'number', required=True),
    'PadHoleType': Field('PadHoleType', 'integer', required=True),
    'SurfacePad': Field('SurfacePad', 'boolean', required=True),
    'PadShape_New': Field('PadShape_New', 'integer|text', required=True,
        description='Current shape code or public XML label, including empty text.'),
    'PadAngle': Field('PadAngle', 'number', required=True),
    'PadShape_X': Field('PadShape_X', 'number', required=True),
    'PadShape_Y': Field('PadShape_Y', 'number', required=True),
    'PadCorner': Field('PadCorner', 'number', required=True),
    'PadWidth_New': Field('PadWidth_New', 'number', required=True),
    'PadHeight_New': Field('PadHeight_New', 'number', required=True),
    'Group': Field('Group', 'integer', required=True),
    'Standard': Field('Standard', 'boolean', required=True),
    'PadTerminalCount': TERMINAL_COUNT,
    'PadMask_Percent': Field('PadMask_Percent', 'number', required=True),
    'PadMask_EdgeGap': Field('PadMask_EdgeGap', 'number', required=True),
    'PadMask_SegmentGap': Field('PadMask_SegmentGap', 'number', required=True),
    'PadMask_SegmentSide': Field('PadMask_SegmentSide', 'integer', required=True),
    'Index': Field('Index', 'integer', required=True, default=0, getter=lambda node: node._ordinal(),
        ordinal_dependencies=lambda node: (node,)),
    'StringNumber': Field('StringNumber', 'text', required=True, default=''),
    'Name': Field('Name', 'text', required=True, default=''),
    'X': Field('X', 'number', required=True, default=0, unit='shared length'),
    'Y': Field('Y', 'number', required=True, default=0, unit='shared length'),
    'Id': Field('Id', 'integer',
        description='Optional persistent public pad key; positional writers generate their own indices.'),
}, parameters=('Index', 'StringNumber', 'Name', 'X', 'Y'),
   children={
       'PadMask_TopSegments': Child('PadMask_TopSegments', 'PasteSegments'),
       'PadMask_BotSegments': Child('PadMask_BotSegments', 'PasteSegments'),
       'PadPoints_New': Child('PadPoints_New', 'Points'),
       'PadTerminal': Child('PadTerminal', 'PadTerminal', maximum=None),
       'UnresolvedKeys': Child('UnresolvedKeys', 'UnresolvedKeys'),
   })


PAD_STYLE = Record('PadStyle', {
    'SurfacePad': Field('SurfacePad', 'boolean', required=True),
    'Sided': Field('Sided', 'boolean', required=True),
    'PadHoleType': Field('PadHoleType', 'integer', required=True),
    'PadHole': Field('PadHole', 'number', required=True),
    'PadHoleH': Field('PadHoleH', 'number', required=True),
    'PadShape': Field('PadShape', 'integer|text', required=True,
        description='Shape code or public XML label, including empty text.'),
    'PadWidth': Field('PadWidth', 'number', required=True),
    'PadHeight': Field('PadHeight', 'number', required=True),
    'PadCorner': Field('PadCorner', 'number', required=True),
    'PadShape_X': Field('PadShape_X', 'number', required=True),
    'PadShape_Y': Field('PadShape_Y', 'number', required=True),
    'PadTerminalCount': TERMINAL_COUNT,
    'TopMask_State': Field('TopMask_State', 'integer', required=True),
    'BotMask_State': Field('BotMask_State', 'integer', required=True),
    'TopPaste_State': Field('TopPaste_State', 'integer', required=True),
    'BotPaste_State': Field('BotPaste_State', 'integer', required=True),
    'CustomSwell_New': Field('CustomSwell_New', 'number', required=True),
    'CustomShrink_New': Field('CustomShrink_New', 'number', required=True),
    'PadMask_Percent': Field('PadMask_Percent', 'number', required=True),
    'PadMask_EdgeGap': Field('PadMask_EdgeGap', 'number', required=True),
    'PadMask_SegmentGap': Field('PadMask_SegmentGap', 'number', required=True),
    'PadMask_SegmentSide': Field('PadMask_SegmentSide', 'integer', required=True),
    'Name': Field('Name', 'text', required=True, default=''),
}, parameters=('Name',),
   children={
       'PadMask_TopSegments': Child('PadMask_TopSegments', 'PasteSegments'),
       'PadMask_BotSegments': Child('PadMask_BotSegments', 'PasteSegments'),
       'PadPoints': Child('PadPoints', 'Points'),
       'PadTerminal': Child('PadTerminal', 'PadTerminal', maximum=None),
   })


PATTERN_SHAPE = Record('PatternDrawing', {
    'Type': Field('Type', 'integer', required=True),
    'Locked': Field('Locked', 'boolean', required=True),
    'Layer': Field('Layer', 'integer', required=True),
    'FontName': Field('FontName', 'text', required=True),
    'VectorFont': Field('VectorFont', 'boolean', required=True),
    'FontSize': Field('FontSize', 'number', required=True),
    'FontScale': Field('FontScale', 'number', required=True),
    'FontWidth': Field('FontWidth', 'number', required=True),
    'FontMono': Field('FontMono', 'boolean', default=False),
    'TextShow': Field('TextShow', 'integer', required=True),
    'Width': Field('Width', 'number', required=True, unit='shared length'),
    'TextAngle': Field('TextAngle', 'number', required=True, unit='radians'),
    'TextHorz': Field('TextHorz', 'integer', required=True),
    'TextVert': Field('TextVert', 'integer', required=True),
    'TextAlign': Field('TextAlign', 'integer', required=True),
    'LineSpacing': Field('LineSpacing', 'number', required=True),
    'AllLayers': Field('AllLayers', 'boolean', required=True),
    'Group': Field('Group', 'integer', required=True),
    'PadId': Field('PadId', 'integer', required=True),
    'Index': Field('Index', 'integer', required=True, default=0, getter=lambda node: node._ordinal(),
        ordinal_dependencies=lambda node: (node,)),
}, parameters=('Index',),
   children={
       'Points_New': Child('Points_New', 'Points'),
       'TextLine': Child('TextLine', 'TextLines'),
       'UnresolvedKeys': Child('UnresolvedKeys', 'UnresolvedKeys'),
   })


DIMENSION = Record('Dimension', {
    'Enabled': Field('Enabled', 'boolean', required=True),
    'Locked': Field('Locked', 'boolean', required=True),
    'Type': Field('Type', 'integer', required=True),
    'Connected1': Field('Connected1', 'integer', required=True),
    'Object1': Field('Object1', 'integer', required=True),
    'SubObject1': Field('SubObject1', 'integer', required=True),
    'Point1': Field('Point1', 'integer', required=True),
    'Connected2': Field('Connected2', 'integer', required=True),
    'Object2': Field('Object2', 'integer', required=True),
    'SubObject2': Field('SubObject2', 'integer', required=True),
    'Point2': Field('Point2', 'integer', required=True),
    'Layer': Field('Layer', 'integer', required=True),
    'X1': Field('X1', 'number', required=True),
    'Y1': Field('Y1', 'number', required=True),
    'X2': Field('X2', 'number', required=True),
    'Y2': Field('Y2', 'number', required=True),
    'XD': Field('XD', 'number', required=True),
    'YD': Field('YD', 'number', required=True),
    'ArrowSize': Field('ArrowSize', 'number', required=True),
    'Units': Field('Units', 'integer', required=True),
    'VectorFont': Field('VectorFont', 'boolean', required=True),
    'FontName': Field('FontName', 'text', required=True),
    'FontSize': Field('FontSize', 'number', required=True),
    'FontScale': Field('FontScale', 'number', required=True),
    'FontWidth': Field('FontWidth', 'number', required=True),
    'ShowUnits': Field('ShowUnits', 'boolean', required=True),
    'Angle': Field('Angle', 'number', required=True),
    'ExternalRadius': Field('ExternalRadius', 'number', required=True),
    'PointerMode': Field('PointerMode', 'integer', required=True),
    'PointerText': Field('PointerText', 'text', required=True),
    'Group': Field('Group', 'integer', required=True),
    'FontMono': Field('FontMono', 'boolean', default=False),
    'Index': Field('Index', 'integer', required=True, default=0, getter=lambda node: node._ordinal(),
        ordinal_dependencies=lambda node: (node,)),
}, parameters=('Index',),
   children={
       'UnresolvedKeys': Child('UnresolvedKeys', 'UnresolvedKeys'),
   })


TERMINAL = Record('PadTerminal', {
    'Index': Field('Index', 'integer', description='Current terminal position.',
        getter=lambda node: node._ordinal(), ordinal_dependencies=lambda node: (node,)),
    'Type': Field('Type', 'integer|text', required=True, default=0,
        description='Terminal shape code or a public text selection, including empty text.'),
    'Angle': Field('Angle', 'number', required=True, default=0,
        description='Unquantized terminal angle in its public field representation.'),
    'X': Field('X', 'number', required=True, default=0, unit='shared length'),
    'Y': Field('Y', 'number', required=True, default=0, unit='shared length'),
    'ShapeWidth': Field('ShapeWidth', 'number', required=True, default=0, unit='shared length'),
    'ShapeHeight': Field('ShapeHeight', 'number', required=True, default=0, unit='shared length'),
    'ShapeCorner': Field('ShapeCorner', 'number', required=True, default=0, unit='percent'),
}, parameters=('Index',),
   children={
       'ShapePoints': Child('ShapePoints', 'Points'),
   })


HOLE = Record('Hole', {
    'Enabled': Field('Enabled', 'boolean', required=True, default=False),
    'Locked': Field('Locked', 'boolean', required=True, default=False),
    'X': Field('X', 'number', required=True, default=0, unit='shared length'),
    'Y': Field('Y', 'number', required=True, default=0, unit='shared length'),
    'Diam': Field('Diam', 'number', required=True, default=0, unit='shared length',
        description='Outer diameter.'),
    'HoleDiam': Field('HoleDiam', 'number', required=True, default=0, unit='shared length',
        description='Drill diameter.'),
    'Group': Field('Group', 'integer', required=True, default=-1,
        description='Managed pattern-group index; -1 means no group.'),
}, parameters=('Enabled', 'Locked', 'X', 'Y', 'Diam', 'HoleDiam', 'Group'),
   children={
       'UnresolvedKeys': Child('UnresolvedKeys', 'UnresolvedKeys'),
   })


SUPPLIERS = Record('Suppliers', {
    'PartNumber': Field('PartNumber', 'text', default=''),
    'Manufacturer': Field('Manufacturer', 'text', default=''),
    'Pattern': Field('Pattern', 'text', default=''),
    'Supplier': Field('Supplier', 'text', default=''),
    'SourceLocator': Field('SourceLocator', 'text', default=''),
    'Currency': Field('Currency', 'text', default=''),
    'MainSupplier': Field('MainSupplier', 'boolean'),
}, parameters=(),
   children={
       'Prices': Child('Prices', 'Prices'),
   })


MODEL3D = Record('Model3D', {
    'Model3DFile': Field('Model3DFile', 'text', default=''),
    'Model3DFile_Variable': Field('Model3DFile_Variable', 'text', default=''),
    'Mirror': Field('Mirror', 'boolean', default=False),
    'NoSearch': Field('NoSearch', 'boolean', default=False),
    'Units': Field('Units', 'integer', default=0),
    'IPC_XOff': Field('IPC_XOff', 'number', default=0),
    'IPC_YOff': Field('IPC_YOff', 'number', default=0),
    'AutoHeight': Field('AutoHeight', 'number', default=0),
    'AutoColor': Field('AutoColor', 'integer', default=4934475),
    'Type': Field('Type', 'integer', default=0),
    'KeepPins': Field('KeepPins', 'boolean', default=False),
}, parameters=(),
   children={
       'Offset': Child('Offset', 'ModelOffset'),
       'Rotate': Child('Rotate', 'ModelRotate'),
       'Zoom': Child('Zoom', 'ModelZoom'),
   })


MODEL_OFFSET = Record('ModelOffset', {
    'X': Field('X', 'number', required=True, default=0, description='Model offset on this axis.'),
    'Y': Field('Y', 'number', required=True, default=0, description='Model offset on this axis.'),
    'Z': Field('Z', 'number', required=True, default=0, description='Model offset on this axis.'),
}, parameters=(),
   children={
   })


MODEL_ROTATE = Record('ModelRotate', {
    'X': Field('X', 'number', required=True, default=0, description='Model rotate on this axis.'),
    'Y': Field('Y', 'number', required=True, default=0, description='Model rotate on this axis.'),
    'Z': Field('Z', 'number', required=True, default=0, description='Model rotate on this axis.'),
}, parameters=(),
   children={
   })


MODEL_ZOOM = Record('ModelZoom', {
    'X': Field('X', 'number', required=True, default=1, description='Model zoom on this axis.'),
    'Y': Field('Y', 'number', required=True, default=1, description='Model zoom on this axis.'),
    'Z': Field('Z', 'number', required=True, default=1, description='Model zoom on this axis.'),
}, parameters=(),
   children={
   })


VECTORS = {'Offset': MODEL_OFFSET, 'Rotate': MODEL_ROTATE, 'Zoom': MODEL_ZOOM}


def pad_geometry_definition(node):
    """Shared terminal, contour and paste geometry under pads or pad defaults.

    Ownership distinguishes these point collections from routing points and
    other document geometry. Cached and placed footprints use the same fields.
    """
    parent = node.parent
    if parent is None:
        return None
    if parent.kind in ('Pad', 'Pattern', 'PadStyle'):
        if node.kind == 'PadTerminal':
            return TERMINAL
        if node.kind in ('PadMask_TopSegments', 'PadMask_BotSegments'):
            return PASTE_SEGMENTS
        if node.kind == ('PadPoints_New' if parent.kind == 'Pad' else 'PadPoints'):
            return POINTS
    if parent.kind == 'PadTerminal' and node.kind == 'ShapePoints':
        return POINTS
    owner = parent.parent
    if node.kind == 'pt' and owner is not None:
        if owner.kind in ('Pad', 'Pattern', 'PadStyle'):
            if parent.kind in ('PadMask_TopSegments', 'PadMask_BotSegments'):
                return PASTE_SEGMENT
            if parent.kind == ('PadPoints_New' if owner.kind == 'Pad' else 'PadPoints'):
                return POINT
        if owner.kind == 'PadTerminal' and parent.kind == 'ShapePoints':
            return POINT
    return None


def nested_definition(node):
    """Physical subrecords and supplier facts shared across placed/cache owners."""
    if (pad := pad_geometry_definition(node)) is not None:
        return pad
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'Suppliers' and parent.kind in ('Component', 'Part', 'Pattern'):
        return SUPPLIERS
    if node.kind == 'Model3D' and parent.kind == 'Pattern':
        return MODEL3D
    if parent.kind == 'Model3D':
        return VECTORS.get(node.kind)
    return None
