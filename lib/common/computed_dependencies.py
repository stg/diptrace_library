"""Private reverse indexes for declared dependencies of calculated fields."""


class ComputedDependencies:
    def __init__(self):
        self._entries = {}
        self._ordinals = {}
        self._collections = {}
        self._relationships = {}
        self._nodes = {}

    def discard(self, owner):
        previous = self._entries.pop(owner, ((), (), (), ()))
        for index, keys in zip((self._ordinals, self._collections, self._relationships, self._nodes), previous):
            for key in keys:
                bucket = index[key]
                del bucket[owner]
                if not bucket:
                    del index[key]

    def update(self, owner, fields, *, ordinals=()):
        ordinals, relationships, collections = set(ordinals), set(), set()
        for node, definition in fields:
            if definition.ordinal_dependencies is not None:
                ordinals.update(definition.ordinal_dependencies(node))
            if definition.reference_dependencies is not None:
                relationships.update(definition.reference_dependencies(node))
            if definition.collection_dependencies is not None:
                collections.update(definition.collection_dependencies(node))
        collections.update((node.parent, node.kind) for node in ordinals)
        entries = ordinals, collections, relationships, ordinals | {key[0] for key in (*relationships, *collections)}
        if self._entries.get(owner) == entries:
            return
        self.discard(owner)
        if any(entries):
            self._entries[owner] = entries
            for index, keys in zip((self._ordinals, self._collections, self._relationships, self._nodes), entries):
                for key in keys:
                    index.setdefault(key, {})[owner] = None

    def ordinal_users(self, node):
        return self._ordinals.get(node, ())

    def node_users(self, node):
        return self._nodes.get(node, ())

    def collection_users(self, parent, kind):
        return self._collections.get((parent, kind), ())

    def relationship_users(self, reference):
        target = reference.target
        targets = (target.start, target.end) if hasattr(target, 'start') else (target,)
        keys = ((reference.source, reference.role, 'outgoing'),
                *((node, reference.role, 'incoming') for node in targets))
        users = set()
        for node, role, direction in keys:
            users.update(self._relationships.get((node, role, direction), ()))
            users.update(self._relationships.get((node, '', direction), ()))
        return users
