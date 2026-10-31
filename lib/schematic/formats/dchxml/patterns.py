"""XML footprint geometry and model placement over shared editable records."""
from ....common.xml_footprint_vocabulary import PATTERN_TYPES
from .syntax import (set_attribute)
from .components import HORZ, VERT
from ....common.xml_library_output import project_category
from ....common.xml_output import enum_text, field, numeric
from ....common.xml_output import point_attributes
from ....common.model import (Element)
from .fonts import uses_physical_width
from ....common.xml_footprint_output import project_model3d, project_drawing as _project_drawing, project_dimension as _project_dimension
from ...model.local_keys import (project_key, public_keys, reserved_keys, missing_key)




def project_pattern_drawing(shape, *, index, units, pad_ids=True, pad_keys=None, group_keys=None, version=46):
    group = project_key(shape,'Group',shape.scalar('Group'),group_keys)
    pad = project_key(shape,'PadId',shape.scalar('PadId',-1),pad_keys) if pad_ids else -1
    return _project_drawing(shape,index=index,units=units,group=group,pad_id=pad,
                            fractional_font=version >= 52,physical_font_width=uses_physical_width(version))


def project_dimension(dimension, *, units, pad_keys=None, shape_keys=None, hole_keys=None, group_keys=None, version=46):
    attachments = []
    for side in ('1','2'):
        mode = dimension.scalar('Connected'+side)
        member = dimension.scalar('SubObject'+side)
        mapping = {0:pad_keys,1:shape_keys,2:hole_keys}.get(mode)
        member = project_key(dimension,'SubObject'+side,member,mapping)
        attachments.append((mode,dimension.scalar('Object'+side),member,dimension.scalar('Point'+side)))
    group = project_key(dimension,'Group',dimension.scalar('Group'),group_keys)
    return _project_dimension(dimension,units=units,attachments=attachments,group=group,
        fractional_font=version >= 52,physical_font_width=uses_physical_width(version),none_label='None' if version >= 52 else None)


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
    category = project_category(pattern)
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
