"""Placed-pad layer overrides and teardrop settings."""
from ...common.schema import Child, Field, Record
from ...common.references import ReferenceError
from .relationships import reference_field, index_field


LAYER_FIELDS = {'Layer': reference_field('Layer', 'copper-layer'),
                'Lay': index_field('Lay', 'copper-layer')}
LAYER_MEMBER = Record('PcbPadLayer', LAYER_FIELDS, parameters=('Lay',))
THERMAL = Record('PcbPadThermal', {**LAYER_FIELDS,
    'Type': Field('Type', 'integer', default=0),
    'Spoke': Field('Spoke', 'integer', default=0),
    'Width': Field('Width', 'number', default=0, unit='shared length'),
}, parameters=('Lay', 'Type', 'Spoke', 'Width'))
TEARDROP = Record('TeardropParameters', {
    **{name: Field(name, 'integer', default=0) for name in ('PadVia', 'Smd', 'Trace', 'TJunc')},
    **{name: Field(name, 'number', default=0) for name in
       ('PadViaWidth', 'PadViaLength', 'SmdWidth', 'SmdLength', 'TraceLength', 'TJuncLength')},
})
COLLECTIONS = {
    'HideLayer': Record('HiddenPadLayers', {}, children={'Item': Child('Item', LAYER_MEMBER.name, maximum=None)}),
    'BlindLayer': Record('BlindPadLayers', {}, children={'Item': Child('Item', LAYER_MEMBER.name, maximum=None)}),
    'CustomSpokes': Record('PadThermals', {}, children={'CustomSpoke': Child('CustomSpoke', THERMAL.name, maximum=None)}),
}


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'TeardropParams' and parent.kind in ('Pad', 'Net'):
        return TEARDROP
    if parent.kind == 'Pad':
        return COLLECTIONS.get(node.kind)
    owner = parent.parent
    if owner is not None and owner.kind == 'Pad':
        if parent.kind in ('HideLayer', 'BlindLayer') and node.kind == 'Item':
            return LAYER_MEMBER
        if parent.kind == 'CustomSpokes' and node.kind == 'CustomSpoke':
            return THERMAL
    return None


def validate_reference(document, reference, target):
    if reference.role != 'copper-layer' or reference.source.schema not in (LAYER_MEMBER, THERMAL):
        return
    source = reference.source
    if source.parent is None or source.parent.parent is None or source.parent.parent.kind != 'Pad':
        raise ReferenceError('pad layer settings require an owning pad')
    for candidate in document.references.incoming(target, role='copper-layer'):
        if candidate.source is not source and candidate.source.parent is source.parent:
            raise ReferenceError('pad layer settings already contain this layer')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)
