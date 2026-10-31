"""Expand PCB ASC components into the model's owned footprint vocabulary.

This is an import stage, before identity binding. Saved component/pad keys and
boundary rows are consumed by the remaining assembly; they are not model facts.
"""
from contextlib import nullcontext

from ....common.asc_text import raw_token
from ....common.structural_edits import assembly
from ....common.model import Value
from ....common import footprint_records
from ....common.asc_footprints import unpack_model, unpack_terminals, unpack_pattern_shapes
from ....common.library_metadata import CLASSIFICATIONS, consume_count, modernize_classifications
from ....common.supplier_records import SUPPLIERS
from ...model.definitions import COMPONENT, PATTERN_SHAPE
from ...model.connection_policies import POLICY
from .values import boolean as _boolean, rename as _rename, numeric_row
from .teardrops import unpack_parameters as unpack_teardrop_parameters
from .vocabulary import PAD_FIELD_NAMES


_PATTERN_FIELDS = (footprint_records.PATTERN.fields.keys() |
                   footprint_records.PATTERN.children.keys()) - {
    'Name', 'RefDes', 'Datasheet', 'Sided', 'UserFields', 'InternalConnections'}
_BOOLEANS = {name for schema in (COMPONENT, footprint_records.PATTERN,
                                footprint_records.PAD, footprint_records.MODEL3D, PATTERN_SHAPE, POLICY, SUPPLIERS)
             for name, field in schema.fields.items() if field.kind == 'boolean'}

def _counted_rows(owner, name, *, kind='pt', target=None):
    container = owner.child(name)
    if container is None:
        return
    rows = container.children(kind)
    if (container.values != (len(rows),) or
            len(rows) != len(container.children())):
        raise ValueError(f'{container.path}: count does not match records')
    container.set_values()
    if target is not None:
        container.kind = target
    for row in rows:
        row.kind = 'Item'


def _pad(pad):
    if len(pad.arguments) != 5:
        raise ValueError(f'{pad.path}: expected five pad header values')
    _rename(pad, PAD_FIELD_NAMES)
    unpack_terminals(pad, container='PadTerminals', counted=False)
    for name in ('HideLayer', 'BlindLayer'):
        if (layers := pad.child(name)) is not None:
            if layers.arguments:
                raise ValueError(f'{layers.path}: expected pad-layer rows')
            for row in layers.children():
                numeric_row(row, 1, integers=(0,))
                row.kind = 'Item'
    for thermal in pad.select('CustomSpokes/CustomSpoke'):
        if thermal.arguments or {node.kind for node in thermal.children()} != {'Layer', 'Type', 'Spoke', 'Width'}:
            raise ValueError(f'{thermal.path}: expected named pad thermal settings')
        values = []
        for name in ('Layer', 'Type', 'Spoke', 'Width'):
            field = thermal.one(name)
            values.extend(numeric_row(field, 1, kind=name, integers=(0,) if name != 'Width' else ()))
            field.detach()
        thermal.set_values(*values)
    unpack_teardrop_parameters(pad)


def unpack_component(component):
    """Consume one owned syntax record; return it with named footprint ownership.

    Coordinates already use shared length units and angles are unquantized
    radians. The input is adapter-owned, not a caller's editable document.
    """
    owner = component._owner()
    if component.schema is not None or owner is not None and owner.representation != 'asc':
        raise TypeError('component expansion requires unbound ASC adapter input')
    with assembly(owner) if owner is not None else nullcontext():
        return _unpack_component(component)


def _unpack_component(component):
    if component.kind != 'Component' or not 1 <= len(component.arguments) <= 2:
        raise ValueError('expected a PCB ASC component with name and RefDes')
    # ASC writes the RefDes as an unquoted token and writes nothing for an
    # empty one. Interpret these declared text positions before discarding
    # lexical spelling: 003 and 3 must remain different authored labels.
    values = []
    for index, value in enumerate(component.arguments):
        # The receiver treats this header's RefDes as a raw token. Quote marks
        # at this position are literal name characters, unlike Component.Name.
        if index == 1:
            text = raw_token(value)
        else:
            text = value.value if isinstance(value.value, str) else value.lexeme or str(value.value)
        values.append(Value(text, 'string', source=value.source))
    component.set_values(*values, *([''] if len(values) == 1 else []))
    pattern = component.one('Pattern')
    if len(pattern.arguments) != 1 or pattern.children():
        raise ValueError(f'{pattern.path}: expected a scalar footprint name')
    for node in tuple(component.children()):
        if node.kind in _PATTERN_FIELDS:
            if pattern.child(node.kind) is not None:
                raise ValueError(f'{component.path}: duplicate footprint field {node.kind}')
            node.move_to(pattern)
    for owner, name in ((component, 'Component_CategoryTypes'), (pattern, 'Pattern_CategoryTypes')):
        if (classifications := owner.child(name)) is not None:
            modernize_classifications(classifications)
            consume_count(classifications, CLASSIFICATIONS)
    terminals = component.one('PadTerminals')
    terminals.move_to(pattern)
    unpack_terminals(pattern, container='PadTerminals', counted=False)
    if (points := pattern.child('PadPoints')) is not None:
        if points.arguments:
            raise ValueError(f'{points.path}: expected default pad-contour rows')
        for row in points.children():
            # PCB ASC spells these coordinate rows Type, in contrast to an
            # individual pad's pt rows. Both become ordinary XY model points.
            if row.kind == 'Type':
                row.kind = 'pt'
            numeric_row(row, 2)
    for pad in pattern.one('Pads').children('Pad'):
        _pad(pad)
    shapes = pattern.one('Shapes')
    unpack_pattern_shapes(shapes, pad_id=False, points_name='Points',
                          header_fields=(('Layer', 2), ('TextAngle', 15)))
    for shape in shapes.children('Shape'):
        _rename(shape, {'Marking_Generated': 'MarkingGenerated'})
    for hole in pattern.select('Holes/Hole'):
        if len(hole.arguments) != 7:
            raise ValueError(f'{hole.path}: expected seven hole values')
        hole.set_values(*(_boolean(value, hole.path) if i < 2 else value
                          for i, value in enumerate(hole.arguments)))
    model = pattern.one('Model3D')
    _rename(model, {'IPC_X': 'IPC_XOff', 'IPC_Y': 'IPC_YOff', 'ModelType': 'Type'})
    unpack_model(model, fields=('Mirror', 'NoSearch', 'Units'))
    _counted_rows(component, 'Hidden_Path', target='HierarchyPath')
    _counted_rows(component, 'AssemblyExclude')
    for group in component.select('InternalConnections/IntCon'):
        _rename(group, {'PadNum': 'PadId'})
        for collection in ('PadId', 'Line'):
            container = group.one(collection)
            for row in container.children():
                if row.kind != 'pt':
                    raise ValueError(f'{row.path}: expected internal connection row')
                row.kind = 'Item'
    for node in component.walk():
        if node.kind in _BOOLEANS and len(node.arguments) == 1 and not node.children():
            node.set_values(_boolean(node.arguments[0], node.path))
    return component
