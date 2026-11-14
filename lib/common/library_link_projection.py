"""Detached positional adaptation of unavailable standalone-library targets."""
from .conversion import warn
from .structural_edits import assembly
from . import unplaced_footprint_records as physical


REFERENCE_FIELDS = {
    physical.GROUP_ROLE: 'Group', physical.PAD_ROLE: 'Pad',
    **dict(zip(physical.CONNECTION_ROLES, ('Pad1', 'Pad2'))),
}


def check_issues(document, *, roles=()):
    supported = {*REFERENCE_FIELDS, *physical.DIMENSION_ROLES, *roles}
    for issue in document.references.issues:
        role = issue.message.partition(':')[0]
        if role not in supported:
            raise NotImplementedError('unavailable library relationship has no output mapping: '+role)


def report_xml_catalogue_projection(document, *, destination, report=None):
    """Expose XML's label-based adaptation of unresolved catalogue selections."""
    from .library_catalogue import ROLES, CATEGORY_ROLE
    sources = tuple(dict.fromkeys((
        *(issue.source for issue in document.references.issues if issue.message.partition(':')[0] in ROLES),
        *(link.source for link in document.references if link.role == CATEGORY_ROLE and not link.target['Name']))))
    if sources:
        warn(report, 'library-catalogue-selection', destination,
             'XML output adapts unavailable, conflicting or unnamed catalogue selections through named definitions.', sources,
             recoverability='the source selections remain; choose named definitions for unambiguous XML output')


def prepare_positional_links(document, *, destination, report=None, roles=None, retained_roles=()):
    """Leave unavailable targets unassigned; never bind them by coincident slot.

    Public keyed outputs can reserve missing keys. Positional formats cannot
    represent every missing key without selecting an unrelated current member.
    The caller supplies a detached view; all authored source facts stay intact.
    """
    roles = {**REFERENCE_FIELDS, **(roles or {})}
    removed_pairs = {}
    for issue in tuple(document.references.issues):
        if issue not in document.references.issues:
            continue
        role = issue.message.partition(':')[0]
        source = issue.source
        if role in retained_roles:
            continue
        if role in physical.CONNECTION_ROLES:
            removed_pairs[source] = None
            continue
        if role in physical.DIMENSION_ROLES:
            side = role[-1]
            if source['Connected'+side] not in (0, 1, 2, 3):
                raise NotImplementedError('unavailable dimension mode has no positional mapping')
            document.references.discard_issue(issue)
            with assembly(document):
                for name in ('Connected', 'Object', 'SubObject', 'Point'):
                    source[name+side] = -1
        elif role in roles:
            source[roles[role]] = None
        else:
            raise NotImplementedError('unavailable library relationship has no output mapping: '+role)
        warn(report, 'unresolved-local-reference', destination,
             'An unavailable local target exports as unassigned.', (source,),
             recoverability='the unresolved selection remains in the source model; geometry and text are retained')
    for pair in removed_pairs:
        warn(report, 'unresolved-internal-connection', destination,
             'An internal connection with an unavailable pad is omitted.', (pair,),
             recoverability='the source connection and missing selection remain editable')
        for issue in tuple(document.references._source_issues(pair)):
            document.references.discard_issue(issue)
        for reference in tuple(document.references.outgoing(pair)):
            document.references.discard(reference)
        pair.detach()
    document.validate()
