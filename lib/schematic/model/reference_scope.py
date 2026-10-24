"""Choose affected reference sources without traversing unrelated design data."""


class OrdinalLookup:
    """Authored reference numbers address the current ordered model view."""
    def __init__(self, records):
        self.records = records

    def get(self, number, default=None):
        try:
            position = int(number)
        except (ValueError, TypeError, OverflowError):
            return default
        if isinstance(number, bool) or position != number or not 0 <= position < len(self.records):
            return default
        return self.records[position]


class ReferenceScope:
    def __init__(self, root, *, additional=()):
        roots = (root, *additional)
        self.nodes = frozenset(node for owner in roots for node in owner.walk(include_self=True))
        self._kinds = {}
        self._included_references = set()
        self._expanded_sources = {}
        seen = set()
        for root in roots:
            for node in root.walk(include_self=True):
                self._add_ancestors(node, seen)

    def _add_ancestors(self, node, seen):
        while node is not None and node not in seen:
            seen.add(node)
            self._kinds.setdefault(node.kind, []).append(node)
            node = node.parent

    def select(self, owner, path):
        if owner is None:
            return ()
        if (owner, path) in self._expanded_sources:
            return owner.select(path)
        names = path.split('/')
        result = []
        for node in self._kinds.get(names[-1], ()):
            ancestor = node
            for name in reversed(names):
                if ancestor is None or ancestor.kind != name:
                    break
                ancestor = ancestor.parent
            else:
                if ancestor is owner:
                    result.append(node)
        return result

    def affects(self, specification):
        source, _, role, indices, guards = specification
        return ((source, role) in self._included_references or source in self.nodes or
                any(item is not None and item.field in self.nodes for item in indices)
                or any(guard.field in self.nodes for guard in guards))

    def include_reference(self, source, role):
        self._included_references.add((source, role))

    def include_children(self, owner, path):
        self._expanded_sources[owner, path] = True


def select(owner, path, scope=None):
    if owner is None:
        return ()
    return scope.select(owner, path) if scope is not None else owner.select(path)
