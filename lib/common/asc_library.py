"""Shared ASC library catalogues and explicit project path pairs."""


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
