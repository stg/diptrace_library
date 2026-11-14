"""Modernize temporary footprint import records into owned library objects."""
from dataclasses import dataclass
from collections import ChainMap
from . import library_metadata
from .supplier_records import SUPPLIERS
from .dimension_refs import local_attachment, local_scopes
from .model import Element
from . import unplaced_footprint_records as records
from .footprint_text import normalize_text_style
from .unplaced_footprint_frame import normalize_frame
from .library_group_bounds import normalize as normalize_group


@dataclass
class FootprintInput:
    element: Element
    links: list
    unavailable: list
    attachments: list


def active_pad_indices(pattern):
    """Read the occupied interior slots; negative/unmatched selectors are inactive."""
    return [index for index, pad in enumerate(pattern.select('Pads/Pad')[1:-1], 1)
            if pad['Number_New'] == index]


def _missing(owner, template):
    for field in template.children():
        current = owner.child(field.kind)
        if current is None:
            owner.append(field.clone())
        elif field.kind in ('Model3D', 'Offset', 'Rotate', 'Zoom'):
            _missing(current, field)


def fill_defaults(pattern, *, pattern_defaults, pad_defaults):
    """Supply current facts absent from a serialization and consume its counts."""
    _missing(pattern, pattern_defaults)
    for pad in pattern.select('Pads/Pad'):
        _missing(pad, pad_defaults)
    if pattern['OriginCommon'] == 2:
        pattern.one('OriginCommon').set_values(1)
    for node in pattern._record_walk(include_self=True):
        if node.kind in ('PadMask_TopSegments', 'PadMask_BotSegments') and node.values:
            if node.values != (len(node.children('pt')),):
                raise ValueError('paste segment count does not match rows')
            node.set_values()
        if node.kind == 'Pattern_CategoryTypes':
            library_metadata.consume_count(node, library_metadata.CLASSIFICATIONS)
        if node.kind == 'PossibleNames':
            library_metadata.consume_count(node, library_metadata.POSSIBLE_NAMES)


def _drop_empty_supplier(pattern):
    supplier = pattern.child('Suppliers')
    if supplier is None:
        return
    supplier.bind_schema(SUPPLIERS)
    SUPPLIERS.validate_fields(supplier)
    prices = supplier.child('Prices')
    if (all(child.kind in SUPPLIERS.fields or child.kind == 'Prices' for child in supplier.children())
            and not any(supplier.get(name) for name in SUPPLIERS.fields)
            and (prices is None or not prices.values and not prices.children())):
        supplier.detach()


def normalize(pattern, *, pad_indices, shape_indices, hole_indices,
              establish_records, pattern_record=records.PATTERN):
    """Drop boundary slots and replace positional selections with identities."""
    pads = pattern.one('Pads').children('Pad')
    shapes = pattern.one('Shapes').children('Shape')
    holes = pattern.one('Holes').children('Hole')
    current_pads = {index: pads[index] for index in pad_indices}
    current_shapes = {index: shapes[index] for index in shape_indices}
    current_holes = {index: holes[index] for index in hole_indices}
    dimensions = pattern.select('Dimensions/Dimension')
    current_dimensions = {index: dimension for index,dimension in enumerate(dimensions) if dimension['Enabled']}
    groups = pattern.one('Pattern_Groups').children('pt')
    for group in groups:
        normalize_group(group)
    links, unavailable, missing_dimension_members = [], [], {}
    for collection, active, schema in ((pattern.one('Pads'), current_pads, records.PAD),
                                       (pattern.one('Shapes'), current_shapes, records.DRAWING),
                                       (pattern.one('Holes'), current_holes, records.HOLE),
                                       (pattern.one('Dimensions'), current_dimensions, records.DIMENSION)):
        kept = set(active.values())
        for node in list(collection.children()):
            if node not in kept:
                node.detach()
                continue
            if node.kind == 'Hole' and node.schema is None:
                values = node.arguments
                if len(values) != 7:
                    raise ValueError('expected the seven temporary hole values')
                node.set_values()
                for name, value in zip(('Enabled', 'Locked', 'X', 'Y', 'Diam', 'HoleDiam', 'Group'), values):
                    node.add(name, value)
            group = node.get('Group', -1)
            if group >= 0:
                if group >= len(groups):
                    raise ValueError('normalized group selection is outside its collection')
                links.append((node, groups[group], records.GROUP_ROLE))
            if (field := node.child('Group')) is not None:
                field.detach()
            if node.kind == 'Pad':
                node.one('Number_New').detach()
                if (key := node.child('Id')) is not None:
                    key.detach()
            if node.kind == 'Dimension':
                node.set_values()
            if node.kind == 'Shape':
                selected = node.get('PadId', -1)
                if selected >= 0:
                    if selected not in current_pads:
                        raise ValueError('normalized drawing pad selection is outside its collection')
                    links.append((node, current_pads[selected], records.PAD_ROLE))
                node.one('PadId').detach()
                lines = node.one('TextLine').children('pt')
                if node['Type'] != 7 and len(lines) == 1 and lines[0].values == ('',):
                    lines[0].detach()
            if (missing := node.child('UnresolvedKeys')) is not None:
                for item in missing.children('Key'):
                    name, key = item.values
                    if name == 'Group':
                        field, role, scope = 'UnresolvedGroupId', records.GROUP_ROLE, pattern.one('Pattern_Groups')
                    elif name == 'PadId' and node.kind == 'Shape':
                        field, role, scope = 'UnresolvedPadId', records.PAD_ROLE, pattern.one('Pads')
                    elif node.kind == 'Dimension' and name in ('SubObject1', 'SubObject2'):
                        node.one(name).set_values(key)
                        missing_dimension_members[node, name[-1]] = key
                        continue
                    else:
                        raise NotImplementedError(f'unresolved standalone pattern selector {name}')
                    node.add(field, key)
                    unavailable.append((node, role, key, scope))
                missing.detach()
            node.bind_schema(schema)
            if node.kind == 'Shape':
                normalize_text_style(node)
    _drop_empty_supplier(pattern)
    for connection in pattern.select('InternalConnections/IntCon'):
        keys = connection.values
        if len(keys) != 2:
            raise ValueError('internal connection requires two pad selections')
        explicit = connection.child('UnresolvedKeys')
        missing_keys = dict(item.values for item in explicit.children('Key')) if explicit is not None else {}
        connection.set_values()
        if explicit is not None:
            explicit.detach()
        for index, key, role in zip(('X', 'Y'), keys, records.CONNECTION_ROLES):
            key = missing_keys.get(index, key)
            if key < 0:
                continue
            if key in current_pads and index not in missing_keys:
                links.append((connection, current_pads[key], role))
            else:
                connection.add('Unresolved'+index, key)
                unavailable.append((connection, role, key, pattern.one('Pads')))
        connection.bind_schema(records.PAIR)
    if pattern.child('Sided') is None:
        pattern.add('Sided', False)
    pattern.bind_schema(pattern_record)
    establish_records(pattern)
    normalize_frame(pattern)
    objects = {0: current_pads, 1: current_shapes, 2: current_holes}
    attachments = []
    for dimension in current_dimensions.values():
        for side, role in zip(('1', '2'), records.DIMENSION_ROLES):
            scopes = objects
            if (key := missing_dimension_members.get((dimension, side))) is not None:
                mode = dimension['Connected'+side]
                if mode not in (0, 1, 2):
                    raise ValueError('unavailable public dimension member requires an object-key attachment')
                # The missing public key can equal a different object's compact
                # slot. Mask just this lookup until the graph owns its absence.
                scopes = {**objects, mode: ChainMap({key: None}, objects[mode])}
            attachment = local_attachment(dimension, side, scopes, offset=1)
            if attachment is not None:
                attachments.append((dimension, role, attachment, local_scopes(pattern, dimension, side, scopes)))
    return FootprintInput(pattern, links, unavailable, attachments)


def finish(document, inputs, *, establish_records, bind_additional=None):
    """Bind every adapter's imported identities through the same graph contract."""
    establish_records(document.root)
    if bind_additional is not None:
        bind_additional(document)
    for imported in inputs:
        for owner, target, role in imported.links:
            document.references.bind(owner, target, role=role)
        for owner, role, key, scope in imported.unavailable:
            document.references.note(owner, f'{role}: unavailable key {key}', collections=(scope,))
        for dimension, role, (target, indices, guards), scopes in imported.attachments:
            if target is None:
                document.references.note(dimension, role+': unavailable attachment', *indices,
                                         collections=scopes, guards=guards)
            else:
                for item in indices:
                    ancestor = target
                    for _ in range(item.ancestor):
                        ancestor = ancestor.parent
                    item.field.set_values(ancestor._ordinal()+item.offset)
                document.references.bind(dimension, target, *indices, role=role, guards=guards, preserve=True)
    document.validate()
    return document
