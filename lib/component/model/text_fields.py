"""Identity-backed placement choices without rewriting authored symbol text."""
from ...common.field_edits import preview_slots, prepare_reference_edit
from ...common.reference_edits import assign_indexed_reference
from ...common.references import Index, ReferenceError
from ...common.schema import Field
from .metadata import component_of


ROLE = 'component-text-user-field'


def selected(source):
    document = source._owner()
    if document is None:
        return None
    links = document.references.outgoing(source, role=ROLE)
    if len(links) > 1:
        raise ReferenceError('text has several user-field selections')
    # A prospective replacement is authoritative during atomic edit planning.
    if links:
        return links[0].target
    if source.get('FontType', 0) >= 20 and any(issue.message.startswith(ROLE+':')
            for issue in document.references._source_issues(source)):
        raise ReferenceError('text selects an unavailable component user field')
    return None


def assign(source, target):
    if target is None and source.get('FontType', 0) < 20:
        return
    assign_indexed_reference(source, target, role=ROLE, field_name='FontType', offset=20, none_value=0)


SELECTION = Field('UserField', 'reference', nullable=True, getter=selected, setter=assign,
    description='Component user field selected for placement; clearing selects literal template text.',
    reference_dependencies=lambda source: ((source, ROLE, 'outgoing'),),
    value_dependencies=lambda source: ((source, 'FontType'),) if source.child('FontType') is not None else (),
    collection_dependencies=lambda source: ((source, 'FontType'),))


def plans(document, nodes):
    """Prepare only newly meaningful selectors in a prospective ownership scope."""
    from .symbols import DRAWING
    specifications, issues = [], []
    graph = document.references
    for source in nodes:
        if source.schema is not DRAWING or source['Type'] != 10 or source.get('FontType', 0) < 20:
            continue
        if graph.outgoing(source, role=ROLE) or any(issue.message.startswith(ROLE+':')
                for issue in graph._source_issues(source)):
            continue
        component = component_of(source)
        if component is None:
            raise ReferenceError('attach selected text inside a component')
        collection = component.one('UserFields')
        fields = collection.children('UserField')
        index = source['FontType']-20
        indices = (Index(source.one('FontType'), offset=20),)
        if index < len(fields):
            specifications.append((source, fields[index], ROLE, indices, ()))
        else:
            issues.append((source, ROLE+': unavailable field '+str(index), indices, (collection,), ()))
    return specifications, issues


def prepare_edit(document, source, field, values, *, created, base):
    with preview_slots(base.projections.values):
        specifications, issues = plans(document, (source,))
    return prepare_reference_edit(document, source, field, values, created=created, base=base,
                                  specifications=specifications, issues=issues)


def bind_imported(document):
    """Establish selectors once after the importer's schemas are complete."""
    specifications, issues = plans(document, document.root._record_walk(include_self=True))
    for source, target, role, indices, guards in specifications:
        document.references.bind(source, target, *indices, role=role, guards=guards, preserve=True)
    for source, message, indices, collections, guards in issues:
        document.references.note(source, message, *indices, collections=collections, guards=guards)
