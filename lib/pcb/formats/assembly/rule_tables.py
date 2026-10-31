"""Modernize positional rule tables into editable, identity-based PCB records."""
from ....common.structural_edits import assembly
from ....common.conversion import import_notice
from ...model import rule_records
from ..errors import PcbError


def _matrix_cells(matrix):
    """Yield the two format boundary shapes without imposing either on the model."""
    rows, cells = matrix.children('Row'), matrix.children('Cell')
    if rows and cells:
        raise PcbError('mixed class clearance matrix representations')
    if cells:
        for cell in cells:
            if len(cell.values) != 2 or any(type(value) is not int or value < 0 for value in cell.values):
                raise PcbError('invalid class clearance coordinates')
            yield cell.values[0], cell.values[1], cell
    else:
        for first, row in enumerate(rows):
            for second, cell in enumerate(row.children('Cell')):
                yield first, second, cell


def assemble_tables(result):
    """Bind rule-table targets after the board's layer/style/class identities.

    The remaining PCB import stages still own geometry, diagnostics and other
    reference families. This does not return a publicly usable partial import.
    """
    document = result.document
    board = document.one('/Board')
    links, clear_details, remove, clear_values, flags, replacements = [], [], [], [], [], []
    settings = board.child('Settings')
    routing = settings.child('Routing') if settings is not None else None
    # Binary files save two copies of the default width/clearance. The routing
    # settings supply their current value; the model stores it in the default
    # class and exposes the settings names as writable aliases.
    defaults = {name: routing.child(name) for name in ('TraceWidth', 'TraceClearance')} if routing is not None else {}
    default_class = next(iter(result.classes.values()), None)
    if default_class is not None:
        links.append((board, 'default-net-class', default_class))
        rows = default_class.select('LayProperties/LayProperty')
        if rows:
            for name, target in (('TraceWidth', 'Width'), ('TraceClearance', 'Clearance')):
                if defaults.get(name) is not None:
                    replacements.append((rows[0], target, defaults[name].values[0]))
    # These boundary slots are aliases, including when no class/property row
    # exists. In that case the current alias is unavailable, not a stored copy.
    remove.extend(slot for slot in defaults.values() if slot is not None)

    def layer_scope(rows, uniform):
        if uniform:
            # Uniform rules have one authored value. Remaining saved slots are
            # inactive copies; writers regenerate positions for their format.
            remove.extend(rows[1:])
            rows = rows[:1]
        for index, row in enumerate(rows):
            clear_values.append(row)
            if not uniform:
                if index not in result.layers:
                    raise PcbError('rule layer table requires import resizing')
                links.append((row, 'copper-layer', result.layers[index]))
        return rows

    for net_class in result.classes.values():
        properties = layer_scope(net_class.select('LayProperties/LayProperty'), net_class.get('AllLayers', False))
        for row in properties:
            if net_class.get('Type', 0) == 1:
                for field, name in (('Width', 'TraceWidth'), ('Clearance', 'TraceClearance'), ('DifClearance', 'TraceClearance')):
                    if row.get(field, -1) <= -1 and defaults.get(name) is not None:
                        replacements.append((row, field, defaults[name].values[0]))
            source = row.child('ClearDetails')
            if source is not None:
                values = source.children('pt')
                if len(values) != 4 or any(len(item.values) != 5 for item in values):
                    raise PcbError('invalid class clearance detail dimensions')
                clear_details.append((source, tuple(
                    (rule_records.CLEARANCE_KINDS[first]+'To'+rule_records.CLEARANCE_KINDS[second], values[first].values[second])
                    for first in range(4) for second in range(first, 5))))
        for allowed in net_class.select('AllowedVias/ViaStyle'):
            key, = allowed.values
            if key not in result.via_styles:
                raise PcbError(f'unresolved allowed via style {key}')
            links.append((allowed, 'via-style', result.via_styles[key]))
            clear_values.append(allowed)
        for index, flag in enumerate(net_class.select('RouteLayers/Item')):
            if index not in result.layers:
                raise PcbError('routing layer table requires import resizing')
            flags.append((flag, flag.values[0]))
            links.append((flag, 'copper-layer', result.layers[index]))

    for kind in ('DRC', 'LastDRC'):
        drc = board.child(kind)
        if drc is not None:
            layer_scope(drc.select('LayClearances/LayClearance'), drc['AllLayers'])
            layer_scope(drc.select('LaySizes/LaySize'), drc['AllLayers'])

    matrix = board.child('ClassClearances')
    cells, surplus = [], []
    if matrix is not None:
        for first, second, cell in _matrix_cells(matrix):
            # The public rule is symmetric. Only the lower triangle is
            # addressed; the opposite half is generated during output.
            if second > first:
                continue
            if first not in result.classes or second not in result.classes:
                surplus.append(cell)
                continue
            values = tuple(item.values[0] for item in cell.select('Values/Item'))
            uniform = cell['AllLayers']
            if not uniform and len(values) > len(result.layers):
                raise PcbError('class clearance layer table requires import resizing')
            cells.append((cell, result.classes[first], result.classes[second], uniform, values))
    if surplus:
        import_notice('info', 'class-clearance-table-normalization',
                      f'Removed {len(surplus)} unused clearance cells outside the current class list.',
                      (matrix,), recoverability='rules for current classes retained; unused table storage removed')

    with assembly(document):
        for node, name, value in replacements:
            node[name] = value
        for node in remove:
            node.detach()
        for node in clear_values:
            node.set_values()
        for source, fields in clear_details:
            for child in source.children():
                child.detach()
            source.kind = 'ClearanceDetails'
            for name, value in fields:
                source.add(name, value)
        for flag, value in flags:
            flag.set_values()
            flag.add('Enabled', value)
        if matrix is not None:
            for row in matrix.children():
                row.detach()
            for cell, first, second, uniform, values in cells:
                cell.detach()
                cell.set_values()
                cell.one('Values').detach()
                if uniform:
                    cell.add('Clearance', None if not values or values[0] == -1 else values[0])
                else:
                    per_layer = cell.add('LayerClearances')
                    for index, value in enumerate(values):
                        rule = per_layer.add('LayerClearance')
                        rule.add('Clearance', None if value == -1 else value)
                        links.append((rule, 'copper-layer', result.layers[index]))
                matrix.append(cell)
                links.extend(((cell, 'net-class-1', first), (cell, 'net-class-2', second)))
        for node in board.walk(include_self=True):
            if (schema := rule_records.definition(node)) is not None:
                node.bind_schema(schema)
        with document.references.binding_batch():
            for source, role, target in links:
                document.references.bind(source, target, role=role, preserve=True)
    return result
