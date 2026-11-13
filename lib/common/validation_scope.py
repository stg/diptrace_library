"""Reuse an initial audit during library-owned, detached preparation.

This is not a user transaction or a persistent validation cache. The caller owns
an isolated view and uses model mutators throughout the scope. Every fact is
audited on entry. Mutations identify records/ancestors to check again, and new
owned subtrees receive complete checks. Reference checks remain whole-document.
Public validation never consults this scope.
"""
from contextvars import ContextVar

from .element_storage import RecordItems


_active = ContextVar('design_checked_preparation', default=None)


class checked_edits:
    """Audit an adapter-owned view before and after controlled preparation.

    Raw content/parent/identity writes are not an editing interface inside this
    private scope. Use model mutators; callers must discard the view on failure.
    """
    def __init__(self, document, *, force=True):
        self.document, self.force = document, force
        self.changed, self.incoming = set(), set()
        self.identities_changed = False
        self._token = None

    def __enter__(self):
        if self.document._automatic_structure:
            raise ValueError('checked preparation requires an adapter-owned view')
        previous = _active.get()
        if previous is not None and previous.document is self.document:
            raise ValueError('checked preparation cannot nest on the same document')
        self.document._synchronize(force=False)
        self._token = _active.set(self)
        return self

    def __exit__(self, error_type, error, traceback):
        _active.reset(self._token)
        if error_type is None:
            self._finish()

    def _finish(self):
        self._validate_changes()
        if self.document._reference_validator:
            self.document._reference_validator(self.document)
        self.document.references.synchronize(force=self.force)
        self.document._identity_index = None

    def touch(self, node):
        if node._owner() is self.document:
            while node is not None:
                self.changed.add(node)
                node = node._parent

    def attach(self, parent, node, *, incoming=True):
        if parent._owner() is self.document:
            self.touch(parent)
            if incoming:
                self.incoming.add(node)

    def identity(self, node):
        if node._owner() is self.document:
            self.identities_changed = True

    def schema(self, node):
        if node._owner() is self.document:
            self.touch(node)
            # Rebinding may move observed field identities between layouts.
            self.identities_changed = True

    def _owned(self, node):
        seen = set()
        while node._parent is not None:
            if node in seen:
                raise ValueError('a parent cycle is not part of a document')
            seen.add(node)
            node = node._parent
        return node is self.document.root

    def _children(self, node):
        children = node._audit_owned_content()
        seen = set()
        for child in children:
            if child in seen:
                raise ValueError('an element occurs more than once in the document')
            seen.add(child)
            if child.parent is not node:
                raise ValueError(f'inconsistent parent for {child.uid}')
        return children

    def _validate_changes(self):
        nodes = {node for node in self.changed if self._owned(node)}
        visited = set()
        pending = [node for node in self.incoming if self._owned(node)]
        while pending:
            node = pending.pop()
            if node in visited:
                continue
            visited.add(node)
            nodes.add(node)
            content = node._content
            if node._uid is not None or type(content) is RecordItems and content.identities:
                self.identities_changed = True
            pending.extend(self._children(node))
        if self.identities_changed:
            # New observed IDs, imported IDs or a rebound layout need the global
            # identity/ownership audit, including nonmaterialized field IDs.
            for _ in self.document._audit_nodes():
                pass
        else:
            for node in nodes - visited:
                self._children(node)
        for node in nodes:
            self.document._validate_record(node)


def _finish_removals(document, parents):
    """Finish known removals after the caller's successful whole-model audit.

    The intervening operation must only detach children with model mutators.
    Remaining descendants retain their audited contents/identities. Parents and
    ancestors need fresh content/cardinality checks; all links are checked and
    reprojected. This is not a validation shortcut for arbitrary editing.
    """
    changes = checked_edits(document)
    for parent in parents:
        changes.touch(parent)
    changes._finish()
