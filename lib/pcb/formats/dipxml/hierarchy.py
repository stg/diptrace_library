"""Literal schematic hierarchy identities from one PCB XML document."""


def read_sheets(record, board):
    if record is None:
        return
    sheets = board.add('HierarchySheets')
    for source in record.children('HSheet'):
        sheet = sheets.add('HSheet', source.text('Name', ''), source.integer('Number'))
        blocks = sheet.add('UpdateIds')
        for item in source.rows('UpdateIds', 'UId'):
            blocks.add('UId', item.integer('Name', attribute=True),
                       item.text('Name', '', attribute=False))
            item.finish()
        source.finish()
    record.finish()


def read_path(record, component):
    path = component.add('HierarchyPath')
    if record is None:
        return
    for item in record.children('Item'):
        value = item.content()
        if value.kind != 'number' or value.unit or value.value != int(value.value):
            raise ValueError(f'{item.node.path}: expected an integer hierarchy identity')
        path.add('Item', int(value.value))
        item.finish(allow_text=True)
    record.finish()
