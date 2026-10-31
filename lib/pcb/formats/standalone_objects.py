"""Data a receiving editor initializes for mounting holes and static vias."""
from functools import lru_cache

from ...common.conversion import import_notice, warn
from ...common.footprint_objects import new_model3d
from ...common.footprint_records import VECTORS


_COLLECTIONS = ('HierarchyPath', 'AssemblyExclude', 'InternalConnection_Records', 'IntConRecords')


@lru_cache(maxsize=1)
def _model_defaults():
    """An immutable recipe from the shared constructor, without per-via trees."""
    defaults = new_model3d()
    return (tuple(('', name, defaults[name]) for name in defaults.schema.fields)
            + tuple((name, axis, defaults.one(name)[axis]) for name in defaults.schema.children
                    for axis in defaults.one(name).schema.fields))


def _model_changed(model):
    return any(owner.get(name, value) != value for scope, name, value in _model_defaults()
               if (owner := model.child(scope) if scope else model) is not None)


def ignored_data(component):
    """Identify current authored values which the object's load rules ignore."""
    pattern = component.one('Pattern')
    if pattern['Type'] not in (15, 16):
        return ()
    data = [pattern.one(name) for name in ('OriginX', 'OriginY') if pattern.get(name, 0) != 0]
    data.extend(collection for name in _COLLECTIONS
                if (collection := component.child(name)) is not None and collection.children())
    model = pattern.child('Model3D')
    if pattern['Type'] == 16 and model is not None:
        if _model_changed(model):
            data.append(model)
    return tuple(data)


def normalize_component(component):
    """Initialize prepared input records before relationship binding.

    This does not change cached footprint definitions or apply editing policy
    to an already attached document. Its geometry and electrical pad identities
    remain in place; discarded selections are not a second source of truth.
    """
    pattern = component.one('Pattern')
    if pattern['Type'] not in (15, 16):
        return
    changed = bool(ignored_data(component))
    for name in ('OriginX', 'OriginY'):
        if pattern.child(name) is not None:
            pattern.set_field(name, 0)
    for name in _COLLECTIONS:
        if (collection := component.child(name)) is not None:
            for row in tuple(collection.children()):
                row.detach()
    if pattern['Type'] == 16 and (model := pattern.child('Model3D')) is not None:
        owners = {'': model}
        for scope, name, value in _model_defaults():
            if scope not in owners:
                owners[scope] = model.child(scope) or model.add(scope).bind_schema(VECTORS[scope])
            owners[scope].set_field(name, value)
    if changed:
        import_notice('info', 'standalone-object-data',
                      'Initialized origin and component-only settings for a standalone PCB object.',
                      (component,), recoverability='physical geometry and pad connections remain; a via has no 3D attachment')


def normalize_components(board):
    for component in board.select('Components/Component'):
        if component.get('Enabled', True) and component.one('Pattern')['Type'] in (15, 16):
            normalize_component(component)


def report_ignored_data(board, *, destination, report=None):
    for component in board.select('Components/Component'):
        if not component['Enabled'] or component.one('Pattern')['Type'] not in (15, 16):
            continue
        if (data := ignored_data(component)):
            warn(report, 'standalone-object-data', destination,
                 'A receiving editor clears component-only settings on mounting holes and vias', data,
                 recoverability='origins, hierarchy/assembly selections and authored pad pairs clear; vias also reset their 3D attachment')
