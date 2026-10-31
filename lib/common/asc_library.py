"""Shared ASC library catalogues and explicit project path pairs."""
from .model import Element, Value


def unprefix(cache):
    for node in cache.walk(include_self=True):
        if node.kind.startswith('cl_'):
            node.kind = node.kind[3:]


def rows(owner, kind):
    children = owner.children()
    if any(row.kind != kind for row in children):
        raise ValueError(f'{owner.path}: expected {kind} records')
    return children


def _count(owner, count):
    if (len(owner.arguments) != 1 or owner.arguments[0].kind != 'number'
            or owner.arguments[0].unit or owner.values[0] != count):
        raise ValueError(f'{owner.path}: invalid catalog record count')
    owner.set_values()


def unpack_catalogs(cache):
    """Consume only catalogue counts, retaining declared keys and ordering."""
    categories, folders = cache.one('Categories'), cache.one('Subfolders')
    _count(categories, len(rows(categories, 'Category')))
    _count(folders, len(rows(folders, 'Subfolder')))
    for category in categories.children():
        types = rows(category, 'Type')
        if len(category.arguments) != 3 or category.values[2] != len(types):
            raise ValueError(f'{category.path}: invalid category type count')
        category.set_values(*category.arguments[:2])
        for kind in types:
            subtypes = rows(kind, 'SubType')
            if len(kind.arguments) != 3 or kind.values[2] != len(subtypes):
                raise ValueError(f'{kind.path}: invalid category subtype count')
            kind.set_values(*kind.arguments[:2])
            for subtype in subtypes:
                if subtype.children() or len(subtype.arguments) != 2:
                    raise ValueError(f'{subtype.path}: unsupported category subtype')
                subtype.kind = 'Subtype'
    for folder in folders.children():
        if folder.children() or len(folder.arguments) != 1:
            raise ValueError(f'{folder.path}: unsupported cache subfolder')
        folder.kind = 'Folder'


def unpack_project_paths(owner):
    """Own each variable expression beside its literal path, without discovery."""
    for name, kind in (('ProjectLibs_Folders', 'Folder'), ('ProjectLibs_Libs', 'Lib')):
        container = owner.child(name)
        if container is None:
            continue
        records = container.children()
        if len(records) % 2:
            raise ValueError(f'{container.path}: expected actual/variable path pairs')
        if container.values:
            _count(container, len(records)//2)
        for actual, variable in zip(records[::2], records[1::2]):
            if (actual.kind != kind or variable.kind != kind+'_Variable' or
                    len(actual.arguments) != 1 or actual.children() or
                    len(variable.arguments) != 1 or variable.children() or
                    any(value.kind != 'string' for value in (*actual.arguments, *variable.arguments))):
                raise ValueError(f'{container.path}: expected {kind}/{kind}_Variable siblings')
            variable.kind = 'VariablePath'
            variable.move_to(actual)


def _children(node):
    parameters = node.schema.parameters if node.schema is not None else ()
    return [child for child in node.children() if child.kind not in parameters]


def project_library_paths(container, kind, *, convert=lambda value: value,
                          visible=_children, variable_fallback=False):
    """Flatten owned path pairs; the caller chooses any dialect fallback."""
    records = visible(container)
    if any(record.kind != kind for record in records):
        raise ValueError(f'{container.path}: expected only {kind} records')
    output = Element(container.kind, len(records))
    for record in records:
        if (len(record.arguments) != 1 or record.arguments[0].kind != 'string' or
                any(child.kind != 'VariablePath' for child in visible(record))):
            raise ValueError(f'{record.path}: expected a path and optional VariablePath')
        path, variable = record.arguments[0], record.scalar('VariablePath', '')
        if variable_fallback and not variable.replace(' ', ''):
            variable = path.value
        output.add(kind, convert(path))
        output.add(kind+'_Variable', convert(Value.of(variable)))
    return output


def project_catalogs(cache, *, convert=lambda value: value, visible=_children):
    """Generate catalogue counts, retaining declared names, keys and row order."""
    def project(parent, kind, public, child_kind=None):
        members = visible(parent)
        if any(member.kind != kind for member in members):
            raise ValueError(f'{parent.path}: expected only {kind} records')
        for member in members:
            expected = 1 if kind == 'Folder' else 2
            if len(member.arguments) != expected:
                raise ValueError(f'{member.path}: invalid catalogue row')
            row = Element(public, *(convert(value) for value in member.arguments))
            if child_kind is not None:
                children = tuple(project(member, child_kind,
                    'cl_Type' if child_kind == 'Type' else 'cl_SubType',
                    'Subtype' if child_kind == 'Type' else None))
                row.set_values(*row.arguments, len(children))
                for child in children:
                    row.append(child)
            elif visible(member):
                raise ValueError(f'{member.path}: unexpected catalogue children')
            yield row
    output = Element('CacheLib')
    for name, kind, public, child in (('Categories','Category','cl_Category','Type'),
                                     ('Subfolders','Folder','cl_Subfolder',None)):
        source = cache.child(name)
        members = () if source is None else tuple(project(source, kind, public, child))
        target = output.add('cl_'+name, len(members))
        for row in members:
            target.append(row)
    return output
