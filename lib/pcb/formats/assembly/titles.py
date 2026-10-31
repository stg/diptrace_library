"""Bind title-field selections after consuming their source positions."""
from ....common.references import Index
from ....common.conversion import import_notice
from ...model import title_records as records, title_relations as links
from ..errors import PcbError


def bind_titles(document, sheet):
    if sheet is None:
        return
    prepared = []
    for grid in sheet.select('TitleBlocks/TitleBlock'):
        contents = grid.select('Contents/Content')
        for cell in grid.select('Cells/Cell'):
            if len(cell.values) != 3 or type(cell.values[2]) is not int:
                raise PcbError('title cell requires column, row and field position')
            index = cell.values[2]
            target = contents[index] if 0 <= index < len(contents) else None
            if target is None and index >= 0:
                cell.add(links.MISSING, index)
            prepared.append((cell, target, grid.one('Contents')))
    for node in sheet.walk():
        if (schema := records.definition(node)) is not None:
            node.bind_schema(schema)
    unresolved = []
    with document.references.binding_batch():
        for cell, target, collection in prepared:
            if target is not None:
                document.references.bind(cell, target, role=links.ROLE, preserve=True)
            elif (missing := cell.child(links.MISSING)) is not None:
                document.references.note(cell, links.ROLE+': field position cannot be resolved',
                                         Index(missing), collections=(collection,))
                unresolved.append(cell)
    if unresolved:
        import_notice('warning', 'unresolved-title-field', 'Title cells refer to unavailable fields', unresolved)
