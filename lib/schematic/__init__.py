"""Schematic document I/O, constructors and configuration.

Exports resolve lazily because the generic entry point also imports the model
while its package is initializing.
"""
from importlib import import_module

_SCOPED = frozenset(('format_capabilities', 'parse', 'parse_source', 'read',
                     'read_source', 'serialize', 'write'))
__all__ = [
    *_SCOPED, 'Document', 'ImportContext', 'ExportContext', 'AscExportContext',
    'DchExportContext', 'DchXmlExportContext', 'schematic_schema', 'new_document',
    'new_schematic', 'new_symbol', 'new_pin', 'new_schematic_shape', 'new_net', 'new_wire',
]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    api = import_module('..', __name__)
    value = getattr(api, 'new_schematic' if name == 'new_document' else name)
    if name in _SCOPED:
        value = api._for_family(value, 'schematic')
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
