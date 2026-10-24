"""XML footprint geometry and model placement over shared editable records."""
from .syntax import (set_attribute)
from .components import (HORZ, VERT, _category)
from .settings import (enum_text, field, numeric)
from .symbols import (point_attributes)
from ....common.model import (Element)
from ...model.local_keys import (project_key, public_keys, reserved_keys, missing_key)


PATTERN_TYPES = ('Free', 'Right Angle', 'Left Angle', 'T', 'Circle', 'Lines', 'Square', 'Matrix',
                 'Rectangle', 'Zig-Zag', 'IPC-7351')
DRAWING_TYPES = ('None', 'Line', 'Rectangle', 'Obround', 'FillRect', 'FillObround', 'Arc', 'Text', 'Polyline', 'Polygon')
LAYERS = ('Top Silk', 'Top Assy', 'Top Mask', 'Top Paste', 'Bottom Paste', 'Bottom Mask', 'Bottom Assy',
    'Bottom Silk', 'Top', 'Top Keepout', 'Bottom Keepout', 'Bottom', 'Board Cutout', 'Top Dimension',
    'Bottom Dimension', 'Non-Signal', 'Top Courtyard', 'Bottom Courtyard', 'Top Outline', 'Bottom Outline',
    'Top Terminals', 'Bottom Terminals')
TEXT_SHOW = ('Any Text', 'Name', 'RefDes', 'Value', 'Manufacturer', 'Unique Name', 'Datasheet')


def project_model3d(model, *, units):
    result = Element('Model3D')
    for name in ('Mirror', 'NoSearch'):
        set_attribute(result, name, model.scalar(name))
    set_attribute(result, 'Units', enum_text(model.scalar('Units'), ('mm', 'mil', 'inch', 'Wings'), negative='Wings'))
    point_attributes(result, model.one('IPC_XOff').arguments[0], model.one('IPC_YOff').arguments[0],
                     units, names=('IPC_XOff', 'IPC_YOff'))
    set_attribute(result, 'AutoHeight', numeric(units.length(model.one('AutoHeight').arguments[0])))
    set_attribute(result, 'AutoColor', model.scalar('AutoColor'))
    set_attribute(result, 'Type', enum_text(model.scalar('Type'), ('File', 'IPC-7351', 'Outline')))
    set_attribute(result, 'KeepPins', model.scalar('KeepPins'))
    path = model.scalar('Model3DFile')
    variable = model.scalar('Model3DFile_Variable', '')
    if not variable.replace(' ', ''):
        variable = path
    if path or variable:
        filename = result.add('Filename')
        field(filename, 'Path', path)
        field(filename, 'Var', variable)
    for name in ('Rotate', 'Offset', 'Zoom'):
        target = result.add(name)
        for axis in ('X', 'Y', 'Z'):
            value = model.one(name+'/'+axis).arguments[0]
            if name == 'Offset':
                value = units.length(value) * (-1 if axis == 'Y' else 1)
            set_attribute(target, axis, numeric(value))
    return result


def project_pattern_drawing(shape, *, index, units, pad_ids=True, pad_keys=None, group_keys=None, version=46):
    result = Element('Shape')
    kind = shape.scalar('Type')
    set_attribute(result, 'Id', index)
    set_attribute(result, 'Type', enum_text(kind, DRAWING_TYPES))
    set_attribute(result, 'Locked', shape.scalar('Locked'))
    set_attribute(result, 'Layer', enum_text(shape.scalar('Layer'), LAYERS))
    if kind == 7:
        for public, own in (('FontVector', 'VectorFont'), ('FontName', 'FontName'), ('FontSize', 'FontSize'),
                            ('FontWidth', 'FontWidth'), ('FontScale', 'FontScale'), ('LineSpacing', 'LineSpacing')):
            set_attribute(result, public, shape.one(own).arguments[0])
        set_attribute(result, 'TextShow', enum_text(shape.scalar('TextShow'), TEXT_SHOW))
        from .fonts import (project_size)
        project_size(shape, result, version=version)
        set_attribute(result, 'Angle', shape.one('TextAngle').arguments[0])
        for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT),
                                    ('TextAlign', 'TextAlign', HORZ)):
            set_attribute(result, public, enum_text(shape.scalar(own), labels, negative=labels[-1]))
    else:
        width = shape.one('Width').arguments[0]
        if width.value != -1:
            set_attribute(result, 'LineWidth', numeric(units.length(width)))
    set_attribute(result, 'AllLayers', shape.scalar('AllLayers'))
    group = project_key(shape, 'Group', shape.scalar('Group'), group_keys)
    if group >= 0:
        set_attribute(result, 'Group', group)
    key = project_key(shape, 'PadId', shape.scalar('PadId', -1), pad_keys)
    if pad_ids and key >= 0:
        set_attribute(result, 'PadId', key)
    if kind == 7 and shape.select('TextLine/pt'):
        target = result.add('Lines')
        for line in shape.select('TextLine/pt'):
            field(target, 'Item', line.arguments[0])
    if shape.select('Points_New/pt'):
        target = result.add('Points')
        for point in shape.select('Points_New/pt'):
            point_attributes(target.add('Item'), *point.arguments, units)
    return result


def project_dimension(dimension, *, units, pad_keys=None, shape_keys=None, hole_keys=None, group_keys=None, version=46):
    result = Element('Dimension')
    set_attribute(result, 'Locked', dimension.scalar('Locked'))
    set_attribute(result, 'Type', enum_text(dimension.scalar('Type'), ('Horizontal', 'Vertical', 'Free', 'Radius', 'Pointer')))
    for side in ('1', '2'):
        set_attribute(result, 'Connected'+side, enum_text(dimension.scalar('Connected'+side), ('Pad', 'Shape', 'Hole', 'Terminal'), negative='None' if version >= 52 else None))
        for name in ('Object', 'SubObject', 'Point'):
            value = dimension.scalar(name+side)
            if name == 'SubObject':
                mapping = {0: pad_keys, 1: shape_keys, 2: hole_keys}.get(dimension.scalar('Connected'+side))
                value = project_key(dimension, name+side, value, mapping)
            set_attribute(result, name+side, value)
    set_attribute(result, 'Layer', enum_text(dimension.scalar('Layer'), LAYERS))
    for suffix in ('1', '2', 'D'):
        point_attributes(result, dimension.one('X'+suffix).arguments[0], dimension.one('Y'+suffix).arguments[0],
                         units, names=('X'+suffix, 'Y'+suffix))
    set_attribute(result, 'ArrowSize', numeric(units.length(dimension.one('ArrowSize').arguments[0])))
    set_attribute(result, 'Units', enum_text(dimension.scalar('Units'), ('Common', 'inch', 'mil', 'mm')))
    for public, own in (('FontVector', 'VectorFont'), ('FontName', 'FontName'), ('FontSize', 'FontSize'),
                        ('FontWidth', 'FontWidth'), ('FontScale', 'FontScale'), ('ShowUnits', 'ShowUnits'),
                        ('Angle', 'Angle'), ('ExternalRadius', 'ExternalRadius'), ('PointerMode', 'PointerMode')):
        set_attribute(result, public, dimension.one(own).arguments[0])
    from .fonts import (project_size)
    project_size(dimension, result, version=version)
    group = project_key(dimension, 'Group', dimension.scalar('Group'), group_keys)
    if group >= 0:
        set_attribute(result, 'Group', group)
    if dimension.scalar('PointerText'):
        field(result, 'PointerText', dimension.scalar('PointerText'))
    return result


def project_pattern(pattern, *, style, default_pad_style, pad_styles, units, pad_ids=True, pad_keys=None, version=46):
    """Project current footprint data with explicitly selected pad-style keys.

    ``pad_styles`` maps physical pad ordinals to public style names. Reserved
    array-boundary slots are omitted, while their ordinals remain meaningful.
    """
    result = Element('Pattern')
    members = [*pattern.select('Pads/Pad'), *pattern.select('Shapes/Shape'),
               *pattern.select('Holes/Hole'), *pattern.select('Dimensions/Dimension')]
    group_keys = public_keys(pattern.select('Pattern_Groups/pt'), reserved_keys(members, ('Group',)))
    dimensions = pattern.select('Dimensions/Dimension')
    def object_keys(container, kind, mode):
        reserved = {key.values[1] for dimension in dimensions for side in ('1', '2')
                    if dimension.scalar('Connected'+side) == mode
                    and (key := missing_key(dimension, 'SubObject'+side)) is not None}
        return public_keys(pattern.select(container+'/'+kind)[1:-1], reserved, start=1)
    shape_keys = object_keys('Shapes', 'Shape', 1)
    hole_keys = object_keys('Holes', 'Hole', 2)
    set_attribute(result, 'PatternStyle', style)
    if pattern.scalar('RefDes', ''):
        set_attribute(result, 'RefDes', pattern.scalar('RefDes'))
    set_attribute(result, 'Mounting', enum_text(pattern.scalar('Mounting'), ('Through', 'SMD', 'Chassis', 'Mixed'), negative='None' if version >= 52 else None))
    for name in ('Width', 'Height'):
        set_attribute(result, name, numeric(units.length(pattern.one(name).arguments[0])))
    orientation = pattern.scalar('PatternOrientation')
    set_attribute(result, 'Orientation', orientation*90 if 0 <= orientation <= 3 else orientation)
    set_attribute(result, 'LockTypeChange', pattern.scalar('LockProperties'))
    set_attribute(result, 'Type', enum_text(pattern.scalar('Type'), PATTERN_TYPES))
    for index in range(1, 4):
        set_attribute(result, 'Float'+str(index), numeric(units.length(pattern.one('Spacing'+str(index)).arguments[0])))
    for index in (1, 2):
        set_attribute(result, 'Int'+str(index), pattern.scalar('Number'+str(index)))
    field(result, 'Name', pattern.arguments[0])
    for public, own in (('Name_Description', 'Name_Description'), ('Name_Unique', 'Name_Unique'),
                        ('Datasheet', 'Datasheet'), ('Manufacturer', 'Pattern_Manufacturer')):
        if pattern.scalar(own, ''):
            field(result, public, pattern.scalar(own))
    names = pattern.select('PossibleNames/PossibleName')
    if names:
        target = result.add('PossibleNames')
        for name in names:
            field(target, 'PossibleName', name.arguments[0])
    category = _category(pattern)
    if category is not None:
        result.append(category)
    origin = result.add('Origin')
    point_attributes(origin, pattern.one('OriginX').arguments[0], pattern.one('OriginY').arguments[0], units)
    for public, own in (('Cross', 'OriginCross'), ('Circle', 'OriginCircle')):
        set_attribute(origin, public, pattern.scalar(own))
    set_attribute(origin, 'Common', enum_text(pattern.scalar('OriginCommon'), ('Show', 'Hide')))
    set_attribute(origin, 'Courtyard', enum_text(pattern.scalar('OriginCourtyard'), ('Show', 'Hide', 'Show if not center')))
    if pattern.scalar('RecoveryCode'):
        recovery = field(result, 'RecoveryCode', pattern.scalar('RecoveryCode'))
        set_attribute(recovery, 'Generator', pattern.scalar('RecoveryCode_Generator'))
        set_attribute(recovery, 'Model', pattern.scalar('RecoveryCode_Model'))
    groups = pattern.select('Pattern_Groups/pt')
    if groups:
        target = result.add('Groups')
        for index, group in enumerate(groups):
            if group.values[0]:
                item = target.add('Item')
                set_attribute(item, 'Id', group_keys[index])
                point_attributes(item, *group.arguments[-2:], units)
    users = pattern.select('UserFields/UserField')
    if users:
        target = result.add('AddFields')
        for user in users:
            item = target.add('AddField')
            set_attribute(item, 'Type', enum_text(user.values[2], ('Text', 'Link')))
            field(item, 'Name', user.arguments[0])
            field(item, 'Text', user.arguments[1])
    set_attribute(result.add('DefPad'), 'Style', default_pad_style)
    pads = pattern.select('Pads/Pad')
    if len(pads) > 2:
        target = result.add('Pads')
        for index, pad in enumerate(pads[1:-1], 1):
            item = target.add('Pad')
            set_attribute(item, 'Id', pad_keys.get(index, index) if pad_keys is not None else index)
            set_attribute(item, 'Style', pad_styles[index])
            if version >= 52:
                set_attribute(item, 'DefStyle', pad.scalar('Standard'))
            point_attributes(item, *pad.arguments[3:5], units)
            set_attribute(item, 'Angle', pad.one('PadAngle').arguments[0])
            set_attribute(item, 'Locked', pad.scalar('Locked'))
            set_attribute(item, 'Side', 'Bottom' if pad.scalar('Sided') else 'Top')
            group = project_key(pad, 'Group', pad.scalar('Group'), group_keys)
            if group >= 0:
                set_attribute(item, 'Group', group)
            field(item, 'Number', pad.arguments[1])
            if pad.values[2]:
                field(item, 'Note', pad.arguments[2])
    all_shapes = pattern.select('Shapes/Shape')
    shapes = [(i, shape) for i, shape in enumerate(all_shapes[1:-1], 1) if shape.scalar('Type') > 0]
    if shapes:
        target = result.add('Shapes')
        for index, shape in shapes:
            target.append(project_pattern_drawing(shape, index=shape_keys[index], units=units,
                          pad_ids=pad_ids, pad_keys=pad_keys, group_keys=group_keys, version=version))
    holes = pattern.select('Holes/Hole')
    holes = [(index, hole) for index, hole in enumerate(holes) if index not in (0, len(holes)-1) and hole.values[0]]
    if holes:
        target = result.add('Holes')
        for index, hole in holes:
            item = target.add('Hole')
            set_attribute(item, 'Id', hole_keys[index])
            set_attribute(item, 'Locked', hole.arguments[1])
            point_attributes(item, *hole.arguments[2:4], units)
            for name, value in zip(('Diam', 'HoleDiam'), hole.arguments[4:6]):
                set_attribute(item, name, numeric(units.length(value)))
            group = project_key(hole, 'Group', hole.values[6], group_keys)
            if group >= 0:
                set_attribute(item, 'Group', group)
    dimensions = [d for d in pattern.select('Dimensions/Dimension') if d.scalar('Enabled')]
    if dimensions:
        target = result.add('Dimensions')
        for dimension in dimensions:
            target.append(project_dimension(dimension, units=units, pad_keys=pad_keys,
                          shape_keys=shape_keys, hole_keys=hole_keys, group_keys=group_keys, version=version))
    result.append(project_model3d(pattern.one('Model3D'), units=units))
    return result
