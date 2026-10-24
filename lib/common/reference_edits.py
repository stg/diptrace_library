"""Prospective relationship queries for atomic graph mutation planning."""
from contextlib import contextmanager
from contextvars import ContextVar


_pending = ContextVar('design_prospective_references', default=None)


def pending_changes(graph):
    state = _pending.get()
    return state[1] if state is not None and state[0] is graph else None


@contextmanager
def preview_references(graph, changes):
    combined = dict(pending_changes(graph) or ())
    combined.update(changes)
    token = _pending.set((graph, combined))
    try:
        yield
    finally:
        _pending.reset(token)
