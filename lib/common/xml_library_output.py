"""Shared XML classification and library metadata projections."""
from .xml import set_attribute
from .xml_output import field
from .model import Element
from .conversion import warn


def report_slot_omissions(slots, *, destination, report=None):
    """Report metadata with no XML definition that can own it.

    XML keeps empty component entries, but paths belong to their Part or
    physical definitions. Never create a definition solely to carry a path.
    """
    paths, models = [], []
    for slot in slots:
        if not slot.children('Definition') and any(slot.get(name, '') for name in ('LibPath', 'VariablePath')):
            paths.append(slot)
        if slot.get('Model3DFile_Variable', ''):
            models.append(slot)
    if paths:
        warn(report, 'empty-library-path', destination,
             'XML omits library paths on slots without definitions', paths,
             recoverability='the empty slot remains; its library paths cannot be recovered from this output alone')
    if models:
        warn(report, 'unattached-model-path', destination,
             'XML omits independent 3D model paths on library slots', models,
             recoverability='physical definitions and their own model paths remain; the separate slot path is omitted')


def project_subfolders(cache):
    """Project ordered folder names; symbols retain their own folder indices."""
    rows = cache.select('Subfolders/Folder') if cache is not None else ()
    if not rows:
        return None
    result = Element('SubFolders')
    for row in rows:
        field(result, 'Item', row.scalar('Name'))
    return result


def project_category(part):
    prefix = 'Pattern_' if part.kind == 'Pattern' else 'Component_'
    name, index = part.scalar(prefix+'CategoryName'), part.scalar(prefix+'CategoryIndex')
    types = part.select(prefix+'CategoryTypes/CategoryType')
    if not name and index < 0 and not types:
        return None
    result = Element('Category')
    if index >= 0:
        set_attribute(result, 'Index', index)
    if name:
        field(result, 'Name', name)
    if types:
        target = result.add('CategoryTypes')
        for row in types:
            if len(row.arguments) != 4:
                raise ValueError(f'{row.path}: category type requires two names and two indices')
            type_name, subtype, type_id, subtype_id = row.arguments
            item = target.add('CategoryType')
            field(item, 'Type', type_name)
            set_attribute(item.one('Type'), 'Index', type_id)
            if subtype.value or subtype_id.value >= 0:
                child = field(item, 'SubType', subtype)
                set_attribute(child, 'Index', subtype_id)
    return result


def project_project_libraries(owner):
    """Serialize literal search paths without opening or discovering libraries."""
    result = Element('ProjectLibs')
    if (sorted_paths := owner.get('ProjectLibs_Sorted')) is not None:
        set_attribute(result, 'Sorted', sorted_paths)
    for own, public, kind in (('ProjectLibs_Folders', 'Folders', 'Folder'), ('ProjectLibs_Libs', 'Libs', 'Lib')):
        if (source := owner.child(own)) is not None:
            target = result.add(public)
            for path in source.children(kind):
                row = target.add(kind)
                field(row, 'Path', path['Path'])
                field(row, 'Var', path.get('VariablePath', ''))
    return result
