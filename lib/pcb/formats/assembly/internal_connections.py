"""Consume source pad keys for authored component connection definitions.

Effective connection groups and their routing data are a later modernization
stage. This module binds the independent authored pair definitions only.
"""
from ....common.structural_edits import assembly
from ...model import internal_connections as model
from ..errors import PcbError


def assemble_definitions(core):
    prepared = []
    for component in core.components.records:
        collection = component.child('InternalConnection_Records')
        if collection is None:
            continue
        for pair in collection.children():
            targets = tuple(core.component_pads[component].get(number) for number in pair.values)
            if len(targets) != 2 or any(target is None for target in targets):
                raise PcbError('unresolved internal connection pad definition')
            prepared.append((pair, targets))
    with assembly(core.document):
        for component in core.components.records:
            collection = component.child('InternalConnection_Records')
            if collection is not None:
                collection.kind = 'IntConRecords'
                collection.bind_schema(model.DEFINITIONS)
            else:
                component.add('IntConRecords').bind_schema(model.DEFINITIONS)
        for pair, targets in prepared:
            pair.kind = 'Item'
            pair.set_values()
            pair.bind_schema(model.PAIR)
        with core.document.references.binding_batch():
            for pair, targets in prepared:
                for role, target in zip(model.ROLES, targets):
                    core.document.references.bind(pair, target, role=role, preserve=True)
    return core
