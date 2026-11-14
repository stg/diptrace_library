"""Standalone XML physical definitions shared by library-family writers."""
from .conversion import warn
from .font_codec import compatibility_size
from .xml import set_attribute
from .xml_footprint_output import project_drawing, project_dimension, project_model3d
from .xml_footprint_vocabulary import PATTERN_TYPES
from .xml_library_output import project_library_supplier
from .library_output_keys import PhysicalKeys
from .xml_output import enum_text, field, numeric, point_attributes
from .xml_pad_output import plan_pad_style
from .xml_pattern_metadata import project_pattern_header, project_pattern_user_fields
from .xml_plan import XmlBuilder
from .library_group_bounds import coordinates as group_coordinates


def _adapt(pattern, profile, destination, report):
    if any(pattern[name] for name in pattern.schema.fields if name.startswith('VariableParameter')):
        warn(report, 'pattern-parameter-options', destination,
             'XML omits footprint parameter-enable choices', (pattern,))
    if not profile.drawing_pad_links:
        linked = [shape for shape in pattern.select('Shapes/Shape') if shape['PadId'] >= 0]
        if linked:
            warn(report, 'drawing-pad-reference', destination,
                 'Destination omits drawing-to-pad associations', linked)
    for shape in pattern.select('Shapes/Shape'):
        if shape['Type'] != 7 and shape.select('TextLine/pt'):
            warn(report, 'non-text-drawing-content', destination,
                 'XML omits text attached to a non-text drawing', (shape,))
    if not profile.current_fields:
        for owner in (*pattern.select('Shapes/Shape'), *pattern.select('Dimensions/Dimension')):
            size = owner['FontSize']
            rounded = compatibility_size(size)
            if size != rounded:
                owner['FontSize'] = rounded
                warn(report, 'fractional-font-size', destination,
                     'Destination font sizes are rounded to integral values', (owner,))
            if owner.get('FontMono', False):
                owner['FontMono'] = False
                warn(report, 'monospaced-font', destination,
                     'Destination omits monospaced vector-font selection', (owner,))


def project_pattern(pattern, *, styles, units, profile, destination, report, keys=None, text_layout=None):
    _adapt(pattern, profile, destination, report)
    keys = keys if keys is not None else PhysicalKeys(pattern, destination=destination, report=report)
    target = XmlBuilder('Pattern')
    project_pattern_header(pattern, target, units=units,
                           type_label=enum_text(pattern['Type'], PATTERN_TYPES),
                           include_empty_templates=True)
    if not profile.current_fields and not any(child.kind == 'Category' for child in target.children):
        set_attribute(target.add('Category'), 'Index', pattern['Pattern_CategoryIndex'])
    groups = pattern.select('Pattern_Groups/pt')
    if groups:
        layout = text_layout if text_layout is not None else profile.text_layout()
        target_groups = target.add('Groups')
        for group in groups:
            if not group['Enabled']:
                continue
            row = target_groups.add('Group')
            if profile.current_fields:
                set_attribute(row, 'Enabled', True)
            set_attribute(row, 'Id', keys.groups.key(group))
            point_attributes(row, *group_coordinates(group, layout=layout), units)
    project_pattern_user_fields(pattern, target)
    project_library_supplier(pattern.child('Suppliers'), target, destination=destination, report=report)
    default = styles.include_plan(plan_pad_style(pattern, name='', units=units))
    set_attribute(target.add('DefPad'), 'Style', default)
    pads = target.add('Pads')
    for pad in pattern.select('Pads/Pad'):
        row = pads.add('Pad')
        set_attribute(row, 'Id', keys.pad(pad))
        excluded = (default,) if not profile.current_fields and not pad['Standard'] else ()
        style = styles.include_plan(plan_pad_style(pad, name='', units=units), exclude=excluded)
        set_attribute(row, 'Style', style)
        for name, value in (('Angle', pad['PadAngle']), ('Locked', pad['Locked']),
                            ('Side', 'Bottom' if pad['Sided'] else 'Top')):
            set_attribute(row, name, value)
        if profile.current_fields:
            set_attribute(row, 'DefStyle', pad['Standard'])
        point_attributes(row, pad['X'], pad['Y'], units)
        if (group := keys.groups.selection(pad)) >= 0:
            set_attribute(row, 'Group', group)
        field(row, 'Number', pad['StringNumber'])
        if pad['Name']:
            field(row, 'Note', pad['Name'])
    shapes = target.add('Shapes')
    for shape in pattern.select('Shapes/Shape'):
        if shape['Type'] <= 0:
            raise ValueError(f'{shape.path}: inactive drawing cannot be exported')
        shapes.append(project_drawing(shape, index=keys.shape(shape), units=units, group=keys.groups.selection(shape),
            pad_id=keys.pad_selection(shape) if profile.drawing_pad_links else -1,
            fractional_font=profile.current_fields,
            physical_font_width=profile.physical_font_width, _factory=XmlBuilder))
    holes = target.add('Holes')
    for hole in pattern.select('Holes/Hole'):
        if not hole['Enabled']:
            raise ValueError(f'{hole.path}: inactive hole cannot be exported')
        row = holes.add('Hole')
        set_attribute(row, 'Id', keys.hole(hole))
        set_attribute(row, 'Locked', hole['Locked'])
        point_attributes(row, hole['X'], hole['Y'], units)
        for name in ('Diam', 'HoleDiam'):
            set_attribute(row, name, numeric(units.length(hole[name])))
        if (group := keys.groups.selection(hole)) >= 0:
            set_attribute(row, 'Group', group)
    dimensions = target.add('Dimensions')
    for dimension in pattern.select('Dimensions/Dimension'):
        if not dimension['Enabled']:
            raise ValueError(f'{dimension.path}: inactive dimension cannot be exported')
        attachments = keys.attachments(dimension)
        dimensions.append(project_dimension(dimension, units=units, attachments=attachments,
            group=keys.groups.selection(dimension), fractional_font=profile.current_fields,
            physical_font_width=profile.physical_font_width, _factory=XmlBuilder))
    target.append(project_model3d(pattern.one('Model3D'), units=units,
                                   variable_fallback=False, _factory=XmlBuilder))
    return target.freeze()
