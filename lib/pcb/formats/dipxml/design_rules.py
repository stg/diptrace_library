"""XML design checks and class-pair clearances enter the existing rule model."""
from ....common.model import Element
from ....common.xml_records import length
from ...model.rule_records import DRC, DRC_CLEARANCE, DRC_SIZE, DRC_CLEARANCE_NAMES
from ..errors import PcbError
from .keys import position


def _clearance(value, units):
    # Class-pair XML uses -1 as inheritance, independently of display units.
    return value if value.value == -1 else length(value, units)


def read_class_clearances(record, board, *, classes, layers, units):
    if record is None:
        return
    board.add('ClassToClass', record.boolean('Enabled', False))
    collection, seen, cells = board.add('ClassClearances'), set(), []
    for source in record.rows('CTC_Cells', 'Cell'):
        pair = tuple(position(source.integer(name), classes, label='clearance net class',
                              path=source.node.path) for name in ('NetClass1', 'NetClass2'))
        if min(pair) < 0:
            raise PcbError(f'{source.node.path}: class clearance requires two classes')
        first, second = max(pair), min(pair)
        if (first, second) in seen:
            raise PcbError(f'{source.node.path}: duplicate symmetric class clearance')
        seen.add((first, second))
        target = Element('Cell', first, second)
        cells.append(target)
        uniform = source.has('Clearance')
        target.add('AllLayers', uniform)
        values = target.add('Values')
        if uniform:
            values.add('Item', _clearance(source.number('Clearance'), units))
        by_layer = {}
        for row in source.rows('LayerClearances', 'LayerClearance'):
            layer = position(row.integer('Id'), layers, label='class clearance layer', path=row.node.path)
            if layer < 0 or layer in by_layer:
                raise PcbError(f'{row.node.path}: invalid or duplicate class clearance layer')
            by_layer[layer] = _clearance(row.number('Clearance', -1), units)
            row.finish()
        if uniform and by_layer:
            raise PcbError(f'{source.node.path}: class clearance mixes uniform and per-layer values')
        if not uniform:
            for index in range(len(layers)):
                values.add('Item', by_layer.get(index, -1))
        source.finish()
    for cell in sorted(cells, key=lambda item: item.values):
        collection.append(cell)
    record.finish()


def _layer_rows(record, target, collection, kind, definition, *, layers, uniform, units):
    rows = {}
    for ordinal, source in enumerate(record.rows(collection, kind)):
        selected = source.integer('Lay', ordinal)
        # The uniform output row convention uses slot zero. Per-layer records
        # instead address saved copper-layer identities before key consumption.
        index = 0 if uniform and selected == 0 else position(
            selected, layers, label='DRC copper layer', path=source.node.path)
        if index < 0 or index in rows:
            raise PcbError(f'{source.node.path}: invalid or duplicate DRC layer')
        row = rows[index] = Element(kind, index)
        for name, field in definition.fields.items():
            if field.getter is None and source.has(name):
                row.add(name, length(source.number(name), units))
        if kind == 'LayClearance':
            for name in ('SameTraceToTrace', 'SameSmdToVia', 'SameSmdToPad', 'SameSmdToSmd'):
                if row.child(name) is None:
                    row.add(name, 0)
            details = source.take('ClearanceDetails')
            output = row.add('ClearanceDetails')
            for name in DRC_CLEARANCE_NAMES:
                output.add(name, length(details.number(name), units)
                           if details is not None and details.has(name) else -1)
            if details is not None:
                details.finish()
        source.finish()
    if uniform:
        if rows and 0 not in rows:
            raise PcbError(f'{record.node.path}: uniform DRC requires its first layer rule')
    elif rows and set(rows) != set(range(len(layers))):
        raise PcbError(f'{record.node.path}: DRC requires a rule per copper layer')
    # The assembler consumes layer positions in stack order, then retains links.
    for index in sorted(rows):
        target.append(rows[index])


def read_drc(record, board, *, kind, layers, units, version):
    if record is None:
        return
    target = board.add(kind)
    target.add('Name', record.text('Name', ''))
    target.add('AllLayers', record.boolean('AllLayers'))
    for name, field in DRC.fields.items():
        if name in ('Name', 'AllLayers'):
            continue
        if kind == 'LastDRC' and name in ('ShowList', 'RealTimeMode', 'DRCDone'):
            # These describe the current check UI, not the saved rule context.
            record.take(name)
            continue
        public = version.drc_copper_pours_name if name == 'CheckCopperPours' else name
        if record.has(public):
            value = getattr(record, field.kind)(public)
            target.add(name, length(value, units) if field.kind == 'number' else value)
    for collection, name, definition in (('LayClearances', 'LayClearance', DRC_CLEARANCE),
                                          ('LaySizes', 'LaySize', DRC_SIZE)):
        _layer_rows(record, target.add(collection), collection, name, definition,
                    layers=layers, uniform=target['AllLayers'], units=units)
    record.finish()


def read_design_rules(record, board, *, classes, layers, units, version):
    read_class_clearances(record.take('ClassToClass'), board, classes=classes, layers=layers, units=units)
    for kind in ('DRC', 'LastDRC'):
        read_drc(record.take(kind), board, kind=kind, layers=layers, units=units, version=version)
