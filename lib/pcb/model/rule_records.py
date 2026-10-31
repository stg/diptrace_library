"""Routing and design-rule records with explicit layer and class identities.

Uniform properties have no copper-layer target. Layer-specific properties refer
to the layer itself, so collection positions never determine their meaning.
Class-pair clearances are flat records rather than an asymmetric saved matrix.
"""
from ...common.schema import Child, Field, Record
from .relationships import reference_field, index_field, linked


def lengths(names, *, default=-1):
    return {name: Field(name, 'number', default=default, unit='shared length') for name in names.split()}


LAYER_FIELDS = {'Layer': reference_field('Layer', 'copper-layer'),
                'Lay': index_field('Lay', 'copper-layer')}


def _layer_name(node):
    layer = linked(node, 'copper-layer')
    return layer['Name'] if layer is not None else ''


LAYER_NAME = Field('LayerName', 'text', getter=_layer_name,
    reference_dependencies=lambda node: ((node, 'copper-layer', 'outgoing'),),
    value_dependencies=lambda node: ((layer, 'Name'),) if (layer := linked(node, 'copper-layer')) is not None else ())

CLEARANCE_KINDS = ('Trace', 'Via', 'Pad', 'Smd', 'Copper', 'Drill', 'Board')
CLASS_CLEARANCE_NAMES = tuple(CLEARANCE_KINDS[first]+'To'+CLEARANCE_KINDS[second]
                              for first in range(4) for second in range(first, 5))
DRC_CLEARANCE_NAMES = tuple(CLEARANCE_KINDS[first]+'To'+CLEARANCE_KINDS[second]
                            for first in range(6) for second in range(first, 7))
CLASS_DETAILS = Record('PcbClassClearanceDetails', lengths(' '.join(CLASS_CLEARANCE_NAMES)))
DRC_DETAILS = Record('PcbDrcClearanceDetails', lengths(' '.join(DRC_CLEARANCE_NAMES)))
LAYER_PROPERTY = Record('PcbClassLayerProperty', {
    **LAYER_FIELDS, 'LayerName': LAYER_NAME,
    **lengths('Width MinWidth MaxWidth Clearance DifClearance Neck_Width Neck_DifClearance Neck_MaxLength'),
}, children={'ClearanceDetails': Child('ClearanceDetails', CLASS_DETAILS.name)})
ALLOWED_VIA = Record('PcbAllowedVia', {
    'Via': reference_field('Via', 'via-style'), 'Id': index_field('Id', 'via-style'),
})
ROUTE_LAYER = Record('PcbRouteLayer', {**LAYER_FIELDS,
    'Enabled': Field('Enabled', 'boolean', default=True),
})
LAYER_CLEARANCE = Record('PcbLayerClearance', {**LAYER_FIELDS,
    'Clearance': Field('Clearance', 'number', nullable=True, default=None, unit='shared length'),
})
CLASS_CELL = Record('PcbClassClearance', {
    'Class1': reference_field('Class1', 'net-class-1'),
    'Class2': reference_field('Class2', 'net-class-2'),
    'NetClass1': index_field('NetClass1', 'net-class-1'),
    'NetClass2': index_field('NetClass2', 'net-class-2'),
    'AllLayers': Field('AllLayers', 'boolean', default=True),
    'Clearance': Field('Clearance', 'number', nullable=True, default=None, unit='shared length'),
}, children={'LayerClearances': Child('LayerClearances', 'PcbLayerClearances')})
DRC_CLEARANCE = Record('PcbDrcLayerClearance', {**LAYER_FIELDS,
    **lengths('SameTraceToTrace SameSmdToVia SameSmdToPad SameSmdToSmd'),
}, children={'ClearanceDetails': Child('ClearanceDetails', DRC_DETAILS.name)})
DRC_SIZE = Record('PcbDrcLayerSize', {**LAYER_FIELDS,
    **lengths('MinTrace MinDrill MinRing MaxRing MaxPlatedHole MaxNonPlatedHole'),
})
DRC = Record('PcbDesignRules', {
    'Name': Field('Name', 'text', default=''),
    **{name: Field(name, 'boolean', default=False) for name in
       ('CheckClearance', 'CheckSize', 'CheckJumpers', 'CheckCopperPours', 'CheckClassToClass',
        'CheckSilk', 'CheckLength', 'AllLayers', 'ShowList', 'CheckKeepouts', 'CheckSameNet',
        'CheckSameComponentPads', 'CheckCourtyard', 'DRCDone')},
    'RealTimeMode': Field('RealTimeMode', 'integer', default=0),
    **lengths('SilkClearance', default=0),
}, children={'LayClearances': Child('LayClearances', 'PcbDrcLayerClearances'),
             'LaySizes': Child('LaySizes', 'PcbDrcLayerSizes')})


def collection(name, kind, record):
    return Record(name, {}, children={kind: Child(kind, record.name, maximum=None)})


COLLECTIONS = {
    'LayProperties': collection('PcbClassLayerProperties', 'LayProperty', LAYER_PROPERTY),
    'AllowedVias': collection('PcbAllowedVias', 'ViaStyle', ALLOWED_VIA),
    'RouteLayers': collection('PcbRouteLayers', 'Item', ROUTE_LAYER),
    'ClassClearances': collection('PcbClassClearances', 'Cell', CLASS_CELL),
    'LayerClearances': collection('PcbLayerClearances', 'LayerClearance', LAYER_CLEARANCE),
    'LayClearances': collection('PcbDrcLayerClearances', 'LayClearance', DRC_CLEARANCE),
    'LaySizes': collection('PcbDrcLayerSizes', 'LaySize', DRC_SIZE),
}


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if parent.kind == 'Settings' and node.kind == 'Routing':
        from .routing_defaults import ROUTING
        return ROUTING
    if parent.kind == 'Board' and node.kind in ('DRC', 'LastDRC'):
        return DRC
    if node.kind in COLLECTIONS:
        owners = {'LayProperties': ('NetClass',), 'AllowedVias': ('NetClass',),
                  'RouteLayers': ('NetClass',), 'ClassClearances': ('Board',),
                  'LayerClearances': ('Cell',), 'LayClearances': ('DRC', 'LastDRC'),
                  'LaySizes': ('DRC', 'LastDRC')}
        if parent.kind in owners[node.kind]:
            return COLLECTIONS[node.kind]
    found = {('LayProperties', 'LayProperty'): LAYER_PROPERTY,
             ('AllowedVias', 'ViaStyle'): ALLOWED_VIA, ('RouteLayers', 'Item'): ROUTE_LAYER,
             ('ClassClearances', 'Cell'): CLASS_CELL, ('LayerClearances', 'LayerClearance'): LAYER_CLEARANCE,
             ('LayClearances', 'LayClearance'): DRC_CLEARANCE, ('LaySizes', 'LaySize'): DRC_SIZE}.get(
                 (parent.kind, node.kind))
    if found is not None:
        return found
    if node.kind == 'ClearanceDetails':
        return CLASS_DETAILS if parent.kind == 'LayProperty' else DRC_DETAILS if parent.kind == 'LayClearance' else None
    return None
