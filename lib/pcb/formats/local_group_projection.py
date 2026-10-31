"""Project local identities without binding a missing selector to another group."""
from ...common.conversion import warn
from ..model.local_groups import owner


def reserved(owner):
    return {node['UnresolvedGroupId'] for node in owner.walk(include_self=True)
            if node.child('UnresolvedGroupId') is not None}


def selection(node, *, destination, report=None, keys=None):
    missing = node.get('UnresolvedGroupId')
    if missing is not None:
        result = missing
        context = owner(node)
        collection = 'Groups' if context.kind == 'Part' else 'Pattern_Groups'
        count = len(context.select(collection+'/pt'))
        if destination != 'dipxml' and missing < count:
            result = -1
        warn(report, 'unresolved-local-group', destination,
             'Local group selection has no current target', (node,),
             recoverability=('the unavailable selector remains in output' if result == missing else
                             'output is unassigned to avoid binding the missing key to another group'))
        return result
    if keys is None:
        return node['GroupId']
    selected = node['Group']
    return -1 if selected is None else keys[selected]
