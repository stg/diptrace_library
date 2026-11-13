"""Read-only access to generated XML facts for destination reference audits.

The borrowed handles below are temporary validation state. They neither own
design facts nor offer editing, persistence or a second document model.
"""
from dataclasses import replace

from .xml_plan import XmlPlan
from .references import Reference, ReferenceError, References


class _Node:
    __slots__ = ('plan', 'parent', '_position', '_handles')
    schema = None

    def __init__(self, plan, parent=None, position=0):
        self.plan, self.parent, self._position = plan, parent, position
        self._handles = None

    @property
    def kind(self):
        return self.plan.kind

    @property
    def arguments(self):
        return self.plan.arguments

    @property
    def values(self):
        return tuple(value.value for value in self.arguments)

    @property
    def path(self):
        if self.parent is None:
            return ''
        return self.parent.path+'/'+self.kind+'['+str(self._position+1)+']'

    def _ordinal(self):
        return self._position

    def _argument_owner(self, argument):
        return self, argument

    def _children(self, kind=None, *, include_attributes=True):
        result, counts = [], {}
        attributes = self.plan.attributes
        for index in range(len(attributes)+len(self.plan.children)):
            name = (attributes[index][0] if index < len(attributes)
                    else self.plan.children[index-len(attributes)].kind)
            position = counts.get(name, 0)
            counts[name] = position+1
            if not include_attributes and index < len(attributes):
                continue
            if kind is not None and name != kind:
                continue
            node = self._handles.get(index) if self._handles is not None else None
            if node is None:
                plan = (XmlPlan(name, (attributes[index][1],)) if index < len(attributes)
                        else self.plan.children[index-len(attributes)])
                if self._handles is None:
                    self._handles = {}
                node = self._handles[index] = _Node(plan, self, position)
            result.append(node)
        return result

    def children(self, kind=None):
        return self._children(kind)

    def child(self, name):
        return next(iter(self.children(name)), None)

    def walk_elements(self, *, include_self=False):
        """Visit ordinary content without allocating handles for attributes."""
        if include_self:
            yield self
        for child in self._children(include_attributes=False):
            yield child
            yield from child.walk_elements()

    def scalar(self, name, default=None):
        # Most attributes need no handle. Reference slots acquire one only
        # when their identity is used by an audit specification.
        for key, value in self.plan.attributes:
            if key == name:
                return value.value
        for child in self.plan.children:
            if child.kind == name:
                return child.arguments[0].value if child.arguments else default
        return default

    def select(self, path):
        nodes = [self]
        for kind in path.strip('/').split('/'):
            nodes = [child for node in nodes for child in node.children(None if kind == '*' else kind)]
        return nodes

    def one(self, path):
        nodes = self.select(path)
        if len(nodes) != 1:
            raise ValueError(f'{self.path}: expected one projection at {path!r}')
        return nodes[0]


class _ReferenceAudit:
    """Check immutable projections with the editable graph's value rules.

    Unresolved slots remain explicit, just as in an inspectable XML view.
    There are no edit subscriptions or reverse indexes to maintain here.
    """
    __slots__ = ('_references', '_outgoing', '_slots', '_unresolved', 'issues')

    def __init__(self, document, specifications):
        self._references, self._outgoing = [], {}
        self._slots, self._unresolved, self.issues = set(), set(), []
        checker, orders = References(document), {}
        for source, target, role, indices, guards in specifications:
            slots = tuple((item.field, item.argument) for item in indices)
            reference = Reference('', source, target, role, tuple(indices), tuple(guards))
            message = None
            if target is None:
                message = f'{role}: target cannot be resolved'
            else:
                try:
                    if len(set(slots)) != len(slots) or self._slots.intersection(slots):
                        raise ReferenceError('an index slot already has a reference')
                    checker._check(reference)
                    positions, domains = checker._positions(reference, orders)
                except ReferenceError as error:
                    message = str(error)
            if message is not None:
                self._unresolved.update(slots)
                self.issues.append((source, message))
                continue
            for item, position, domain in zip(indices, positions, domains):
                expected = checker._projected_value(item, position, domain)
                if not checker._same_value(item.field.arguments[item.argument], expected):
                    raise ReferenceError(f'{role}: generated reference value disagrees with its target')
            self._slots.update(slots)
            self._references.append(reference)
            self._outgoing.setdefault((source, role), []).append(reference)

    def __iter__(self):
        return iter(self._references)

    def manages(self, field, argument=0):
        return (field, argument) in self._slots

    def unresolved_slot(self, field, argument=0):
        return (field, argument) in self._unresolved

    def outgoing(self, source, *, role):
        return self._outgoing.get((source, role), ())


class XmlProjection:
    """Lend immutable XML plans to the same format-specific reference checks."""
    __slots__ = ('root', 'references')

    def __init__(self, source):
        self.root = _Node(XmlPlan('Root', children=(source,)))
        self.references = None

    def one(self, path):
        return self.root.one(path)

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()

    def close(self):
        """Release borrowed ownership cycles before the output is rendered."""
        self.references = None
        pending = [self.root]
        while pending:
            node = pending.pop()
            if node._handles is not None:
                pending.extend(node._handles.values())
                node._handles = None

    def audit(self, specifications, validator):
        self.references = _ReferenceAudit(self, specifications(self))
        validator(self)
        return self.references.issues


class XmlPlanEdits:
    """Apply destination-only omissions to immutable generated XML facts.

    Reads and diagnostic paths describe the original projection. Only changed
    branches are rebuilt; unchanged plans and typed values remain shared.
    This private helper is not an editing interface for authored designs.
    """
    __slots__ = ('root', '_view', '_removed', '_changed')

    def __init__(self, plan, *, detached=False):
        self._view = XmlProjection(plan)
        self.root = self._view.root.child(plan.kind)
        if detached:
            self.root.parent = None
            self._view.root = self.root
        self._removed, self._changed = {}, set()

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self._view.close()
        self._removed.clear()
        self._changed.clear()

    def omit(self, node, name):
        ancestor = node
        while ancestor is not None and ancestor is not self.root:
            ancestor = ancestor.parent
        if ancestor is None:
            raise ValueError('omission requires a node from this XML projection')
        fields = node.children(name)
        if len(fields) > 1:
            raise ValueError(f'{node.path}: expected one generated XML field {name}')
        if fields:
            self._removed.setdefault(node, set()).add(name)
            while node is not None and node not in self._changed:
                self._changed.add(node)
                node = node.parent

    def finish(self):
        def build(node):
            if node not in self._changed:
                return node.plan
            omitted = self._removed.get(node, ())
            attributes = tuple((name, value) for name, value in node.plan.attributes if name not in omitted)
            children, offset = [], len(node.plan.attributes)
            for index, child in enumerate(node.plan.children):
                if child.kind in omitted:
                    continue
                handle = node._handles.get(offset+index) if node._handles is not None else None
                children.append(build(handle) if handle in self._changed else child)
            return replace(node.plan, attributes=attributes, children=tuple(children))
        return build(self.root)
