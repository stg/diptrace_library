"""Public library labels, local groups and points into owned scalar records."""
from .xml_records import enum_value, point, replace_rows
from .conversion import import_notice
from .model import Element
from .units import XmlUnits


def read_points(record, *, units, name='Points', kind=('Item', 'Point')):
    result = []
    for item in record.rows(name, kind):
        result.append(Element('pt', *point(item, units)))
        item.finish()
    return result


def read_groups(record, owner, *, units, container='Groups'):
    rows, ids, inactive = [], {}, []
    for index, source in enumerate(record.rows('Groups', 'Item')):
        identified = source.has('Id')
        key = source.integer('Id', index)
        if source.has('Number'):
            number = source.integer('Number')
            if identified and key != number:
                raise ValueError(f'{source.node.path}: conflicting local group keys')
            key = number
        if key in ids:
            raise ValueError(f'{source.node.path}: duplicate group Id')
        enabled = source.boolean('Enabled', True)
        coordinates = point(source, units, default=0)
        source.finish()
        # Public keys address the supplied rows, not the compacted collection.
        # A known inactive group is unassigned; a missing key remains unresolved.
        ids[key] = len(rows) if enabled else -1
        if enabled:
            rows.append(Element('pt', True, len(rows), *coordinates))
        else:
            inactive.append(source.node)
    replace_rows(owner, container, rows)
    if inactive:
        import_notice('info', 'local-group-normalization',
                      f'Removed {len(inactive)} inactive local groups; their members are ungrouped.', inactive,
                      recoverability='active local groups and member geometry retained')
    return ids


def mapped_group(record, ids, owner, *, resolve_key):
    key = record.integer('Group', -1)
    return resolve_key(owner, 'Group', key, ids)


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
        target.add('CategoryType', type_name, subtype_name, type_id, subtype_id)
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


def read_project_libraries(record, owner):
    """Read literal project search paths; importing does not open libraries."""
    if record is None:
        return
    for own, public, kind in (('ProjectLibs_Folders', 'Folders', 'Folder'), ('ProjectLibs_Libs', 'Libs', 'Lib')):
        if owner.child(own) is None:
            owner.add(own)
        rows = []
        for item in record.rows(public, kind):
            actual, variable = read_path(item)
            path = Element(kind, actual)
            path.add('VariablePath', variable)
            rows.append(path)
        replace_rows(owner, own, rows)
    owner.set_field('ProjectLibs_Sorted', record.boolean('Sorted', False))
    record.finish()


def _catalog_index(record, preferred, default):
    other = 'Number' if preferred == 'Index' else 'Index'
    key = record.integer(preferred, default) if record.has(preferred) else record.integer(other, default)
    if record.has(other):
        alternate = record.integer(other)
        if alternate != key:
            raise ValueError(f'{record.node.path}: conflicting catalog keys')
    return key


def read_catalog(record, *, key):
    result = Element('Categories')
    seen = set()
    for index, source in enumerate(record.rows('Categories', 'Category')):
        number = _catalog_index(source, key, index)
        if number in seen:
            raise ValueError(f'{source.node.path}: duplicate category key')
        seen.add(number)
        category = result.add('Category', source.text('Name', ''), number)
        type_keys = set()
        for ordinal, item in enumerate(source.rows('Types', 'Type')):
            position = _catalog_index(item, key, ordinal)
            if position in type_keys:
                raise ValueError(f'{item.node.path}: duplicate category type key')
            type_keys.add(position)
            kind = category.add('Type', item.text('Name', ''), position)
            subtype_keys = set()
            for order, sub in enumerate(item.rows('SubTypes', 'SubType')):
                value = _catalog_index(sub, key, order)
                if value in subtype_keys:
                    raise ValueError(f'{sub.node.path}: duplicate category subtype key')
                subtype_keys.add(value)
                kind.add('Subtype', sub.text('Name', ''), value)
                sub.finish()
            item.finish()
        source.finish()
    return result


def resolve_category(owner, categories):
    prefix = 'Pattern' if owner.kind == 'Pattern' else 'Component'
    key = owner.scalar(prefix+'_CategoryIndex')
    category = next((item for item in categories.children('Category') if item.values[1] == key), None)
    if category is None:
        return
    if not owner.scalar(prefix+'_CategoryName'):
        owner.set_field(prefix+'_CategoryName', category.arguments[0])
    for row in owner.one(prefix+'_CategoryTypes').children():
        kind = next((item for item in category.children('Type') if item.values[1] == row.values[2]), None)
        if kind is None:
            continue
        if not row.values[0]:
            row.set_argument(0, kind.arguments[0])
        subtype = next((item for item in kind.children('Subtype') if item.values[1] == row.values[3]), None)
        if subtype is not None and not row.values[1]:
            row.set_argument(1, subtype.arguments[0])


def read_library_header(record, kind, units):
    if record.text('Type', 'DipTrace-'+kind+'Library') != 'DipTrace-'+kind+'Library':
        raise ValueError(f'{record.node.path}: expected a {kind.lower()} library')
    record.text('Version', '')
    return XmlUnits(record.text('Units', units.units))


def read_subfolders(record):
    """Read the ordered component-library folder names, when supplied."""
    source = record.take('SubFolders')
    if source is None:
        return None
    result = Element('Subfolders')
    for item in source.children('Item'):
        name = item.content()
        if name.kind != 'string':
            raise ValueError(f'{item.node.path}: expected a folder name')
        result.add('Folder', name)
        item.finish(allow_text=True)
    source.finish()
    return result
