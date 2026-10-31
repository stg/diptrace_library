"""Public net-class rules and permissions, before identity assembly."""
from decimal import Decimal

from ....common.model import Element
from ....common.xml_records import enum_value, length
from ...model.rule_records import LAYER_PROPERTY, CLASS_CLEARANCE_NAMES
from ...model.length_matching import DEFAULT_FIXED_LENGTH, DEFAULT_DELTA
from ..errors import PcbError
from .keys import position, unique_id


CLASS_FLAGS = dict(AllLayers=True, AllVias=True, CheckLength=False, PerformDRC=False)
CLASS_LENGTHS = dict(Phase=6, Phase_ErrorLength=15, LengthDelta=DEFAULT_DELTA,
                     FixedLength=DEFAULT_FIXED_LENGTH, MaxUncoupledLength=30, Tolerance=6)
ROUTE_FLAGS = dict(RoutePriority=False, RouteMaxVias=False,
                   RouteMaxIncorrectWay=False, RouteAllLayers=True)


def _properties(record, target, *, layers, uniform, units):
    rows = []
    for source in record.rows('LayProperties', 'LayProperty'):
        row = Element('LayProperty')
        name = source.text('LayerName', '')
        for field, definition in LAYER_PROPERTY.fields.items():
            if definition.getter is not None:
                continue
            default = {'MinWidth': Decimal('.03'), 'MaxWidth': 300}.get(field, -1)
            value = length(source.number(field), units) if source.has(field) else default
            row.add(field, value)
        details = source.take('ClearanceDetails')
        if details is not None:
            output = row.add('ClearanceDetails')
            for field in CLASS_CLEARANCE_NAMES:
                output.add(field, length(details.number(field), units) if details.has(field) else -1)
            details.finish()
        source.finish()
        rows.append((name, row))
    if not uniform:
        by_name = {}
        for name, row in rows:
            if name in by_name:
                raise PcbError(f'{record.node.path}: duplicate class layer name {name!r}')
            by_name[name] = row
        names = [layer.values[0] for layer in layers.values()]
        if len(set(names)) != len(names) or set(by_name) != set(names):
            raise PcbError(f'{record.node.path}: class properties require one row per named copper layer')
        rows = [(name, by_name[name]) for name in names]
    collection = target.add('LayProperties')
    for _name, row in rows:
        collection.append(row)


def _autorouting(record, target, *, layers):
    for name, default in ROUTE_FLAGS.items():
        target.add(name, record.boolean(name, default) if record is not None else default)
    for name, default in (('PriorityValue', 1), ('MaxViasValue', 10000)):
        target.add(name, record.integer(name, default) if record is not None else default)
    target.add('MaxIncorrectWayValue', record.number('MaxIncorrectWayValue', 30000)
               if record is not None else 30000)
    routes = target.add('RouteLayers')
    if record is not None:
        for source in record.rows('RouteLayers', 'Item'):
            value = source.content().value
            if value not in ('Y', 'N'):
                raise PcbError(f'{source.node.path}: expected Y or N for a routing layer')
            routes.add('Item', value == 'Y')
            source.finish(allow_text=True)
        if routes.children() and len(routes.children()) != len(layers):
            raise PcbError(f'{record.node.path}: routing flags require one entry per copper layer')
        record.finish()


def read_classes(record, board, *, layers, vias, units):
    collection, by_key = board.add('NetClasses'), {}
    for source in record.rows('NetClasses', 'NetClass'):
        key = unique_id(source, by_key, label='net class')
        target = collection.add('NetClass', source.text('Name', ''))
        by_key[key] = target
        target.add('Type', enum_value(source.value('Type', 'Normal'), ('Normal', 'Differential Pair')))
        target.add('HiddenID', source.integer('UpdateId', -1))
        for name, default in CLASS_FLAGS.items():
            target.add(name, source.boolean(name, default))
        for name, default in CLASS_LENGTHS.items():
            target.add(name, length(source.number(name), units) if source.has(name) else default)
        _properties(source, target, layers=layers, uniform=target['AllLayers'], units=units)
        allowed = target.add('AllowedVias')
        for member in source.rows('AllowedVias', 'ViaStyle'):
            value = member.content()
            if value.kind != 'number' or value.unit or int(value.value) != value.value:
                raise PcbError(f'{member.node.path}: expected a via-style Id')
            selected = position(int(value.value), vias, label='allowed via style', path=member.node.path)
            if selected < 0:
                raise PcbError(f'{member.node.path}: allowed via style must have a target')
            allowed.add('ViaStyle', selected)
            member.finish(allow_text=True)
        _autorouting(source.take('Autorouting'), target, layers=layers)
        source.finish()
    return by_key
