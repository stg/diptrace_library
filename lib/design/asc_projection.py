"""ASC record views over our editable data.

The document is never mutated. Public field order belongs to this adapter, while
XML-only identifiers stay in the source model. Document
export methods combine these record views with settings and display context.
"""
from decimal import Decimal
import math

from .model import Element, Value
from .asc_model_body import project_model_body
from .asc_policy import (model3d_arguments, number_text,
                         calculation_number as _calculation, component_orientation)
from .asc_pad_geometry import PadContour, legacy_pad_contour, requires_modern_points
from .pad_data import MASK_FIELDS,mask_state,compatibility_mask


class ProjectionError(ValueError):
    pass


PIN_FIELDS = '''Enabled Type Orientation Number NetNumber Length Name StringNumber
FConnect ShowName PinNumXShift PinNumYShift PinNameXShift PinNameYShift ElectricType
Hidden Locked ModelSig NoConnect NameFontSize NameFontWidth NameFontScale NetName
SignalDelay Group PinNameRotate PinNumRotate'''.split()
NET_FIELDS = '''Enabled UniteByName ConnectPinByName Locked ActiveLine ActivePoint
Number Width Clearance NetClass CustomColor WireColor Global Parts Lines'''.split()
LINE_FIELDS = '''Connect1 Connect2 ConnectL1 ConnectL2 ConnectB1 ConnectB2 Page
ConnectMode1 ConnectMode2 NetNumber Region Number Hidden Points Selected Group
CanUnhide Arrows'''.split()
PAD_FIELDS = '''Number Number_New Inverted Locked Sided DisableTopMask
DisableBottomMask DisableTopPaste DisableBottomPaste CustomSwell CustomShrink
CustomSwell_New CustomShrink_New PadWidth PadHeight PadHole PadHoleH PadHoleType
SurfacePad PadShape PadShape_New PadAngle PadShape_X PadShape_Y PadCorner
PadWidth_New PadHeight_New Group Standard Points PadPoints_New PadTerminalCount
PadTerminal PadMask_Percent PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide
PadMask_TopSegments PadMask_BotSegments'''.split()
PATTERN_FIELDS = '''Type VariableParameter1 VariableParameter2 VariableParameter3
VariableParameter4 VariableParameter5 InternalConnections Number1 Number2
Spacing1 Spacing2 Spacing3 LockProperties PatternOrientation Width Height
OriginCross OriginCircle OriginCommon OriginCourtyard Name_Description Name_Unique
RecoveryCode RecoveryCode_Generator RecoveryCode_Model Pattern_Manufacturer
PadCorner PadShape_X PadShape_Y PadWidth PadHeight PadShape SurfacePad PadHole
PadHoleH PadHoleType PadTerminalCount TopMask_State BotMask_State TopPaste_State
BotPaste_State CustomSwell_New CustomShrink_New PadMask_Percent PadMask_EdgeGap
PadMask_SegmentGap PadMask_SegmentSide PadMask_TopSegments PadMask_BotSegments
OriginX OriginY UserFields PadPoints Pattern_Groups Pads Shapes Holes Dimensions
Model3D Mounting Pattern_CategoryName Pattern_CategoryIndex Pattern_CategoryTypes
PossibleNames'''.split()
DIMENSION_FIELDS = '''Enabled Locked Type Connected1 Object1 SubObject1 Point1
Connected2 Object2 SubObject2 Point2 Layer X1 Y1 X2 Y2 XD YD ArrowSize Units
VectorFont FontName FontSize FontScale FontWidth ShowUnits Angle ExternalRadius
PointerMode PointerText Group'''.split()
SYMBOL_DRAWING_FIELDS = '''Enabled Orientation Type FontSize FontColor FontType
FontName Name PenWidth Points TextAngle TextHorz TextVert TextAlign LineSpacing
Group ShowPart MarkingGenerated TextLine Points_New Locked VectorFont FontWidth
FontScale'''.split()
COMPONENT_FIELDS = '''Enabled Selected Value BaseName BaseRefDes X Y Type Number1
Number2 Page Orientation Group Number Width Height ShowText TextAlign PartNumber
PartType PartName PartDescriptor AllowParts ShowText2 TextAlign2 ShowNumbers
TextPosX TextPosY TextPosX2 TextPosY2 PartString HiddenId UserFields FieldIndex1
FieldIndex2 Locked Angle LibPath LibPath_Variable ModelType ModelString
LockProperties Origin_X Origin_Y ModelBody Datasheet HorzFlip VertFlip ShowOrigin
PageHiddenId Manufacturer Component_CategoryName Component_CategoryIndex
Component_CategoryTypes CustomMarkingFont MarkingFontSize MarkingFontAll
ShowRefDes ShowName ShowValue ShowManufacturer ShowDatasheet Suppliers Pins Shapes
Pattern'''.split()
LEGACY_COMPONENT_VIEW = dict(ShowText=0, TextAlign=0, ShowText2=0, TextAlign2=0,
                            TextPosX=0, TextPosY=0, TextPosX2=0, TextPosY2=0,
                            FieldIndex1=-1, FieldIndex2=-1)
PAGE_FIELDS = '''Zones PageWidth PageHeight HorzZones VertZones ZoneStandard
ZoneFontName ZoneFontSize ZoneBorder HorzZoneBorder VertZoneBorder PageXPos
PageyPos PageScale PageType PageHiddenId FLeft FTop FRight FBottom'''.split()
SETTINGS_FIELDS = '''GridSize OriginEnabled clAxis BusConnectionFont PinNumberFont
PartFontSize PartFontColor UsePartFontColor GridEnabled GridSnap DisplayTitles
DisplaySheet BusConNetName BusConNetNumber ShowPinNumbers HidePinNumbers
BusConAbove BusConBelow BusLineWidth WireLineWidth TableLineWidth TitlesLineWidth
NodeSize UnitsMM UnitsMIL UnitsINCH ERC_PinType ERC_NotConnected ERC_SinglePin
ERC_Short ERC_VCCTemplate ERC_GNDTemplate ERC_PinSuperimpose'''.split()
SCHEMATIC_DRAWING_FIELDS = '''Enabled Selected Orientation Type FontSize FontColor
Color BrushColor FontType Page Group PenWidth FontName Name BitmapIndex Points
RelatedNet RelatedBus Locked VectorFont FontWidth FontScale Picture_Width
Picture_Height Picture_Transparent Picture_File Picture_File_Variable
Picture_Proportions TextHorz TextVert TextAlign TextAngle LineSpacing TextLine
Points_New'''.split()


def _value(value):
    if value.kind == 'boolean':
        return Value('Y' if value.value else 'N', 'string', source=value.source)
    if value.kind == 'number':
        return Value(Decimal(number_text(value.value)), 'number', value.unit, source=value.source)
    if value.kind == 'string':
        return Value(value.value, 'string', source=value.source)
    return value


def _head(node, name=None):
    return Element(name or node.kind, *map(_value, node.arguments), source=node.source)


def _visible(node):
    return [child for child in node.children()
            if child.kind != 'UnresolvedKeys' and not child.annotations.get('asc_omit')]


_COUNTED_ARRAYS = {
    'Component_CategoryTypes': ('Component_Type', 'Type'),
    'Pattern_CategoryTypes': ('Pattern_Type', 'Type'),
    'PossibleNames': ('PossibleName',),
    'PadMask_TopSegments': ('pt',),
    'PadMask_BotSegments': ('pt',),
}


def _plain(node):
    """Homogeneous public arrays and scalar/tuple fields keep their own order."""
    result = _head(node)
    children = _visible(node)
    if node.kind in _COUNTED_ARRAYS:
        if any(child.kind not in _COUNTED_ARRAYS[node.kind] for child in children):
            raise ProjectionError(f'{node.path}: unexpected counted-array record')
        result.set_values(len(children))
    for child in children:
        result.append(_plain(child))
    return result


def project_user_fields(node):
    """format public names for unnamed user fields, preserving their values."""
    result = _plain(node)
    for field in result.children('UserField'):
        if field.values and not field.values[0].replace(' ', ''):
            field.set_argument(0, 'Untitled')
    return result


def _ordered(node, names, handlers=None, *, omitted=()):
    handlers = handlers or {}
    result = _head(node)
    unknown = [child.kind for child in _visible(node) if child.kind not in names and child.kind not in omitted]
    if unknown:
        raise ProjectionError(f'{node.path}: no ASC projection for {unknown}')
    for name in names:
        children = node.children(name)
        if len(children) != 1:
            raise ProjectionError(f'{node.path}: expected one {name}, found {len(children)}')
        result.append(handlers.get(name, _plain)(children[0]))
    return result


def project_pin(pin):
    """Project one placed pin, including every ASC field in order."""
    return _ordered(pin, PIN_FIELDS)


def project_page(page):
    """Page layout; ASC deliberately omits the retained title blocks."""
    def viewport(field):
        
        # formatting, unlike the DCH viewport's retained fractional coordinates.
        return Element(field.kind, round(_calculation(field)), source=field.source)
    return _ordered(page, PAGE_FIELDS, {'PageXPos': viewport, 'PageyPos': viewport})


def project_settings(settings, *, grid_snap, part_font_size=None,
                     part_font_color=None, use_part_font_color=None):
    """Settings in ASC order, with application-only choices supplied explicitly."""
    overrides = dict(GridSnap=grid_snap, PartFontSize=part_font_size,
                     PartFontColor=part_font_color, UsePartFontColor=use_part_font_color)
    view = settings.clone()
    for name, value in overrides.items():
        if value is not None:
            view.set_field(name, value)
    return _ordered(view, SETTINGS_FIELDS, omitted=('MarkingFontName',))


def project_net(net):
    """Project a net and its complete wire records, using current model values.

    Reference indices must first be rebuilt at the document boundary after edits.
    Number and connection fields here are not inferred from names or geometry.
    """
    def lines(node):
        result = _head(node)
        for child in _visible(node):
            if child.kind != 'Line':
                raise ProjectionError(f'{node.path}: expected Line, found {child.kind}')
            result.append(_ordered(child, LINE_FIELDS))
        return result
    return _ordered(net, NET_FIELDS, {'Lines': lines})


def project_model3d(model, *, variable_fallback=True):
    """Project named XML-style 3D placement into the public ASC tuple."""
    names = {'Model3DFile', 'Model3DFile_Variable', 'Offset', 'Rotate', 'Zoom',
             'Mirror', 'NoSearch', 'Units', 'IPC_XOff', 'IPC_YOff', 'AutoHeight',
             'AutoColor', 'Type', 'KeepPins', 'pt'}
    unknown = [child.kind for child in _visible(model) if child.kind not in names]
    if unknown:
        raise ProjectionError(f'{model.path}: no 3D ASC projection for {unknown}')
    result = _head(model)
    for name in ('Model3DFile', 'Model3DFile_Variable'):
        fields = model.children(name)
        if name == 'Model3DFile_Variable' and not variable_fallback and not fields:
            result.add(name, '')
            continue
        if name == 'Model3DFile_Variable' and variable_fallback and (not fields or
                len(fields) == 1 and len(fields[0].values) == 1 and not fields[0].values[0].strip()):
            # Before schema 45 the one serialized path supplies both views.
            
            # from its filename. Configured path-variable compression remains
            # separate; original empty occurrences stay editable in the model.
            fields = model.children('Model3DFile')
        if len(fields) != 1:
            raise ProjectionError(f'{model.path}: expected one {name}')
        field = _plain(fields[0])
        field.kind = name
        result.append(field)
    result.add('pt', *map(_value, model3d_arguments(model)))
    return result


def _project_terminals(parent):
    terminals = parent.children('PadTerminal')
    count = parent.child('PadTerminalCount')
    if count is None or count.values != (len(terminals),):
        raise ProjectionError(f'{parent.path}: PadTerminalCount does not match PadTerminal records')
    container = _plain(count)
    for terminal in terminals:
        projected = _ordered(terminal, '''Type X Y Angle ShapeWidth ShapeHeight
                              ShapeCorner ShapePoints'''.split())
        projected.set_values()
        points = projected.child('ShapePoints')
        points.set_values(len(points.children('pt')))
        container.append(projected)
    return container


def project_pad(pad):
    """Project a complete pad from modern editable geometry into both ASC views.

    PadAngle drives Inverted and the old contour. ASC's Standard value also
    requires near-zero rotation; the shared model's choice is independent.
    This adapter never replaces the source's exact shape, angle, or points.
    """
    unknown = [child.kind for child in _visible(pad) if child.kind not in (*PAD_FIELDS, 'Id')]
    if unknown:
        raise ProjectionError(f'{pad.path}: no pad ASC projection for {unknown}')

    def field(name):
        fields = pad.children(name)
        if len(fields) != 1:
            raise ProjectionError(f'{pad.path}: expected one {name}, found {len(fields)}')
        return fields[0]

    shape = int(field('PadShape_New').values[0])
    width, height, corner = (_calculation(field(name))
                             for name in ('PadWidth_New', 'PadHeight_New', 'PadCorner'))
    angle = float(field('PadAngle').values[0])
    inverted = abs(angle) >= .001 and abs(angle-math.pi) >= .001
    modern_points = pad.child('PadPoints_New')
    points = tuple((_calculation(point), _calculation(point, 1))
                   for point in modern_points.children('pt')) if modern_points is not None else ()
    if round(angle*180/math.pi) % 90 or shape >= 3 or shape == 2 and corner != 0:
        contour = legacy_pad_contour(shape, width, height, corner, points,
                                     angle-math.pi/2 if inverted else angle)
    else:
        contour = PadContour(shape, width, height, points)
    overrides = {
        'Number': -1 if shape == 20 else field('Number_New').values[0],
        'Inverted': inverted, 'PadShape': contour.shape,
        'PadWidth': contour.width, 'PadHeight': contour.height,
        'Standard': bool(field('Standard').values[0]) and abs(angle) < .001,
    }
    for old_name, new_name, states in (
            ('CustomSwell', 'CustomSwell_New', ('DisableTopMask', 'DisableBottomMask')),
            ('CustomShrink', 'CustomShrink_New', ('DisableTopPaste', 'DisableBottomPaste'))):
        overrides[old_name] = (-1000 if any(mask_state(pad,name) == 3 for name in states)
                               else field(new_name).values[0])
    result = _head(pad)
    for name in PAD_FIELDS:
        if name in MASK_FIELDS:
            result.add(name,*(_value(Value.of(value)) for value in compatibility_mask(mask_state(pad,name))))
        elif name in overrides:
            result.add(name, _value(Value.of(overrides[name])))
        elif name == 'Points':
            geometry = result.add(name)
            for point in contour.points:
                geometry.add('pt', *(_value(Value.of(v)) for v in point))
        elif name == 'PadPoints_New':
            if requires_modern_points(contour.points, points):
                geometry = result.add(name)
                if modern_points is not None:
                    for point in modern_points.children('pt'):
                        geometry.append(_plain(point))
        elif name == 'PadTerminalCount':
            result.append(_project_terminals(pad))
        elif name == 'PadTerminal':
            continue  # ASC nests these in the preceding count record.
        else:
            result.append(_plain(field(name)))
    return result


def project_pattern_drawing(shape, pattern, *, line_width=None, text_bounds=None):
    """Return one footprint drawing's flat public ASC sibling records.

    ``line_width(layer)`` supplies application fallback pen widths. A type-7
    vector text uses the built-in semantic metrics provider. System-font text
    requires ``text_bounds(shape)`` to return two physical box corners from a
    font layout service. These inputs stay separate from the stored design.
    """
    names = {'Type', 'Locked', 'Layer', 'TextLine', 'FontName', 'VectorFont',
             'FontSize', 'FontScale', 'FontWidth', 'TextShow', 'Width',
             'Points_New', 'TextAngle', 'TextHorz', 'TextVert', 'TextAlign',
             'LineSpacing', 'AllLayers', 'Group'}
    unknown = [node.kind for node in _visible(shape) if node.kind not in names]
    if unknown:
        raise ProjectionError(f'{shape.path}: no footprint drawing projection for {unknown}')
    fields = {}
    for name in names:
        nodes = shape.children(name)
        if len(nodes) != 1:
            raise ProjectionError(f'{shape.path}: expected one {name}, found {len(nodes)}')
        fields[name] = nodes[0]
    kind, layer = shape.scalar('Type'), shape.scalar('Layer')
    scales = tuple(_calculation(pattern.one(name)) for name in ('Width', 'Height'))
    points = tuple((_calculation(point), _calculation(point, 1))
                   for point in fields['Points_New'].children('pt'))
    if kind == 7:
        if text_bounds is None:
            if shape.scalar('VectorFont') not in (True, 'Y'):
                raise ProjectionError(f'{shape.path}: system-font bounds require a font layout service')
            from .vector_text import pattern_vector_text_bounds
            text_bounds = pattern_vector_text_bounds
        corners = tuple(text_bounds(shape))
        if len(corners) != 2 or any(len(point) != 2 for point in corners):
            raise ProjectionError(f'{shape.path}: text bounds require two box corners')
    else:
        corners = points[:3] if len(points) > 1 else ()
    if (points or corners) and not all(scales):
        raise ProjectionError(f'{pattern.path}: normalized ASC drawing needs nonzero Width and Height')
    compatibility = [0.]*6
    for i, point in enumerate(corners):
        compatibility[i*2:i*2+2] = [float(v)/scale for v, scale in zip(point, scales)]
    legacy_layer = (1 if layer in (16, 18, 20) else 6 if layer in (17, 19, 21)
                    else 1 if layer > 14 else layer)
    width = _calculation(fields['Width'])
    if width < 0:
        if line_width is None:
            raise ProjectionError(f'{shape.path}: fallback line width for layer {layer} is required')
        resolved = Value.of(line_width(layer))
        if resolved.kind != 'number' or resolved.unit or resolved.value < 0:
            raise ProjectionError(f'{shape.path}: fallback line width requires a nonnegative number')
        width = resolved.value
    text = fields['TextLine'].children('pt')
    first_line = text[0].values[0] if text else ''
    header = (max(0, kind), shape.scalar('Locked'), legacy_layer, *compatibility,
              first_line, shape.scalar('FontName'), shape.scalar('VectorFont'),
              shape.scalar('FontSize'), shape.scalar('FontScale'), shape.scalar('FontWidth'),
              round(float(shape.scalar('TextAngle'))/(math.pi/2)), width, shape.scalar('TextShow'))
    result = [Element('Shape', *(_value(Value.of(v)) for v in header))]
    if points:
        normalized = Element('Points')
        for point in points:
            normalized.add('pt', *(_value(Value.of(v/scale)) for v, scale in zip(point, scales)))
        result.append(normalized)
    result.extend(_plain(fields[name]) for name in
                  ('Width', 'Layer', 'TextHorz', 'TextVert', 'TextAlign', 'LineSpacing', 'TextAngle'))
    if points:
        result.append(_plain(fields['Points_New']))
    if len(text) > 1:
        lines = _plain(fields['TextLine'])
        lines.set_values(len(text))
        result.append(lines)
    result.extend(_plain(fields[name]) for name in ('AllLayers', 'Group'))
    return tuple(result)


def project_pattern(pattern, *, line_width=None, text_bounds=None):
    """Project a complete footprint, with explicit pen/font export context.

    Non-ASC facts remain in the authoring tree. Unknown public fields and
    incomplete layout inputs prevent export instead of losing data silently.
    """
    unknown = [node.kind for node in _visible(pattern)
               if node.kind not in PATTERN_FIELDS and node.kind != 'PadTerminal']
    if unknown:
        raise ProjectionError(f'{pattern.path}: no footprint ASC projection for {unknown}')
    result = _head(pattern)
    for name in PATTERN_FIELDS:
        fields = pattern.children(name)
        if len(fields) != 1:
            raise ProjectionError(f'{pattern.path}: expected one {name}, found {len(fields)}')
        field = fields[0]
        if name == 'PadTerminalCount':
            result.append(_project_terminals(pattern))
        elif name == 'Model3D':
            result.append(project_model3d(field))
        elif name == 'UserFields':
            result.append(project_user_fields(field))
        elif name == 'Pads':
            pads = _head(field)
            # The reserved default-pad slot participates in array numbering
            # even though the public ASC view omits its record.
            entries = field.children()
            for index, pad in enumerate(entries):
                if pad.kind != 'Pad':
                    raise ProjectionError(f'{field.path}: expected Pad, found {pad.kind}')
                if pad.annotations.get('asc_omit'):
                    continue
                projected = project_pad(pad)
                projected.set_argument(0, index)
                pads.append(projected)
            result.append(pads)
        elif name == 'Shapes':
            shapes = _head(field)
            for shape in _visible(field):
                if shape.kind != 'Shape':
                    raise ProjectionError(f'{field.path}: expected Shape, found {shape.kind}')
                for record in project_pattern_drawing(shape, pattern, line_width=line_width,
                                                      text_bounds=text_bounds):
                    shapes.append(record)
            result.append(shapes)
        elif name == 'Dimensions':
            dimensions = _head(field)
            for dimension in _visible(field):
                if dimension.kind != 'Dimension':
                    raise ProjectionError(f'{field.path}: expected Dimension, found {dimension.kind}')
                projected = _ordered(dimension, DIMENSION_FIELDS)
                projected.set_values()  # The model index is not an ASC argument.
                dimensions.append(projected)
            result.append(dimensions)
        else:
            result.append(_plain(field))
    return result


def project_symbol_drawing(shape, *, index=None, text_bounds=None, generated_font_name=None):
    """A complete placed-symbol drawing with a derived legacy text box.

    TextLine is the current text; Name is its generated single-line ASC view.
    Orientation is likewise derived from the current angle.
    A caller may supply the application font name used for generated labels;
    leaving it unset preserves the stored name instead of guessing UI settings.
    """
    return _project_drawing(shape, SYMBOL_DRAWING_FIELDS, index=index,
        text_bounds=text_bounds, generated_font_name=generated_font_name, omit_empty=True)


def project_schematic_drawing(shape, *, text_bounds=None):
    """Sheet drawing, sharing text geometry with symbol drawings."""
    result = _project_drawing(shape, SCHEMATIC_DRAWING_FIELDS, text_bounds=text_bounds)
    result.set_values()  # Sheet drawing headers do not contain an array index.
    return result


def _project_drawing(shape, names, *, index=None, text_bounds=None,
                     generated_font_name=None, omit_empty=False):
    unknown = [node.kind for node in _visible(shape) if node.kind not in names]
    if unknown:
        raise ProjectionError(f'{shape.path}: no symbol drawing projection for {unknown}')
    fields = {}
    for name in names:
        if name in ('Name', 'Orientation', 'Points'):
            continue  # Derived format views rather than separate authoring data.
        nodes = shape.children(name)
        if name == 'Picture_File_Variable' and not nodes:
            nodes = shape.children('Picture_File')
        if len(nodes) != 1:
            raise ProjectionError(f'{shape.path}: expected one {name}, found {len(nodes)}')
        fields[name] = nodes[0]
    lines = fields['TextLine'].children('pt')
    result = _head(shape)
    if index is not None:
        result.set_values(index)
    for name in names:
        if name == 'Name':
            result.add(name, _value(lines[0].arguments[0] if lines else Value.of('')))
        elif name == 'Orientation':
            result.add(name, round(float(shape.scalar('TextAngle'))/(math.pi/2)))
        elif name == 'Points':
            if shape.scalar('Type') == 10:
                if text_bounds is None:
                    if shape.scalar('VectorFont') not in (True, 'Y'):
                        raise ProjectionError(f'{shape.path}: system-font bounds require a font layout service')
                    from .vector_text import symbol_vector_text_bounds
                    text_bounds = symbol_vector_text_bounds
                geometry = result.add(name)
                layout_shape = shape
                if generated_font_name is not None and shape.scalar('MarkingGenerated') in (True, 'Y'):
                    layout_shape = shape.clone()
                    layout_shape.set_field('FontName', generated_font_name)
                for point in text_bounds(layout_shape):
                    geometry.add('pt', *(_value(Value.of(v)) for v in point))
            else:
                geometry = _plain(fields['Points_New'])
                geometry.kind = name
                result.append(geometry)
        elif name == 'FontName' and generated_font_name is not None and shape.scalar('MarkingGenerated') in (True, 'Y'):
            result.add(name, _value(Value.of(generated_font_name)))
        elif name == 'TextLine' and not lines and omit_empty:
            continue
        elif name == 'Points_New' and not fields[name].children('pt') and omit_empty:
            continue
        else:
            field = _plain(fields[name])
            field.kind = name
            result.append(field)
    return result


def project_component(part, *, line_width=None, symbol_text_bounds=None,
                      pattern_text_bounds=None, generated_font_name=None):
    """Project a complete placed component from current editable fields.

    Array ordinals belong to this output view. Stable document identities and
    stored wire occurrences remain in the authoring tree, including after moves.
    """
    unknown = [node.kind for node in _visible(part) if node.kind not in COMPONENT_FIELDS]
    if unknown:
        raise ProjectionError(f'{part.path}: no component ASC projection for {unknown}')
    result = _head(part)
    for name in COMPONENT_FIELDS:
        if name in LEGACY_COMPONENT_VIEW:
            result.add(name, LEGACY_COMPONENT_VIEW[name])
            continue
        if name == 'Orientation':
            result.add(name, component_orientation(part))
            continue
        fields = part.children(name)
        if name == 'LibPath_Variable' and (not fields or len(fields) == 1 and not fields[0].values[0].strip()):
            fields = part.children('LibPath')
        if len(fields) != 1:
            raise ProjectionError(f'{part.path}: expected one {name}, found {len(fields)}')
        field = fields[0]
        if name in ('Pins', 'Shapes'):
            collection = _head(field)
            for index, item in enumerate(_visible(field)):
                if name == 'Pins':
                    if item.kind != 'Pin':
                        raise ProjectionError(f'{field.path}: expected Pin, found {item.kind}')
                    projected = project_pin(item)
                    projected.set_argument(0, index)
                else:
                    if item.kind != 'Shape':
                        raise ProjectionError(f'{field.path}: expected Shape, found {item.kind}')
                    projected = project_symbol_drawing(item, index=index, text_bounds=symbol_text_bounds,
                                                       generated_font_name=generated_font_name)
                collection.append(projected)
            result.append(collection)
        elif name == 'Pattern':
            result.append(project_pattern(field, line_width=line_width, text_bounds=pattern_text_bounds))
        elif name == 'Suppliers':
            result.append(project_suppliers(field))
        elif name == 'UserFields':
            result.append(project_user_fields(field))
        elif name == 'ModelBody':
            result.append(project_model_body(field))
        else:
            projected = _plain(field)
            projected.kind = name
            result.append(projected)
    return result


def project_suppliers(suppliers):
    """Project current supplier fields; destination omissions are reported above."""
    names = ('PartNumber', 'Manufacturer', 'Pattern', 'Supplier', 'Currency', 'MainSupplier')
    unknown = [field.kind for field in _visible(suppliers) if field.kind not in names and field.kind not in ('SourceLocator','Prices')]
    if unknown:
        raise ProjectionError(f'{suppliers.path}: no supplier ASC projection for {unknown}')
    result = _head(suppliers)
    for name in names:
        fields = suppliers.children(name)
        if len(fields) != 1:
            raise ProjectionError(f'{suppliers.path}: expected one {name}, found {len(fields)}')
        else:
            result.append(_plain(fields[0]))
    return result
