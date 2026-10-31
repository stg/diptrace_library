"""Public footprint geometry normalized without format record layouts."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable
from .xml_font_import import read_width

from .xml_library_values import read_points, read_groups, mapped_group, read_category, read_user_fields, read_path
from .xml_pads import read_pad_style
from .xml_records import XmlRecord, enum_value, length, point, replace_rows
from .xml_footprint_vocabulary import HORZ, VERT, PATTERN_TYPES, DRAWING_TYPES, LAYERS, TEXT_SHOW, POINTER_MODES
from .model import Element
from .footprint_objects import _fields as fields


@dataclass(frozen=True)
class PatternImportPolicy:
    """Construction, unresolved keys and component-template metadata by family."""
    pattern_factory: Callable
    pad_factory: Callable
    drawing_factory: Callable
    resolve_key: Callable
    pattern_types: tuple = PATTERN_TYPES
    read_defaults: Callable | None = None


@dataclass
class ImportedPattern:
    element: Element
    pad_ids: dict
    shape_ids: dict
    hole_ids: dict
    used_styles: set
    defaults: dict = field(default_factory=dict)


def _model(record, target, *, units):
    for name in ('Mirror', 'NoSearch', 'KeepPins'):
        target.set_field(name, record.boolean(name, False))
    target.set_field('Units', enum_value(record.value('Units', 'mm'), ('mm', 'mil', 'inch', 'Wings'), negative='Wings'))
    target.set_field('Type', enum_value(record.value('Type', 'File'), ('File', 'IPC-7351', 'Outline')))
    for own, value in zip(('IPC_XOff', 'IPC_YOff'), point(record, units, ('IPC_XOff', 'IPC_YOff'), 0)):
        target.set_field(own, value)
    target.set_field('AutoHeight', length(record.number('AutoHeight', 0), units))
    target.set_field('AutoColor', record.integer('AutoColor', 0x4B4B4B))
    filename = record.take('Filename')
    if filename is not None:
        path, variable = read_path(filename)
        target.set_field('Model3DFile', path)
        target.set_field('Model3DFile_Variable', variable)
    for name in ('Rotate', 'Offset', 'Zoom'):
        vector = record.take(name)
        if vector is not None:
            for axis in ('X', 'Y', 'Z'):
                value = vector.number(axis, 1 if name == 'Zoom' else 0)
                target.one(name).set_field(axis, length(value, units, reverse=axis == 'Y') if name == 'Offset' else value)
            vector.finish()
    record.finish()


def _drawing(record, *, index, units, groups, pads, policy, physical_font_width=True):
    shape = policy.drawing_factory(index)
    shape.set_field('Type', enum_value(record.value('Type', 'None'), DRAWING_TYPES))
    shape.set_field('Locked', record.boolean('Locked', False))
    shape.set_field('Layer', enum_value(record.value('Layer', LAYERS[0]), LAYERS))
    shape.set_field('AllLayers', record.boolean('AllLayers', False))
    shape.set_field('Group', mapped_group(record, groups, shape, resolve_key=policy.resolve_key))
    key = record.integer('PadId', -1)
    shape.set_field('PadId', policy.resolve_key(shape, 'PadId', key, pads))
    shape.set_field('Width', length(record.number('LineWidth'), units) if record.has('LineWidth') else -1)
    if shape.scalar('Type') == 7:
        from .xml_font_import import read_font, read_text_extent
        shape.set_field('VectorFont', record.boolean('FontVector', True))
        shape.set_field('FontName', record.text('FontName', ''))
        for public, own, default in (('FontSize', 'FontSize', 6),
                                    ('FontScale', 'FontScale', 1), ('LineSpacing', 'LineSpacing', 1.2), ('Angle', 'TextAngle', 0)):
            shape.set_field(own, record.number(public, default))
        shape.set_field('FontWidth',read_width(record,units=units,physical=physical_font_width))
        shape.set_field('TextShow', enum_value(record.value('TextShow', 'Any Text'), TEXT_SHOW))
        for public, own, labels in (('HorzAlign', 'TextHorz', HORZ), ('VertAlign', 'TextVert', VERT),
                                    ('TextAlign', 'TextAlign', HORZ)):
            shape.set_field(own, enum_value(record.value(public, labels[0]), labels, negative=labels[-1]))
        for line in record.rows(('Lines', 'TextLines'), ('Item', 'TextLine')):
            shape.one('TextLine').add('pt', line.content())
            line.finish(allow_text=True)
        read_font(record, shape)
        read_text_extent(record)
    replace_rows(shape, 'Points_New', read_points(record, units=units))
    record.finish()
    return shape


def _dimension(record, *, index, units, groups, objects, policy, physical_font_width=True):
    record.integer('Id', index)
    result = Element('Dimension', index)
    fields(result, Enabled=True, Locked=record.boolean('Locked', False),
           Type=enum_value(record.value('Type', 'Horizontal'), ('Horizontal', 'Vertical', 'Free', 'Radius', 'Pointer')),
           Layer=enum_value(record.value('Layer', LAYERS[0]), LAYERS),
           Group=mapped_group(record, groups, result, resolve_key=policy.resolve_key))
    for side in ('1', '2'):
        mode = enum_value(record.value('Connected'+side, '-1'), ('Pad', 'Shape', 'Hole', 'Terminal', 'None'), negative='None')
        owner, member = record.integer('Object'+side, -1), record.integer('SubObject'+side, -1)
        # Ordinary attachments use public object keys. Terminal attachments use
        # a pad ordinal and a zero-based terminal position instead.
        if mode in (0, 1, 2) and member >= 0 and objects[mode]:
            member = policy.resolve_key(result, 'SubObject'+side, member, objects[mode])
        fields(result, **{'Connected'+side: mode, 'Object'+side: owner, 'SubObject'+side: member,
                          'Point'+side: record.integer('Point'+side, -1)})
    for suffix in ('1', '2', 'D'):
        for axis, value in zip(('X', 'Y'), point(record, units, ('X'+suffix, 'Y'+suffix), 0)):
            result.add(axis+suffix, value)
    fields(result, ArrowSize=length(record.number('ArrowSize', 0), units),
           Units=enum_value(record.value('Units', 'Common'), ('Common', 'inch', 'mil', 'mm')),
           VectorFont=record.boolean('FontVector', True), FontName=record.text('FontName', ''),
           FontSize=record.integer('FontSize', 6), FontWidth=read_width(record,units=units,physical=physical_font_width),
           FontScale=record.number('FontScale', 1), ShowUnits=record.boolean('ShowUnits', True),
           Angle=record.number('Angle', 0), ExternalRadius=record.integer('ExternalRadius', 0),
           PointerMode=enum_value(record.value('PointerMode', 0), POINTER_MODES),
           PointerText=record.text('PointerText', ''))
    from .xml_font_import import read_font
    read_font(record, result)
    record.finish()
    return result


def read_pattern(record, *, units, styles, policy, physical_font_width=True):
    style = record.text('PatternStyle')
    defaults = policy.read_defaults(record) if policy.read_defaults is not None else {}
    if record.has('Id'):
        record.integer('Id')  # PatternStyle is the reference key in schematic libraries.
    pattern = policy.pattern_factory(record.text('Name', ''))
    if record.has('RefDes') and 'RefDes' not in defaults:
        reference = pattern.add('RefDes', record.text('RefDes'))
        reference.annotations['xml_only'] = 'public library reference prefix; absent from DCH embedded footprints'
        if not reference.values[0]:
            reference.annotations['asc_omit'] = 'empty XML-only footprint reference prefix'
    pattern.set_field('Mounting', enum_value(record.value('Mounting', '-1'), ('Through', 'SMD', 'Chassis', 'Mixed', 'None'), negative='None'))
    pattern.set_field('Type', enum_value(record.value('Type', 'Free'), policy.pattern_types))
    pattern.set_field('PatternOrientation', enum_value(record.number('Orientation', 0), ('0', '90', '180', '270')))
    pattern.set_field('LockProperties', record.boolean('LockTypeChange', False))
    for name in ('Width', 'Height'):
        pattern.set_field(name, length(record.number(name, 0), units))
    for index in (1, 2, 3):
        pattern.set_field('Spacing'+str(index), length(record.number('Float'+str(index), 0), units))
    for index in (1, 2):
        pattern.set_field('Number'+str(index), record.integer('Int'+str(index), 0))
    for public, own in (('Name_Description', 'Name_Description'), ('Name_Unique', 'Name_Unique'),
                        ('Datasheet', 'Datasheet'), ('Manufacturer', 'Pattern_Manufacturer')):
        if public in defaults:
            continue
        target = pattern.set_field(own, record.text(public, ''))
        if own == 'Datasheet' and not target.values[0]:
            target.annotations['asc_omit'] = 'empty XML-only footprint datasheet'
    for name in record.rows('PossibleNames', 'PossibleName'):
        pattern.one('PossibleNames').add('PossibleName', name.content())
        name.finish(allow_text=True)
    read_category(record.take('Category'), pattern)
    origin = record.take('Origin')
    if origin is not None:
        for own, value in zip(('OriginX', 'OriginY'), point(origin, units, default=0)):
            pattern.set_field(own, value)
        for public, own in (('Cross', 'OriginCross'), ('Circle', 'OriginCircle')):
            pattern.set_field(own, origin.boolean(public, True))
        pattern.set_field('OriginCommon', enum_value(origin.value('Common', 'Hide'), ('Show', 'Hide')))
        pattern.set_field('OriginCourtyard', enum_value(origin.value('Courtyard', 'Show'), ('Show', 'Hide', 'Show if not center')))
        origin.finish()
    recovery = record.take('RecoveryCode')
    if recovery is not None:
        pattern.set_field('RecoveryCode', recovery.content())
        pattern.set_field('RecoveryCode_Generator', recovery.boolean('Generator', True))
        pattern.set_field('RecoveryCode_Model', recovery.boolean('Model', True))
        recovery.finish(allow_text=True)
    groups = read_groups(record, pattern, units=units, container='Pattern_Groups')
    read_user_fields(record, pattern)
    used = set()

    def apply_style(source, owner):
        key = source.text('Style')
        if key not in styles:
            raise ValueError(f'{source.node.path}: unresolved pad style {key!r}')
        read_pad_style(XmlRecord(styles[key]), owner, units=units)
        used.add(key)
        return key

    default = record.take('DefPad', required=True)
    default_style = apply_style(default, pattern)
    default.finish()
    pads, pad_ids = [policy.pad_factory(0)], {}
    for source in record.rows('Pads', 'Pad'):
        key = source.integer('Id')
        if key in pad_ids:
            raise ValueError(f'{source.node.path}: duplicate pad Id')
        index = len(pads)
        pad_ids[key] = index
        pad = policy.pad_factory(index)
        pad.annotations.clear()
        selected_style = apply_style(source, pad)
        pad.set_field('Standard', source.boolean('DefStyle', bool(selected_style) and selected_style == default_style))
        pad.set_values(index, source.text('Number', ''), source.text('Note', ''), *point(source, units, default=0))
        pad.set_field('Number_New', index)
        pad.set_field('Id', key)
        pad.set_field('PadAngle', source.number('Angle', 0))
        pad.set_field('Locked', source.boolean('Locked', False))
        # The placed side is explicit even if the shared style chose another side.
        pad.set_field('Sided', enum_value(source.value('Side', 'Bottom' if pad.scalar('Sided') else 'Top'), ('Top', 'Bottom')) == 1)
        pad.set_field('Group', mapped_group(source, groups, pad, resolve_key=policy.resolve_key))
        source.finish()
        pads.append(pad)
    pads.append(policy.pad_factory(len(pads)))
    replace_rows(pattern, 'Pads', pads)
    drawings, shape_ids = [policy.drawing_factory(0)], {}
    for source in record.rows('Shapes', 'Shape'):
        key = source.integer('Id')
        if key in shape_ids:
            raise ValueError(f'{source.node.path}: duplicate shape Id')
        shape_ids[key] = len(drawings)
        drawings.append(_drawing(source, index=len(drawings), units=units, groups=groups, pads=pad_ids, policy=policy, physical_font_width=physical_font_width))
    drawings.append(policy.drawing_factory(len(drawings)))
    replace_rows(pattern, 'Shapes', drawings)
    holes, hole_ids = [Element('Hole', False, False, 0, 0, 0, 0, -1)], {}
    for source in record.rows('Holes', 'Hole'):
        key = source.integer('Id')
        if key in hole_ids:
            raise ValueError(f'{source.node.path}: duplicate hole Id')
        hole_ids[key] = len(holes)
        hole = Element('Hole', True, source.boolean('Locked', False), *point(source, units, default=0),
                             length(source.number('Diam', 0), units), length(source.number('HoleDiam', 0), units),
                             -1)
        hole.set_argument(6, mapped_group(source, groups, hole, resolve_key=policy.resolve_key))
        holes.append(hole)
        source.finish()
    holes.append(Element('Hole', False, False, 0, 0, 0, 0, -1))
    replace_rows(pattern, 'Holes', holes)
    for index, source in enumerate(record.rows('Dimensions', 'Dimension')):
        pattern.one('Dimensions').append(_dimension(source, index=index, units=units, groups=groups,
                                                    objects=(pad_ids, shape_ids, hole_ids), policy=policy,
                                                    physical_font_width=physical_font_width))
    model = record.take('Model3D')
    if model is not None:
        _model(model, pattern.one('Model3D'), units=units)
    record.finish()
    return style, ImportedPattern(pattern, pad_ids, shape_ids, hole_ids, used, defaults)
