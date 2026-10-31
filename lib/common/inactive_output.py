"""Shared diagnostics for inactive content omitted by a destination policy."""
from .conversion import info, warn


def report_omitted_records(nodes, *, destination, report=None, rule='inactive-records', empty_drawing=None):
    """Let the owning domain distinguish unused slots from meaningful content."""
    empty, content = [], []
    for node in nodes:
        (empty if empty_drawing is not None and empty_drawing(node) else content).append(node)
    if empty:
        info(report, 'inactive-empty-drawings', destination, 'empty inactive drawing slots are omitted', empty,
             recoverability='no drawing, text or association is lost; unused slot attributes remain in the authoring model')
    if content:
        warn(report, rule, destination, 'inactive records are omitted from this export view', content,
             recoverability='inactive states and content remain in the authoring model')
