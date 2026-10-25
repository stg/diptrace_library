"""Owned library slots and definition variants shared by design families."""
from .schema import Child, Field, Record


SLOT = Record('LibrarySlot', {
    'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                    ordinal_dependencies=lambda node: (node,),
                    description='Current zero-based library slot position.'),
    'LibPath': Field('LibPath', 'text', required=True, default='',
                      description='Library path associated with this slot.'),
    'VariablePath': Field('VariablePath', 'text', default=''),
    'Model3DFile_Variable': Field('Model3DFile_Variable', 'text', default='',
                                 description='Model path retained on a slot without a definition.'),
}, ('Index', 'LibPath'), children={'Definition': Child('Definition', 'LibraryDefinition', maximum=None)})

DEFINITION = Record('LibraryDefinition', {
    'Index': Field('Index', 'integer', getter=lambda node: node._ordinal(),
                    ordinal_dependencies=lambda node: (node,),
                    description='Current zero-based variant position within its library slot.'),
}, ('Index',), children={'Part': Child('Part', 'CachedPart'), 'Pattern': Child('Pattern', 'Pattern')})


CACHE = Record('CacheLibrary', {}, children={
    name: Child(name, record) for name, record in (
        ('Categories', 'Categories'), ('PatternCategories', 'Categories'), ('Subfolders', 'Subfolders'),
        ('Slots', 'Slots'), ('Patterns', 'Patterns'), ('PadStyles', 'PadStyles'))
})
SLOTS = Record('Slots', {}, children={'Slot': Child('Slot', SLOT.name, maximum=None)})

DESIGN_LINK = Record('DesignCacheLink', {
    'SlotIndex': Field('SlotIndex', 'integer', required=True, default=-1,
                       description='Managed library-slot index in the active prefix; a literal capacity value beyond it.'),
}, ('SlotIndex',))
DESIGN_LINKS = Record('DesignCacheLinks', {},
    description='An ordered collection of DesignCacheLink records.',
    children={'Link': Child('Link', DESIGN_LINK.name, maximum=None)})
