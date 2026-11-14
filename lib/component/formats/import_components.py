"""Modernize standalone serialization records into the owned component library.

The primary part supplies shared component descriptions. Secondary copies of
those serialized slots are inactive, as observable by selecting different parts
in the editor. Part values, simulation and symbol geometry remain independent.
"""
from ...common import footprint_objects, library_metadata, unplaced_footprint_records
from ...common import library_catalogue
from ...common.library_group_bounds import normalize as normalize_group
from ...common.unplaced_footprint_import import active_pad_indices, fill_defaults, normalize, finish
from ...common.unplaced_symbol_frame import normalize_frame as normalize_symbol_frame
from ...common.symbol_text_style import normalize_text_style
from ...common.structural_edits import assembly
from ..model import new_library, new_component, new_part
from ..model import records, symbols, text_fields
from ..model.metadata import SHARED_FIELDS, FOLDER_ROLE
from ..model.schema import establish_records


def _replace_collection(target, source, name):
    incoming = source.child(name)
    if incoming is not None:
        if (current := target.child(name)) is not None:
            current.detach()
        target.append(incoming.detach())


def _groups(raw, part):
    rows = raw.select('Groups/pt')
    mapping = {}
    for index, group in enumerate(rows):
        if group.values[0]:
            part.one('Groups').append(normalize_group(group.detach()))
            mapping[index] = group
        else:
            mapping[index] = None
    return mapping


def _selection(source, name, role, key, targets, collection, links, unavailable, *, unresolved=False):
    if key < 0 or name == 'PadId' and key == 0:
        return
    if not unresolved and key in targets:
        if targets[key] is not None:
            links.append((source, targets[key], role))
    else:
        source.add('Unresolved'+name, key)
        unavailable.append((source, role, key, collection))


def _missing_selections(source, fields):
    missing = source.child('UnresolvedKeys')
    if missing is None:
        return {}
    result = {}
    for row in missing.children('Key'):
        name, key = row.values
        if name not in fields or name in result:
            raise ValueError('unknown or duplicate unavailable symbol selection: '+name)
        result[name] = key
    missing.detach()
    return result


def _symbol(raw, component, pad_targets, links, unavailable):
    part = new_part(raw['PartName'])
    for name, definition in records.PART.fields.items():
        if definition.getter is None and (field := raw.child(name)) is not None:
            part.set(name, raw[name])
    _replace_collection(part, raw, 'ModelBody')
    groups = _groups(raw, part)
    for raw_pin in tuple(raw.select('Pins/Pin')):
        if not raw_pin['Enabled']:
            continue
        missing = _missing_selections(raw_pin, ('PadId', 'Group'))
        pad_key, group_key = missing.get('PadId', raw_pin['Number']), missing.get('Group', raw_pin['Group'])
        raw_pin.one('Number').detach()
        raw_pin.one('Group').detach()
        pin = part.one('Pins').append(raw_pin.detach().bind_schema(symbols.PIN))
        scope = component.child('Pattern')
        _selection(pin, 'PadId', symbols.PAD_ROLE, pad_key, pad_targets,
                   scope.one('Pads') if scope is not None else component, links, unavailable,
                   unresolved='PadId' in missing)
        _selection(pin, 'GroupId', symbols.GROUP_ROLE, group_key, groups,
                   part.one('Groups'), links, unavailable, unresolved='Group' in missing)
    for raw_shape in tuple(raw.select('Shapes/Shape')):
        if not raw_shape['Enabled']:
            continue
        missing = _missing_selections(raw_shape, ('Group',))
        group_key = missing.get('Group', raw_shape['Group'])
        for name in ('Group', 'ShowPart', 'MarkingGenerated', 'Name', 'Orientation'):
            if (field := raw_shape.child(name)) is not None:
                field.detach()
        shape = part.one('Shapes').append(raw_shape.detach().bind_schema(symbols.DRAWING))
        normalize_text_style(shape)
        _selection(shape, 'GroupId', symbols.GROUP_ROLE, group_key, groups,
                   part.one('Groups'), links, unavailable, unresolved='Group' in missing)
    normalize_symbol_frame(part)
    return part


def _physical(raw, component, defaults):
    pattern = raw.one('Pattern')
    pad_indices = active_pad_indices(pattern)
    shape_indices = [index for index, shape in enumerate(pattern.select('Shapes/Shape')) if shape['Type'] > 0]
    hole_indices = [index for index, hole in enumerate(pattern.select('Holes/Hole')) if hole.values[0]]
    meaningful = (pattern['Name'] or pad_indices or shape_indices or hole_indices
                  or pattern.select('Dimensions/Dimension') or pattern.select('UserFields/UserField')
                  or pattern.select('InternalConnections/IntCon') or pattern.one('Model3D').get('Model3DFile'))
    if not meaningful:
        return None, {}
    pattern.detach()
    fill_defaults(pattern, pattern_defaults=defaults[0], pad_defaults=defaults[1])
    pads = pattern.one('Pads').children('Pad')
    pad_targets = {index: pads[index] for index in pad_indices}
    imported = normalize(pattern, pad_indices=pad_indices, shape_indices=shape_indices,
                         hole_indices=hole_indices, establish_records=establish_records)
    component.append(pattern)
    return imported, pad_targets


def construct_library(incoming, *, name, hint):
    document = new_library(name, hint=hint)
    library = document.one('/Library')
    with assembly(document):
        for name in ('Categories', 'Subfolders'):
            _replace_collection(library, incoming, name)
    folders = library.one('Subfolders')
    folder_targets = dict(enumerate(folders.children('Folder')))
    physical_inputs, links, unavailable = [], [], []
    defaults = footprint_objects.new_pattern(), footprint_objects.new_pad()
    for raw in tuple(incoming.select('Components/Component')):
        raw_parts = tuple(raw.select('Parts/Part'))
        if not raw_parts:
            raise ValueError('component library entry has no parts')
        first = raw_parts[0]
        component = new_component(first['Name'], first['RefDes'])
        for name in SHARED_FIELDS:
            if name != 'SubfolderIndex' and first.child(name) is not None:
                component[name] = first[name]
        _selection(component, 'SubfolderIndex', FOLDER_ROLE, first.get('SubfolderIndex', -1),
                   folder_targets, folders, links, unavailable)
        for name in ('UserFields', 'Suppliers', 'Component_CategoryTypes'):
            _replace_collection(component, first, name)
        classes = component.one('Component_CategoryTypes')
        library_metadata.consume_count(classes, library_metadata.CLASSIFICATIONS)
        component.one('Parts/Part').detach()
        imported, pad_targets = _physical(first, component, defaults)
        if imported is not None:
            physical_inputs.append(imported)
        for raw_part in raw_parts:
            component.one('Parts').append(_symbol(raw_part, component, pad_targets, links, unavailable))
        # Import assembles known records before one final schema/reference audit.
        # Ordinary authoring attachments keep their immediate atomic checks.
        with assembly(document):
            library.one('Components').append(component)
    def bind_additional(document):
        for owner, target, role in links:
            document.references.bind(owner, target, role=role)
        for owner, role, key, scope in unavailable:
            document.references.note(owner, f'{role}: unavailable key {key}', collections=(scope,))
        text_fields.bind_imported(document)
        library_catalogue.bind_imported(document)

    return finish(document, physical_inputs, establish_records=establish_records,
                  bind_additional=bind_additional)
