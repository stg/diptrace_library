"""Current XML net-class settings with explicit layer and via references."""
from ....common.conversion import info
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import enum_text, field, numeric
from ...model import board_rules, rule_records
from ..errors import PcbError
from ..output_validation import check_tree, field_value


def layer_rows(owner, path, layers, *, uniform=False):
    rows = tuple(owner.select(path))
    if uniform:
        if len(rows) > 1 or rows and rows[0]['Layer'] is not None:
            raise PcbError(f'{owner.path}: uniform properties require at most one unscoped row')
        return rows
    by_layer = {row['Layer']: row for row in rows}
    if len(by_layer) != len(rows) or set(by_layer) != set(layers):
        raise PcbError(f'{owner.path}: properties require one row per current copper layer')
    return tuple(by_layer[layer] for layer in layers)


def project_classes(board, *, keys, units, report=None):
    result = Element('NetClasses')
    layers, classes = tuple(board.select('Layers/Layer')), keys.indices.classes
    if classes != tuple(board.select('NetClasses/NetClass')):
        info(report, 'default-class-position', 'dipxml', 'XML places the default class first', (board,),
             recoverability='class settings and all identity-based assignments remain')
    for source in classes:
        check_tree(source, board_rules.NET_CLASS, destination='DIPXML')
        row = result.add('NetClass')
        for name, value in (('Id', keys.net_class(source)), ('UpdateId', field_value(source, 'HiddenID')),
                            ('Type', enum_text(field_value(source, 'Type'), ('Normal', 'Differential Pair')))):
            set_attribute(row, name, value)
        field(row, 'Name', source['Name'])
        for name in ('AllLayers', 'AllVias', 'CheckLength', 'PerformDRC'):
            set_attribute(row, name, field_value(source, name))
        for name in ('Phase', 'Phase_ErrorLength', 'LengthDelta', 'FixedLength', 'MaxUncoupledLength', 'Tolerance'):
            if name == 'FixedLength' and field_value(source, name) == -1:
                continue
            set_attribute(row, name, numeric(units.length(field_value(source, name))))
        if not field_value(source, 'AllLayers') and len({layer['Name'] for layer in layers}) != len(layers):
            raise PcbError(f'{source.path}: XML layer-specific properties require distinct copper-layer names')
        properties = row.add('LayProperties')
        for current in layer_rows(source, 'LayProperties/LayProperty', layers, uniform=field_value(source, 'AllLayers')):
            target = properties.add('LayProperty')
            field(target, 'LayerName', current['LayerName'])
            for name, definition in rule_records.LAYER_PROPERTY.fields.items():
                if definition.kind != 'number' or definition.getter is not None:
                    continue
                if field_value(current, name) == -1 and name not in ('MinWidth', 'MaxWidth'):
                    continue
                set_attribute(target, name, numeric(units.length(field_value(current, name))))
            if (details := current.child('ClearanceDetails')) is not None:
                target = target.add('ClearanceDetails')
                for name in rule_records.CLASS_CLEARANCE_NAMES:
                    if field_value(details, name) != -1:
                        set_attribute(target, name, numeric(units.length(field_value(details, name))))
        allowed = row.add('AllowedVias')
        for member in source.select('AllowedVias/ViaStyle'):
            if member['Via'] is None:
                raise PcbError(f'{member.path}: allowed via requires a current via style')
            field(allowed, 'ViaStyle', member['Id'])
        routes = row.add('Autorouting')
        for name in ('RoutePriority', 'RouteMaxVias', 'RouteMaxIncorrectWay', 'RouteAllLayers',
                     'PriorityValue', 'MaxViasValue', 'MaxIncorrectWayValue'):
            set_attribute(routes, name, field_value(source, name))
        selected = source.select('RouteLayers/Item')
        flags = routes.add('RouteLayers')
        if selected:
            for member in layer_rows(source, 'RouteLayers/Item', layers):
                field(flags, 'Item', 'Y' if member['Enabled'] else 'N')
    return result
