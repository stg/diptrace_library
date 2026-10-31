"""Copper-layer identity and supplied material-stack data from public XML."""
from decimal import Decimal

from ....common.xml_records import enum_value, length
from .keys import position, unique_id


def read_layers(record, board, *, units):
    collection, by_key = board.add('Layers'), {}
    for source in record.rows('CopperLayers', 'Lay'):
        key = unique_id(source, by_key, label='copper layer')
        layer = collection.add('Layer', source.text('Name', ''))
        by_key[key] = layer
        layer.add('Number', key)
        layer.add('Enabled', source.boolean('Enabled', True))
        layer.add('Locked', source.boolean('Locked', False))
        layer.add('Color', source.integer('Color', 0))
        layer.add('Type', enum_value(source.value('Type', 'Signal'), ('Signal', 'Plane')))
        layer.add('HoleType', enum_value(source.value('PlanePad', 'By Pads'), ('By Pads', 'Fixed Ring')))
        layer.add('HoleRing', length(source.number('PlaneRing'), units) if source.has('PlaneRing') else Decimal('0.6'))
        layer.add('NetNumber', source.integer('NetId', -1))
        source.finish()
    return by_key


def read_stack(record, board, *, layers, units):
    board.add('LayerStackName', record.text('LayerStackName', ''))
    target = board.add('LayerStackItems')
    for index, source in enumerate(record.rows('LayerStackItems', 'LayerStackItem')):
        row = target.add('LayerStackItem', index)
        row.add('Lay', position(source.integer('Lay', -1), layers,
                               label='stack copper layer', path=source.node.path))
        material = source.take('Material', required=True)
        output = row.add('Material')
        output.add('Name', material.text('Name', ''))
        output.add('Type', enum_value(material.value('Type', 'Dielectric'), ('Conductor', 'Plane', 'Dielectric')))
        output.add('VariableThickness', material.boolean('VariableThickness', False))
        for name in ('Thickness', 'TraceWidth'):
            output.add(name, length(material.number(name, 0), units))
        output.add('Constant', material.number('Constant', 0))
        material.finish()
        source.finish()
