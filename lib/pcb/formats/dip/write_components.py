"""Placed PCB data in the initial and current physical binary sections.

Boundary rows and compatibility coordinates are export bookkeeping. The model
continues to own only actual pads/drawings/holes, current geometry and identities.
"""
from dataclasses import dataclass

from ....common.binary import NUMBER_LIMIT
from ....common.conversion import info, warn
from ....common.dimension_codec import write_dimension_properties
from ....common.drawing_codec import write_text_properties
from ....common.footprint_codec import (write_pad_geometry, write_holes, write_model,
    write_terminals, write_mask_segments, write_model_extensions, write_pad_extensions)
from ....common.footprint_records import HOLE
from ....common.model import Element
from ....common.pad_masks import MASK_FIELDS, mask_state
from ...model import definitions, markings
from ...model.hierarchy import linkage_path
from ...model.objects import new_pad, new_pattern_drawing
from ..errors import PcbError
from ..output_indices import pad_number
from ..output_validation import check, check_tree, field_value


@dataclass(frozen=True)
class ComponentOutput:
    component: Element
    pads: tuple
    drawings: tuple
    holes: tuple

    @property
    def pattern(self):
        return self.component.one('Pattern')


def component_outputs(board):
    """Build one export's compact arrays with fresh inactive boundary entries."""
    outputs = []
    for component in board.select('Components/Component'):
        check(component, definitions.COMPONENT, destination='DIP')
        pattern = component.one('Pattern')
        check(pattern, definitions.PATTERN, destination='DIP')
        for owner in (component, pattern):
            for child in owner.children():
                if child.kind in owner.schema.fields or child is pattern:
                    continue
                if child.schema is None or child.schema.name != owner.schema.children[child.kind].record:
                    raise PcbError(f'{child.path}: expected {owner.schema.children[child.kind].record}')
                check_tree(child, child.schema, destination='DIP')
        boundary_pad = new_pad()
        boundary_drawing = new_pattern_drawing()
        boundary_hole = Element('Hole', False, False, 0, 0, 0, 0, -1).bind_schema(HOLE)
        outputs.append(ComponentOutput(component,
            (boundary_pad, *pattern.select('Pads/Pad'), boundary_pad),
            (boundary_drawing, *pattern.select('Shapes/Shape'), boundary_drawing),
            (boundary_hole, *pattern.select('Holes/Hole'), boundary_hole)))
    return tuple(outputs)


def _compatibility_number(writer, source, value):
    """Bound a redundant old coordinate; current points are written separately."""
    bounded = min(NUMBER_LIMIT, max(-NUMBER_LIMIT, value))
    if bounded != value:
        writer.compatibility_changes.append(source)
    writer.number(bounded)


def _head(writer, output):
    component, pattern = output.component, output.pattern
    writer.fields(component, 'boolean', 'Enabled Selected')
    writer.fields(pattern, 'integer', 'Type Number1 Number2')
    quarter = writer.quarter_turns(component['Angle'])
    writer.integer(quarter)
    writer.fields(component, 'integer', 'Group Number')
    writer.field(pattern, 'PadShape', 'integer')
    writer.field(pattern, 'SurfacePad', 'boolean')
    for value in (0, 6, 0, 6):
        writer.integer(value)
    for _ in range(4):
        writer.number(0)
    writer.field(component, 'BottomSide', 'boolean')
    writer.field(component, 'ConnectedLayer', 'integer')
    writer.field(component, 'Flipped', 'boolean')
    writer.field(component, 'HiddenId', 'integer')
    writer.fields(pattern, 'number', 'OriginX OriginY')
    writer.boolean(pattern['OriginCommon'] == 0)
    writer.field(component, 'HorizontalFlip', 'boolean')
    fields = component.select('UserFields/UserField')
    writer.integer(len(fields))
    for field in fields:
        writer.fields(field, 'text', 'Name Value')
        writer.field(field, 'Type', 'integer')
    writer.integer(-1)
    writer.integer(-1)
    writer.number(0)
    writer.field(component, 'Locked', 'boolean')
    writer.field(component, 'LibPath', 'text')
    writer.field(component, 'GsType', 'integer')
    writer.rows(pattern.one('PadPoints'), 'pt', 'number number')
    writer.fields(pattern, 'boolean', 'VariableParameter1 VariableParameter2 VariableParameter3 VariableParameter4')
    writer.fields(component, 'number', 'X Y')
    writer.fields(pattern, 'number', 'Spacing1 Spacing2')
    writer.field(pattern, 'VariableParameter5', 'boolean')
    writer.field(pattern, 'Spacing3', 'number')
    writer.field(pattern, 'LockProperties', 'boolean')
    writer.field(component, 'PanelExclude', 'boolean')
    writer.field(pattern, 'PatternOrientation', 'integer')
    writer.field(component, 'ViaStyle', 'integer')
    writer.field(pattern, 'Name', 'text')
    for name in (('Height', 'Width') if quarter % 2 else ('Width', 'Height')):
        writer.field(pattern, name, 'number')
    writer.fields(pattern, 'number', 'PadWidth PadHeight PadHole PadHoleH')
    writer.field(pattern, 'PadHoleType', 'integer')
    path = linkage_path(component)
    writer.integer(len(path))
    for identifier in path:
        writer.integer(identifier)
    writer.fields(component, 'text', 'Name RefDes Value BaseName')


def _pads(writer, output):
    writer.integer(len(output.pads))
    for index, pad in enumerate(output.pads):
        boundary = index in (0, len(output.pads)-1)
        writer.boolean(writer.quarter_turns(pad['PadAngle']) % 2 == 1)
        writer.integer(-1 if boundary else pad_number(pad))
        writer.integer(-1 if boundary else pad['NetNumber'])
        writer.fields(pad, 'number', 'X Y')
        writer.fields(pad, 'text', 'StringNumber Name')
        write_pad_geometry(writer, pad)
        writer.boolean(False)  # Obsolete selection slot.
        for name in ('HideLayer', 'BlindLayer'):
            members = pad.select(name+'/Item')
            writer.integer(len(members))
            for member in members:
                writer.field(member, 'Lay', 'integer')
        spokes = pad.select('CustomSpokes/CustomSpoke')
        writer.integer(len(spokes))
        for spoke in spokes:
            writer.fields(spoke, 'integer', 'Lay Type Spoke')
            writer.field(spoke, 'Width', 'number')
        writer.field(pad, 'Locked', 'boolean')
        for name in MASK_FIELDS:
            writer.boolean(mask_state(pad, name) == 2)
        writer.fields(pad, 'number', 'CustomSwell_New CustomShrink_New')
        writer.field(pad, 'Sided', 'boolean')


def write_pattern_graphics(writer, pattern, *, drawings, holes, placed=False):
    """Initial physical geometry over explicit current/boundary output arrays."""
    writer.integer(len(drawings))
    for shape in drawings:
        if placed and field_value(shape, 'PadId') != -1:
            warn(writer.report, 'placed-drawing-pad', 'dip',
                 'DIP omits a placed drawing pad association; geometry remains.', (shape,))
        kind = shape['Type']
        writer.integer(700 if placed and kind == 7 and field_value(shape, 'MarkingGenerated') else kind)
        dimensions = float(pattern['Width']), float(pattern['Height'])
        geometry = shape.select('Points_New/pt')
        if geometry and any(not size and any(point.values[axis] for point in geometry)
                            for axis, size in enumerate(dimensions)):
            writer.compatibility_changes.append(shape)
        normalized = tuple(tuple(float(value)/size if size else 0 for value, size in zip(point.values, dimensions))
                           for point in geometry)
        controls = [0]*6
        if 0 < kind < 8:
            for index, point in enumerate(normalized[:3 if kind == 6 else 2]):
                controls[2*index:2*index+2] = point
        for value in controls:
            _compatibility_number(writer, shape, value)
        writer.field(shape, 'Locked', 'boolean')
        writer.field(shape, 'Layer', 'integer')
        lines = shape.select('TextLine/pt')
        writer.text(lines[0]['Text'] if lines else '')
        writer.field(shape, 'FontName', 'text')
        writer.field(shape, 'VectorFont', 'boolean')
        writer.field(shape, 'FontSize', 'integer')
        writer.fields(shape, 'number', 'FontScale FontWidth')
        writer.integer(writer.quarter_turns(shape['TextAngle']))
        writer.field(shape, 'TextShow', 'integer')
        writer.field(shape, 'Width', 'number')
        writer.integer(len(geometry))
        for point in normalized:
            for value in point:
                _compatibility_number(writer, shape, value)
    write_holes(writer, holes)
    dimensions = pattern.select('Dimensions/Dimension')
    writer.integer(len(dimensions))
    for dimension in dimensions:
        writer.fields(dimension, 'boolean', 'Enabled Locked')
        write_dimension_properties(writer, dimension)


def write_base_components(writer, outputs):
    """Append components after their count, retaining the plan for extensions."""
    for output in outputs:
        for pad in output.pattern.select('Pads/Pad'):
            if pad.child('Id') is not None:
                warn(writer.report, 'pad-persistent-key', 'dip', 'DIP generates positional placed-pad keys', (pad,),
                     recoverability='current pad data and references remain; independent XML pad identifiers are omitted')
        if output.pattern.child('Sided') is not None:
            notice = warn if output.pattern['Sided'] else info
            notice(writer.report, 'placed-pattern-sided', 'dip',
                   'DIP omits the independent footprint-template Sided setting', (output.pattern,),
                   recoverability='placed component side and individual pad settings remain')
        _head(writer, output)
        _pads(writer, output)
        write_pattern_graphics(writer, output.pattern, drawings=output.drawings, holes=output.holes, placed=True)
        write_model(writer, output.pattern)


def write_pad_mask_overrides(writer, outputs):
    """The current integral mask choices supersede initial Boolean slots."""
    for output in outputs:
        for pad in output.pads:
            for name in MASK_FIELDS:
                writer.integer(mask_state(pad, name))


def component_font_records(outputs):
    """Current font extension order, including generated boundary records."""
    for output in outputs:
        yield output.component, 'MarkingFontSize', None
        for shape in output.drawings:
            yield shape, 'FontSize', 'FontMono'
        for dimension in output.pattern.select('Dimensions/Dimension'):
            yield dimension, 'FontSize', 'FontMono'


def _marking(writer, owner, prefix):
    writer.fields(owner, 'integer', ' '.join(prefix+name for name in ('Show', 'Align', 'Horz', 'Vert')))
    writer.fields(owner, 'number', ' '.join(prefix+name for name in ('X', 'Y', 'Angle')))


def _internal_connections(writer, component):
    pairs = component.select('IntConRecords/Item')
    writer.integer(len(pairs))
    for pair in pairs:
        for name in ('Pad1', 'Pad2'):
            if pair[name] is None:
                raise PcbError(f'{pair.path}: internal connection requires two current pads')
            writer.integer(pad_number(pair[name]))
    policies = component.select('InternalConnections/IntCon')
    writer.integer(len(policies))
    for policy in policies:
        members, tree = policy['Members'], policy['Ratlines']
        if members is None or tree is None:
            raise PcbError(f'{policy.path}: internal connection policy requires a current pad group')
        writer.field(policy, 'ConnectAll', 'boolean')
        writer.integer(len(members))
        for pad in members:
            writer.integer(pad_number(pad))
        writer.integer(len(tree))
        for first, second in tree:
            writer.integer(pad_number(first))
            writer.integer(pad_number(second))


def write_placed_extensions(writer, output):
    """Write current placement, marking and physical geometry for one component."""
    component, pattern = output.component, output.pattern
    writer.fields(pattern, 'number', 'Width Height')
    writer.field(component, 'Angle', 'number')
    writer.fields(pattern, 'boolean', 'OriginCross OriginCircle')
    writer.fields(pattern, 'integer', 'OriginCommon OriginCourtyard')
    writer.field(component, 'ShowFiducial', 'integer')
    writer.fields(pattern, 'text', 'Name_Description Name_Unique RecoveryCode')
    writer.fields(pattern, 'boolean', 'RecoveryCode_Generator RecoveryCode_Model')
    writer.field(component, 'CustomMarkingFont', 'boolean')
    writer.field(component, 'MarkingFontSize', 'integer')
    writer.field(component, 'MarkingFontAll', 'boolean')
    for name in markings.NAMES:
        for side in markings.SIDES:
            _marking(writer, component, name+'_'+side)
    for field in component.select('UserFields/UserField'):
        for side in markings.SIDES:
            _marking(writer, field, side)
    writer.fields(pattern, 'number', 'PadCorner PadShape_X PadShape_Y')
    write_terminals(writer, pattern)
    writer.fields(pattern, 'integer', 'TopMask_State BotMask_State TopPaste_State BotPaste_State')
    writer.fields(pattern, 'number', 'CustomSwell_New CustomShrink_New PadMask_Percent '
                  'PadMask_EdgeGap PadMask_SegmentGap PadMask_SegmentSide')
    write_mask_segments(writer, pattern)
    for pad in output.pads:
        writer.fields(pad, 'integer', 'Group InternalConnection')
        write_pad_extensions(writer, pad)
    for shape in output.drawings:
        for point in shape.select('Points_New/pt'):
            writer.values(point, 'number number')
        write_text_properties(writer, shape)
        writer.field(shape, 'AllLayers', 'boolean')
        writer.field(shape, 'Group', 'integer')
        writer.field(shape, 'MarkingGenerated', 'boolean')
    for hole in output.holes:
        writer.field(hole, 'Group', 'integer')
    for dimension in pattern.select('Dimensions/Dimension'):
        writer.field(dimension, 'Group', 'integer')
    write_model_extensions(writer, pattern)
    _internal_connections(writer, component)
