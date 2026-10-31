"""Placed component data over owned physical footprint definitions."""
from dataclasses import dataclass

from ....common.model import Element
from ....common.xml_records import enum_value, point, length, replace_rows
from ....common.xml_font_import import read_size
from ....common.xml_library_values import read_path, read_category
from ....common.xml_footprint_vocabulary import HORZ, VERT
from ...model import markings
from ..errors import PcbError
from .pad_options import read_pad_options
from .patterns import PCB_PATTERN_TYPES
from .hierarchy import read_path as read_hierarchy_path
from .internal_connections import read_connections
from .assembly_variants import read_exclusions


SHOW = ('Common', 'Show', 'Hide')
ALIGN = ('Common', 'Center', 'Top', 'Bottom', 'Left', 'Right', 'Corner', 'Auto', 'Position')


@dataclass(frozen=True)
class PlacedInput:
    component: Element
    pad_positions: dict
    shape_positions: dict
    hole_positions: dict


def _marking(record, target, prefix, *, units):
    for side in markings.SIDES:
        source = record.take(side) if record is not None else None
        stem = prefix+'_'+side if prefix else side
        for name, labels in (('Show', SHOW), ('Align', ALIGN), ('Horz', HORZ), ('Vert', VERT)):
            value = enum_value(source.value(name, labels[0]), labels,
                negative=labels[-1] if name in ('Horz', 'Vert') else None) if source is not None else 0
            target.add(stem+name, value)
        coordinates = point(source, units, default=0) if source is not None else (0, 0)
        for name, value in zip(('X', 'Y'), coordinates):
            target.add(stem+name, value)
        target.add(stem+'Angle', source.number('Angle', 0) if source is not None else 0)
        if source is not None:
            source.finish()
    if record is not None:
        record.finish()


def read_component(record, *, patterns, units, vias=None, layers=None, common_fiducials=True):
    via_key = record.integer('ViaStyle', -1)
    if via_key >= 0 and (vias is None or via_key not in vias):
        raise PcbError(f'{record.node.path}: unresolved via style {via_key}')
    key = record.text('PatternStyle', '')
    if key:
        if key not in patterns:
            raise PcbError(f'{record.node.path}: unresolved footprint style {key!r}')
        definition = patterns[key]
    elif enum_value(record.value('Type', 'Free'), PCB_PATTERN_TYPES) == 16 and via_key >= 0:
        from .vias import implicit_via_pattern
        definition = implicit_via_pattern(vias[via_key])
    else:
        raise PcbError(f'{record.node.path}: component geometry requires a footprint style')
    component = Element('Component', record.text('Name', ''), record.text('RefDes', ''))
    component.add('Enabled', True)
    component.add('Number', record.integer('Id'))
    component.add('HiddenId', record.integer('UpdateId', -1))
    for axis, value in zip(('X', 'Y'), point(record, units, default=0)):
        component.add(axis, value)
    component.add('Angle', record.number('Angle', 0))
    side = enum_value(record.value('Side', 'Top'), ('Top', 'Bottom'))
    if side not in (0, 1):
        raise PcbError(f'{record.node.path}: unsupported component side')
    component.add('BottomSide', side == 1)
    component.add('Flipped', record.boolean('Flip', False))
    component.add('HorizontalFlip', record.boolean('HorzFlip', False))
    for name in ('Selected', 'Locked', 'PanelExclude', 'CustomMarkingFont', 'MarkingFontAll'):
        component.add(name, record.boolean(name, False))
    component.add('MarkingFontSize', read_size(record, 'MarkingFontSize', 5, floating='MarkingFontSizeFloat'))
    component.add('GsType', enum_value(record.value('GridAlign', 'Origin'), ('Pad', 'Origin')))
    component.add('ShowFiducial', enum_value(record.value('ShowFiducials', 'Common'), SHOW))
    component.add('Group', record.integer('Group', -1))
    component.add('ShieldGroup', record.integer('ShieldGroup', -1))
    component.add('ViaStyle', vias[via_key]._ordinal() if via_key >= 0 else -1)
    component.add('PlacementClearance', length(record.number('PlacementClearance'), units)
                  if record.has('PlacementClearance') else -1)
    for name in ('Value', 'Manufacturer', 'Datasheet'):
        component.add(name, record.text(name, definition.defaults.get(name, '')))
    path = record.take('LibPath')
    actual, variable = read_path(path) if path is not None else ('', '')
    component.add('LibPath', actual)
    component.add('LibPath_Variable', variable)
    component.add('BaseName', definition.element['Name'])
    component.add('ConnectedLayer', -1)
    read_hierarchy_path(record.take('HierarchyPath'), component)
    component.add('Component_CategoryName', '')
    component.add('Component_CategoryIndex', -1)
    component.add('Component_CategoryTypes')
    read_category(record.take('Category'), component)
    for name in markings.NAMES:
        _marking(record.take(name+'Marking'), component, name, units=units)
    fields = component.add('UserFields')
    for item in record.rows('AddFields', 'AddField'):
        field = fields.add('UserField', item.text('Name', ''), item.text('Text', ''),
                           enum_value(item.value('Type', 'Text'), ('Text', 'Link')))
        _marking(item, field, '', units=units)

    pattern = component.append(definition.element.clone())
    # Template fields belong to the cached library definition. The placed
    # component's AddFields above owns its current fields and marking settings.
    # A geometry copy must not manufacture a second independent field list.
    for field in tuple(pattern.one('UserFields').children()):
        field.detach()
    # Local groups belong to the footprint definition. Placement transfers the
    # physical objects without creating another editable group namespace.
    if (groups := pattern.child('Pattern_Groups')) is not None:
        groups.detach()
    # These shared constructor collections do not describe placed content when
    # empty. Authored placed pad pairs are owned by Component.IntConRecords.
    for name in ('InternalConnections', 'UserFields'):
        branch = pattern.child(name)
        if branch is not None and not branch.arguments and not branch.children():
            branch.detach()
    # Construction installs the physical template frame before placement data.
    # The cached definition and incoming component coordinates stay independent.
    from ..placement_frames import install_definition_frame
    install_definition_frame(pattern, common_fiducials=common_fiducials)
    if record.has('Type'):
        pattern['Type'] = enum_value(record.value('Type'), PCB_PATTERN_TYPES)
    inferred = []
    if pattern['Type'] == 16:
        from .vias import read_via_pads
        pad_ids = read_via_pads(record, pattern, units=units, layers=layers)
    else:
        pad_ids = definition.pad_ids
        pads = pattern.one('Pads').children('Pad')
        for pad in pads:
            pad.add('NetNumber', -1)
            pad.add('InternalConnection', -1)
        seen = set()
        for source in record.rows('Pads', 'Pad'):
            key = source.integer('Id')
            if key not in pad_ids or key in seen:
                raise PcbError(f'{source.node.path}: missing or duplicate placed pad {key}')
            seen.add(key)
            pad = pads[pad_ids[key]]
            pad.one('NetNumber').set_values(source.integer('NetId', -1))
            pad.one('InternalConnection').set_values(source.integer('InternalConnection', -1))
            if not source.has('DefStyle'):
                inferred.append(pad)
            read_pad_options(source, pad, units=units, layers=layers)
            source.finish()
    read_connections(record, component, pad_positions=pad_ids)
    read_exclusions(record, component)
    record.finish()
    from ..standalone_objects import normalize_component
    normalize_component(component)
    from .placement_frame import install_geometry
    install_geometry(component)
    from .pad_defaults import infer_defaults
    infer_defaults(component, inferred)
    return PlacedInput(component, pad_ids, definition.shape_ids, definition.hole_ids)
