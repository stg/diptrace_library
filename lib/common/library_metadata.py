"""Named catalogue, classification and path records shared by design families."""
from dataclasses import replace

from .schema import Child, Field, Record
from .library_records import DESIGN_LINK, DESIGN_LINKS


def _row(name, fields):
    return Record(name, {field.name: field for field in fields}, tuple(field.name for field in fields))


def _collection(name, kind, record):
    return Record(name, {}, description='An ordered collection of '+record+' records.',
                  children={kind: Child(kind, record, maximum=None)})


CATEGORY_TYPE = _row('CategoryType', (
    Field('Type', 'text', required=True, default='', description='Classification type name.'),
    Field('SubType', 'text', required=True, default='', description='Classification subtype name.'),
    Field('TypeIndex', 'integer', required=True, default=-1, description='Declared type key.'),
    Field('SubTypeIndex', 'integer', required=True, default=-1, description='Declared subtype key.'),
))
CATALOG_ENTRY = _row('CatalogEntry', (
    Field('Name', 'text', required=True, default=''),
    Field('Index', 'integer', required=True, default=-1,
          description='Declared catalog key; independent of collection position.'),
))
CATALOG_CATEGORY = replace(CATALOG_ENTRY, name='CatalogCategory', children={
    'Type': Child('Type', 'CatalogType', maximum=None)})
CATALOG_TYPE = replace(CATALOG_ENTRY, name='CatalogType', children={
    'Subtype': Child('Subtype', 'CatalogSubtype', maximum=None)})
CATALOG_SUBTYPE = replace(CATALOG_ENTRY, name='CatalogSubtype')
LIBRARY_PATH = Record('LibraryPath', {
    'Path': Field('Path', 'text', required=True, default=''),
    'VariablePath': Field('VariablePath', 'text', default=''),
}, ('Path',))
SUBFOLDER = _row('LibrarySubfolder', (Field('Name', 'text', required=True, default=''),))
POSSIBLE_NAME = _row('PossibleName', (Field('Name', 'text', required=True, default=''),))
MODEL_LINE = _row('ModelLine', (Field('Text', 'text', required=True, default=''),))

CLASSIFICATIONS = _collection('Classifications', 'CategoryType', CATEGORY_TYPE.name)
POSSIBLE_NAMES = _collection('PossibleNames', 'PossibleName', POSSIBLE_NAME.name)
PROJECT_FOLDERS = _collection('ProjectFolders', 'Folder', LIBRARY_PATH.name)
PROJECT_LIBRARIES = _collection('ProjectLibraries', 'Lib', LIBRARY_PATH.name)
CATEGORIES = _collection('Categories', 'Category', CATALOG_CATEGORY.name)
SUBFOLDERS = _collection('Subfolders', 'Folder', SUBFOLDER.name)
MODEL_BODY = _collection('ModelBody', 'Line', MODEL_LINE.name)


def modernize_classifications(root):
    """Use one row kind for cached, placed and public text classifications."""
    for node in root.walk(include_self=True):
        if (node.kind in ('Type', 'Component_Type', 'Pattern_Type') and node.parent is not None and
                node.parent.kind in ('Component_CategoryTypes', 'Pattern_CategoryTypes')):
            node.kind = 'CategoryType'


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    name, owner = node.kind, parent.kind
    if name == 'DesignCache_Links' and owner in ('Board', 'Schematic'):
        return DESIGN_LINKS
    if name == 'Link' and owner == 'DesignCache_Links':
        return DESIGN_LINK
    if name in ('Component_CategoryTypes', 'Pattern_CategoryTypes') and owner in ('Part', 'Pattern', 'Component'):
        return CLASSIFICATIONS
    if name == 'CategoryType' and owner in ('Component_CategoryTypes', 'Pattern_CategoryTypes'):
        return CATEGORY_TYPE
    if name == 'PossibleNames' and owner == 'Pattern':
        return POSSIBLE_NAMES
    if name == 'PossibleName' and owner == 'PossibleNames':
        return POSSIBLE_NAME
    if name in ('Categories', 'PatternCategories') and owner == 'CacheLib':
        return CATEGORIES
    if name == 'Category' and owner in ('Categories', 'PatternCategories'):
        return CATALOG_CATEGORY
    if name == 'Type' and owner == 'Category':
        return CATALOG_TYPE
    if name == 'Subtype' and owner == 'Type':
        return CATALOG_SUBTYPE
    if name == 'Subfolders' and owner == 'CacheLib':
        return SUBFOLDERS
    if name == 'Folder' and owner == 'Subfolders':
        return SUBFOLDER
    if owner in ('Board', 'Schematic') and name in ('ProjectLibs_Folders', 'ProjectLibs_Libs'):
        return PROJECT_FOLDERS if name == 'ProjectLibs_Folders' else PROJECT_LIBRARIES
    if name in ('Folder', 'Lib') and owner in ('ProjectLibs_Folders', 'ProjectLibs_Libs'):
        return LIBRARY_PATH
    if name == 'ModelBody' and owner == 'Part':
        return MODEL_BODY
    if name == 'Line' and owner == 'ModelBody':
        return MODEL_LINE
    return None


def consume_count(node, schema):
    """Discard a serialized collection length after checking its actual rows."""
    if schema in (CLASSIFICATIONS, POSSIBLE_NAMES, PROJECT_FOLDERS, PROJECT_LIBRARIES, DESIGN_LINKS) and node.values:
        if (len(node.arguments) != 1 or node.arguments[0].kind != 'number' or
                node.arguments[0].unit or node.values[0] != len(node.children())):
            raise ValueError(f'{node.path}: collection count does not match rows')
        node.set_values()
