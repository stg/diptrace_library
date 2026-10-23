"""Public library labels, local groups and points into owned scalar records."""
from .dchxml_import_values import enum_value, point, replace_rows
from .model import Element
from .local_keys import map_key


def read_points(record, *, units, name='Points', kind=('Item', 'Point')):
    result = []
    for item in record.rows(name, kind):
        result.append(Element('pt', *point(item, units)))
        item.finish()
    return result


def read_groups(record, owner, *, units, container='Groups'):
    rows, ids = [], {}
    for index, source in enumerate(record.rows('Groups', 'Item')):
        key = source.integer('Id', index)
        if key in ids:
            raise ValueError(f'{source.node.path}: duplicate group Id')
        ids[key] = index
        rows.append(Element('pt', True, index, *point(source, units, default=0)))
        source.finish()
    replace_rows(owner, container, rows)
    return ids


def mapped_group(record, ids, owner):
    key = record.integer('Group', -1)
    return map_key(owner, 'Group', key, ids)


def read_category(source, owner):
    if source is None:
        return
    prefix = 'Pattern' if owner.kind == 'Pattern' else 'Component'
    owner.set_field(prefix+'_CategoryName', source.text('Name', ''))
    owner.set_field(prefix+'_CategoryIndex', source.integer('Index', -1))
    target = owner.one(prefix+'_CategoryTypes')
    for item in source.rows('CategoryTypes', 'CategoryType'):
        kind = item.take('Type', required=True)
        type_name, type_id = kind.content(), kind.integer('Index', -1)
        kind.finish(allow_text=True)
        subtype = item.take('SubType')
        subtype_name, subtype_id = '', -1
        if subtype is not None:
            subtype_name, subtype_id = subtype.content(), subtype.integer('Index', -1)
            subtype.finish(allow_text=True)
        target.add(prefix+'_Type', type_name, subtype_name, type_id, subtype_id)
        item.finish()
    source.finish()


def read_user_fields(record, owner, *, placed=False):
    for item in record.rows('AddFields', 'AddField'):
        values = [item.text('Name', ''), item.text('Text', ''), enum_value(item.value('Type', 'Text'), ('Text', 'Link'))]
        if owner.kind == 'Part' and not placed:
            values.extend((0,)*7)
        owner.one('UserFields').add('UserField', *values)
        item.finish()


def read_path(record):
    path = record.text('Path', '')
    variable = record.text('Var', path)
    record.finish()
    return path, variable
