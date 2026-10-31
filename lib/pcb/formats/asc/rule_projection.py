"""Generate ASC board rules from current layer, style and class identities.

This internal section writer is not a complete document adapter. Its output is
detached: mirrored matrix cells, compatibility diameters and all positional
selectors are generated here, without adding them to the editable model.
"""
from ....common.model import Element, Value
from ....common.conversion import info, warn
from ...model import board_rules as model, rule_records as rules
from ..errors import PcbError
from ..output_indices import OutputIndices
from .projection import check, collection, fields, flag, layer_rows, rows, value
from .length_projection import project_length_rules
from .rule_settings_projection import project_rule_settings


def _board_rows(board, name, schema):
    return collection(board, name, model.COLLECTIONS[name], schema)


def _layers(board, output, report):
    layers = _board_rows(board, 'Layers', model.LAYER)
    result = output.add('Layers')
    for layer in layers:
        name = value(layer, 'Name')
        # ASC decodes every exclamation mark as a space in layer names.
        # A literal exclamation mark therefore has no faithful ASC spelling.
        if '!' in name:
            warn(report, 'layer-name-spelling', 'asc',
                 'ASC reads literal exclamation marks in copper-layer names as spaces', [layer],
                 recoverability='layer identities and positional connections remain; the name spelling changes')
        row = result.add('Name', *([Value(name.replace(' ', '!'), 'symbol')] if name else []))
        row.add('Number', layer['Number'])
        fields(layer, row, exclude=('Name', 'HoleRing'))
        row.add('NetNumber', layer['NetNumber'])
        radius = value(layer, 'HoleRing')
        row.add('HoleSize', radius*2)
        row.add('HoleRing', radius)
    return layers


def _vias(board, output):
    result = output.add('ViaStyles')
    for style in _board_rows(board, 'ViaStyles', model.VIA):
        model.validate_span(board._owner(), style)
        result.add('ViaStyle', value(style, 'Name'), flag(style['Through']),
                   value(style, 'Size'), value(style, 'HoleSize'), style['Lay1'], style['Lay2'])


def _layer_rows(owner, name, record, layers, *, uniform=False):
    return layer_rows(owner, name, rules.COLLECTIONS[name], record, layers, uniform=uniform)


def _details(source, output):
    check(source, rules.CLASS_DETAILS)
    projected = output.add('ClearDetails')
    # The compact rectangle repeats no independent lower-triangle rules.
    # Those unused entries use the format's ordinary inherited-value marker.
    for first in range(4):
        projected.add('pt', *(-1 if second < first else value(source,
            rules.CLEARANCE_KINDS[first]+'To'+rules.CLEARANCE_KINDS[second])
            for second in range(5)))


def _classes(board, output, layers, indices):
    _board_rows(board, 'NetClasses', model.NET_CLASS)
    classes = indices.classes
    result = output.add('NetClasses')
    for net_class in classes:
        row = result.add('NetClass', value(net_class, 'Name'))
        fields(net_class, row, exclude=('Name',), names={
            'RoutePriority': 'RouteParity', 'PriorityValue': 'ParityValue'})
        properties = row.add('LayProperties')
        for source in _layer_rows(net_class, 'LayProperties', rules.LAYER_PROPERTY,
                                  layers, uniform=value(net_class, 'AllLayers')):
            projected = properties.add('LayProperty')
            fields(source, projected, names={'MinWidth': 'MaxWidth', 'MaxWidth': 'MinWidth'})
            if (details := source.child('ClearanceDetails')) is not None:
                _details(details, projected)
        allowed = row.add('ViaStyle')
        for source in collection(net_class, 'AllowedVias', rules.COLLECTIONS['AllowedVias'], rules.ALLOWED_VIA):
            if source['Via'] is None:
                raise PcbError(f'{source.path}: allowed via requires a via-style target')
            allowed.add('pt', source['Id'])
        route_layers = row.add('RouteLayers')
        for source in _layer_rows(net_class, 'RouteLayers', rules.ROUTE_LAYER, layers):
            route_layers.add('pt', flag(value(source, 'Enabled')))
    return classes


def _matrix(board, output, layers, classes):
    source = board.child('ClassClearances')
    if source is None:
        return
    cells = rows(source, rules.COLLECTIONS['ClassClearances'], rules.CLASS_CELL)
    positions = {net_class: index for index, net_class in enumerate(classes)}
    by_pair = {}
    for cell in cells:
        try:
            pair = tuple(sorted((positions[cell['Class1']], positions[cell['Class2']])))
        except KeyError:
            raise PcbError(f'{cell.path}: clearance requires two current net classes') from None
        if pair in by_pair:
            raise PcbError(f'{cell.path}: duplicate symmetric class-clearance rule')
        if value(cell, 'AllLayers'):
            if cell.child('LayerClearances') is not None:
                raise PcbError(f'{cell.path}: uniform clearance has inactive per-layer data')
            selected = (value(cell, 'Clearance'),)
        else:
            if cell.child('Clearance') is not None and value(cell, 'Clearance') is not None:
                raise PcbError(f'{cell.path}: per-layer clearance has an inactive uniform value')
            selected = tuple(value(row, 'Clearance') for row in
                _layer_rows(cell, 'LayerClearances', rules.LAYER_CLEARANCE, layers))
        by_pair[pair] = value(cell, 'AllLayers'), selected
    # An empty optional matrix stays empty. A populated matrix extends through
    # its last addressed class; missing pairs have no override (inherited -1).
    # Do not turn unused class capacity into additional authored model rules.
    count = max((pair[1]+1 for pair in by_pair), default=0)
    matrix = output.add('CTC_Cells', count)
    for first in range(count):
        for second in range(count):
            uniform, values = by_pair.get(tuple(sorted((first, second))), (True, (None,)))
            projected = matrix.add('Cell', first, second, flag(uniform))
            for current in values:
                projected.add('pt', -1 if current is None else current)


def _stack(board, output):
    source = board.child('LayerStackItems')
    if source is None:
        return
    items = rows(source, model.COLLECTIONS['LayerStackItems'], model.STACK_ITEM)
    stack = output.add('LayerStack', value(board, 'LayerStackName'), len(items))
    for item in items:
        material = item.one('Material')
        check(material, model.MATERIAL)
        stack.add('pt', item['Lay'], value(material, 'Name'), material['Type'],
                  flag(value(material, 'VariableThickness')), value(material, 'Thickness'),
                  value(material, 'Constant'), value(material, 'TraceWidth'))


def project_rules(board, *, report=None, indices=None):
    """Return only the complete rule sections; other Board data is owned elsewhere.

    A caller composing a whole document must also handle all remaining board
    sections. This function does not assert whole-document output eligibility.
    """
    output = Element('Board')
    indices = indices or OutputIndices(board)
    if indices.classes != tuple(board.select('NetClasses/NetClass')):
        info(report, 'default-class-order', 'asc', 'Placed the default class first in ASC output',
             indices.classes, recoverability='class identities and settings retain their meaning')
    layers = _layers(board, output, report)
    _vias(board, output)
    classes = _classes(board, output, layers, indices)
    output.add('ClassToClass', flag(value(board, 'ClassToClass')))
    _matrix(board, output, layers, classes)
    _stack(board, output)
    for node in project_length_rules(board, indices=indices).children():
        node.move_to(output)
    settings = project_rule_settings(board, layers)
    if settings.children():
        output.append(settings)
    return output
