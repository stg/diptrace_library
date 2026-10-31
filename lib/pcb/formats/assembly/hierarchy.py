"""Normalize schematic hierarchy linkage without opening a companion file."""
from ....common.structural_edits import assembly
from ....common.references import Key
from ...model import hierarchy_records, hierarchy
from ..errors import PcbError


def assemble_hierarchy(core):
    roots = []
    with assembly(core.document):
        for component in core.components.records:
            path = component.child('HierarchyPath')
            if path is None:
                continue
            # An unlinked object, via or mounting hole has no schematic path.
            if component['HiddenId'] < 0 or component.one('Pattern')['Type'] in (15, 16):
                for item in path.children():
                    item.detach()
            elif (steps := path.children()):
                # The final serialized entry repeats the component identity;
                # our path contains only the enclosing block instances.
                if steps[-1].values != (component['HiddenId'],):
                    raise PcbError('hierarchy path terminal differs from component schematic identity')
                steps[-1].detach()
            roots.append(path)
        if (sheets := core.document.one('/Board').child('HierarchySheets')) is not None:
            roots.append(sheets)
        for root in roots:
            for node in root.walk(include_self=True):
                if (schema := hierarchy_records.definition(node)) is not None:
                    node.bind_schema(schema)
        choices = {}
        for block in core.document.select('/Board/HierarchySheets/HSheet/UpdateIds/UId'):
            key = block['Id']
            choices[key] = block if key not in choices else None
        with core.document.references.binding_batch():
            for component in core.components.records:
                for step in component.select('HierarchyPath/Item'):
                    key = Key(step)
                    target = choices.get(step['Id'])
                    if target is None:
                        core.document.references.note(step,
                            hierarchy.BLOCK_ROLE+': unresolved or ambiguous block identifier', key,
                            collections=tuple(root for root in roots if root.kind == 'HierarchySheets'))
                    else:
                        core.document.references.bind(step, target, key, role=hierarchy.BLOCK_ROLE, preserve=True)
    return core
