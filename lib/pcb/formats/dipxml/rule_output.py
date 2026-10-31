"""PCB check rules and material stack from current class/layer identities."""
from ....common.conversion import info
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import enum_text, field, numeric
from ...model import board_rules, rule_records
from ..errors import PcbError
from ..output_validation import check_tree, field_value
from .class_output import layer_rows


def _clearance(value, units):
    return -1 if value is None else numeric(units.length(value))


def _class_clearances(board, *, keys, units):
    result = Element('ClassToClass')
    if (enabled := board.get('ClassToClass')) is not None:
        set_attribute(result, 'Enabled', enabled)
    if (source := board.child('ClassClearances')) is None:
        return result
    check_tree(source, rule_records.COLLECTIONS['ClassClearances'], destination='DIPXML')
    rows, seen, layers = result.add('CTC_Cells'), set(), tuple(board.select('Layers/Layer'))
    for cell in source.children('Cell'):
        if cell['Class1'] is None or cell['Class2'] is None:
            raise PcbError(f'{cell.path}: class clearance requires two current classes')
        pair = tuple(sorted((keys.net_class(cell['Class1']), keys.net_class(cell['Class2']))))
        if pair in seen:
            raise PcbError(f'{cell.path}: duplicate symmetric class clearance')
        seen.add(pair)
        row = rows.add('Cell')
        for name, value in zip(('NetClass1', 'NetClass2'), pair):
            set_attribute(row, name, value)
        if cell['AllLayers']:
            if cell.child('LayerClearances') is not None:
                raise PcbError(f'{cell.path}: uniform clearance has inactive per-layer data')
            set_attribute(row, 'Clearance', _clearance(cell['Clearance'], units))
        else:
            if cell.get('Clearance') is not None:
                raise PcbError(f'{cell.path}: per-layer clearance has an inactive uniform value')
            target = row.add('LayerClearances')
            for current in layer_rows(cell, 'LayerClearances/LayerClearance', layers):
                entry = target.add('LayerClearance')
                set_attribute(entry, 'Id', current['Lay'])
                set_attribute(entry, 'Clearance', _clearance(current['Clearance'], units))
    return result


def _drc(source, *, layers, units, report):
    check_tree(source, rule_records.DRC, destination='DIPXML')
    result = Element(source.kind)
    for name, definition in rule_records.DRC.fields.items():
        if source.kind == 'LastDRC' and name in ('ShowList', 'RealTimeMode', 'DRCDone'):
            if name in source:
                info(report, 'previous-check-ui', 'dipxml',
                     'Previous-rule output omits current check-window state', (source,))
            continue
        value = field_value(source, name)
        emit = field if name in ('Name', 'ShowList', 'RealTimeMode', 'DRCDone') else set_attribute
        emit(result, name, numeric(units.length(value)) if definition.unit == 'shared length' else value)
    uniform = field_value(source, 'AllLayers')
    for name, kind, definition in (('LayClearances', 'LayClearance', rule_records.DRC_CLEARANCE),
                                  ('LaySizes', 'LaySize', rule_records.DRC_SIZE)):
        target = result.add(name)
        existing = source.select(name+'/'+kind)
        rows = layer_rows(source, name+'/'+kind, layers, uniform=uniform) if existing else ()
        for current in rows:
            row = target.add(kind)
            set_attribute(row, 'Lay', 0 if uniform else current['Lay'])
            for field_name, item in definition.fields.items():
                if item.kind == 'number' and item.getter is None:
                    set_attribute(row, field_name, numeric(units.length(field_value(current, field_name))))
            if (details := current.child('ClearanceDetails')) is not None:
                values = row.add('ClearanceDetails')
                for field_name in rule_records.DRC_CLEARANCE_NAMES:
                    if (value := field_value(details, field_name)) != -1:
                        set_attribute(values, field_name, numeric(units.length(value)))
    return result


def project_stack(board, *, units):
    result = Element('Board')
    if (name := board.get('LayerStackName')) is not None:
        field(result, 'LayerStackName', name)
    if (source := board.child('LayerStackItems')) is None:
        return result
    check_tree(source, board_rules.COLLECTIONS['LayerStackItems'], destination='DIPXML')
    rows = result.add('LayerStackItems')
    for current in source.children('LayerStackItem'):
        row = rows.add('LayerStackItem')
        set_attribute(row, 'Lay', current['Lay'])
        material, target = current.one('Material'), row.add('Material')
        field(target, 'Name', field_value(material, 'Name'))
        set_attribute(target, 'Type', enum_text(material['Type'], ('Conductor', 'Plane', 'Dielectric')))
        for name in ('VariableThickness', 'Constant'):
            set_attribute(target, name, field_value(material, name))
        for name in ('Thickness', 'TraceWidth'):
            set_attribute(target, name, numeric(units.length(field_value(material, name))))
    return result


def project_design_rules(board, *, keys, units, report=None):
    result = project_stack(board, units=units)
    clearances = _class_clearances(board, keys=keys, units=units)
    if clearances.children():
        result.append(clearances)
    for name in ('DRC', 'LastDRC'):
        if (source := board.child(name)) is not None:
            result.append(_drc(source, layers=tuple(board.select('Layers/Layer')), units=units, report=report))
    return result
