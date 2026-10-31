"""Picture sources are filenames, unresolved companion references or unassigned."""


def picture_reference_index(shape, index):
    """An authored filename takes precedence over a legacy companion-table key."""
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError(f'{shape.path}: BitmapIndex requires an integer')
    paths = tuple(shape.scalar(name, '') for name in ('Picture_File', 'Picture_File_Variable'))
    if any(not isinstance(path, str) for path in paths):
        raise TypeError(f'{shape.path}: picture filenames require text')
    return index if index >= 0 and not any(paths) else -1


def picture_source_paths(shape, *, filenames=None):
    """Return current literal paths and any unresolved companion-table key."""
    actual, variable = (shape.scalar(name, '') for name in ('Picture_File', 'Picture_File_Variable'))
    index = picture_reference_index(shape, shape.scalar('BitmapIndex', -1))
    if index >= 0 and filenames is not None and index < len(filenames) and filenames[index]:
        actual, index = filenames[index], -1
        if not isinstance(actual, str):
            raise TypeError('legacy picture filenames require text')
    return actual, variable, index


def prepare_picture_sources(shapes, *, destination, keep_legacy_indices=False, filenames=None, report=None):
    """Project sources on a detached view, without opening any resource files."""
    unresolved = []
    for shape in shapes:
        actual, _variable, index = picture_source_paths(shape, filenames=filenames)
        if actual != shape.scalar('Picture_File', ''):
            shape.set_field('Picture_File', actual)
        if index >= 0:
            unresolved.append(shape)
            if keep_legacy_indices:
                continue
        shape.set_field('BitmapIndex', -1)
    if unresolved:
        from .conversion import warn
        message = ('unresolved picture indices are retained; current application readers require picture filenames'
                   if keep_legacy_indices else
                   'unresolved companion picture references become unassigned picture sources')
        warn(report, 'unresolved-picture-reference', destination, message, unresolved,
             recoverability='supply a current Picture_File or an explicit legacy_picture_files table; authoring references remain intact')
