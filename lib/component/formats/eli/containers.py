"""Component library organization before the component/part payload.

This is an incomplete internal decoder, not a public document reader. The
serialized entry count follows catalogues and folders; it is not a header slot.
"""
from dataclasses import dataclass, replace

from ....common.catalog_codec import read_categories
from ....common.library_binary import LibraryHeader
from ....common.model import Element


@dataclass(frozen=True)
class Container:
    header: LibraryHeader
    library: Element
    body_start: int


def read_container(reader):
    version = reader.header.version
    library = Element('Library')
    library.add('Name', reader.header.name)
    library.add('Hint', reader.header.hint)
    if version >= 33:
        reader.take(4)  # Fresh serialization bookkeeping, not an authored identity.
    if version >= 24:
        read_categories(reader, library)
    else:
        library.add('Categories')
    folders = reader.add(library, 'Subfolders')
    for _ in range(reader.count('library subfolders')):
        reader.record(folders, 'Folder', 'text')
    count = reader.count('library components')
    for node in library.walk(include_self=True):
        if (record := reader.record_definition(node)) is not None:
            node.bind_schema(record)
    return Container(replace(reader.header, entry_count=count), library, reader.pos)
