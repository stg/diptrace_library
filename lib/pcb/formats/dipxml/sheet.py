"""PCB's single drawing sheet and viewport, independent of board geometry."""
from ....common.xml_records import length, point
from ....common.xml_font_import import read_size
from ....common.xml_cells import read_title_blocks
from ....common.title_records import new_title_blocks
from ...model.settings_records import SHEET, BORDER_ZONES


def read_sheet(record, root, board, *, units):
    if record is None:
        return
    sheet = board.add('SheetSettings')
    for name, field in SHEET.fields.items():
        if record.has(name):
            value = getattr(record, field.kind)(name)
            sheet.add(name, length(value, units) if field.unit == 'shared length' else value)
    if record.has('Scale'):
        root.add('Scale', record.number('Scale'))
    for name, value in zip(('Xpos', 'Ypos'), point(record, units, ('Xpos', 'Ypos'), 0)):
        root.add(name, value)
    source = record.take('BorderZones')
    if source is not None:
        zones = sheet.add('BorderZones')
        for name, field in BORDER_ZONES.fields.items():
            if name == 'FontSize':
                if source.has('FontSize') or source.has('FontSizeFloat'):
                    zones.add(name, read_size(source))
            elif source.has(name):
                value = getattr(source, field.kind)(name)
                # A negative pen width selects a font stroke convention.
                zones.add(name, length(value, units) if field.unit == 'shared length'
                          and (name != 'FontLineWidth' or value.value >= 0) else value)
        source.finish()
    sheet.append(new_title_blocks())
    read_title_blocks(record, sheet, units=units)
    record.finish()
