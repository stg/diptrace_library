"""Supplied design-check snapshots and their current object relationships.

Editing an object does not recompute a stored check. Object selectors are managed
by the reference graph; measured values and the recorded threshold stay supplied
data until the caller replaces or removes that result.
"""
from ...common.references import ReferenceError
from ...common.reference_edits import resolve_unavailable_reference
from ...common.schema import Child, Field, Record
from .relationships import assign, linked, optional_reference_fields
from . import length_matching


OBJECT_ROLES = ('drc-object-1', 'drc-object-2')
CLASS_ROLES = ('drc-class-1', 'drc-class-2')
PAD_TYPES = (4, 6, 9, 10, 13, 20)
HOLE_TYPES = (5, 11)
TRACE_TYPES = (0, 3, 12, 16)
SHAPE_TYPES = (2, 8, 14, 15, 19)
PANEL_HOLE_TYPES = (22, 23)
PAUSED_TYPES = (24, 25, 26, 27)
TARGET_TYPES = frozenset((*PAD_TYPES, *HOLE_TYPES, *TRACE_TYPES, *SHAPE_TYPES,
                          *PANEL_HOLE_TYPES, *PAUSED_TYPES, 1, 7, 17, 18, 21))


def _selected(row, role, missing):
    if row.child(missing) is not None:
        raise ReferenceError(f'{role}: unresolved target')
    return linked(row, role)


def _set_selected(row, role, missing, target):
    unavailable = row.child(missing)
    if unavailable is None:
        assign(row, role, target)
    else:
        resolve_unavailable_reference(row, target, role=role, missing=unavailable)


def _dependencies(role, missing, names):
    return dict(reference_dependencies=lambda row: ((row, role, 'outgoing'),),
        collection_dependencies=lambda row: ((row, missing),),
        value_dependencies=lambda row: tuple((node, name) for name in names)
            if (node := row.child(missing)) is not None else ())


def _selectors(target):
    values = dict.fromkeys(('Object', 'SubObject', 'Point', 'ExtObject'), -1)
    if target is None:
        return values
    if target.kind in ('Pad', 'Hole'):
        values.update(Object=target.parent.parent.parent._ordinal(), SubObject=target._ordinal())
    elif target.kind == 'Component':
        values['ExtObject'] = target._ordinal()
    elif target.kind in ('Trace', 'Point'):
        trace = target if target.kind == 'Trace' else target.parent.parent
        values.update(Object=trace.parent.parent._ordinal(), SubObject=trace._ordinal(),
                      Point=target._ordinal() if target.kind == 'Point' else -1)
    elif target.kind == 'Shape':
        values['Object'] = target._ordinal()
    elif target.kind == 'CopperPour':
        values['Object'] = target._ordinal()
    elif target.kind == 'Teardrop':
        values.update(Object=target.parent.parent._ordinal(), SubObject=target._ordinal())
    elif target.kind == 'CenterPoint':
        values.update(Object=target.parent.parent.parent.parent._ordinal(),
                      SubObject=target.parent.parent._ordinal(), Point=target._ordinal())
    elif target.schema is length_matching.CONNECTION:
        values['Object'], values['SubObject'] = length_matching.connection_position(target)
    elif target.kind == 'pt':
        values['Point'] = target._ordinal()
    return values


def _object_fields(side, role):
    missing = 'UnresolvedTarget'+side
    names = ('Object', 'SubObject', 'Point', 'ExtObject')
    dependencies = _dependencies(role, missing, names)
    missing_collections = dependencies['collection_dependencies']
    missing_values = dependencies['value_dependencies']
    def selected(row):
        return _selected(row, role, missing)
    def selector(row, name):
        unavailable = row.child(missing)
        return unavailable[name] if unavailable is not None else _selectors(selected(row))[name]
    def ordinals(row):
        node = selected(row) if row.child(missing) is None else None
        result = []
        while node is not None and node.kind != 'Board':
            result.append(node)
            node = node.parent
        return tuple(result)
    def policy_collections(row):
        result = missing_collections(row)
        target = selected(row) if row.child(missing) is None else None
        if target is not None and target.schema is length_matching.CONNECTION:
            board = row._owner().one('/Board')
            result += ((board, 'NetClasses'), (board, 'LengthRules'))
            result += tuple((collection, name) for kind, name in
                (('NetClasses', 'NetClass'), ('LengthRules', 'LengthRule'))
                if (collection := board.child(kind)) is not None)
            result += tuple((net_class, 'CheckLength')
                            for net_class in board.select('NetClasses/NetClass'))
        return result
    def policy_values(row):
        result = missing_values(row)
        target = selected(row) if row.child(missing) is None else None
        if target is not None and target.schema is length_matching.CONNECTION:
            result += tuple((net_class, 'CheckLength')
                            for net_class in row._owner().select('/Board/NetClasses/NetClass')
                            if net_class.child('CheckLength') is not None)
        return result
    dependencies.update(collection_dependencies=policy_collections, value_dependencies=policy_values)
    return {
        'Target'+side: Field('Target'+side, 'reference', nullable=True, getter=selected,
            setter=lambda row, target: _set_selected(row, role, missing, target), **dependencies),
        **{name+side: Field(name+side, 'integer', getter=lambda row, name=name: selector(row, name),
             ordinal_dependencies=ordinals, **dependencies) for name in names},
    }


UNRESOLVED = Record('PcbUnresolvedCheckTarget',
    {name: Field(name, 'integer') for name in ('Object', 'SubObject', 'Point', 'ExtObject')},
    parameters=('Object', 'SubObject', 'Point', 'ExtObject'))
ERROR = Record('PcbDesignError', {
    'Id': Field('Id', 'integer', getter=lambda row: row._ordinal(), ordinal_dependencies=lambda row: (row,)),
    'Enabled': Field('Enabled', 'boolean', default=True),
    **{name: Field(name, 'number', default=0, unit='shared length') for name in ('X', 'Y', 'Value', 'Rule')},
    'Type': Field('Type', 'integer', default=0),
    'RuleType': Field('RuleType', 'integer', default=-1),
    **{'ObjectType'+side: Field('ObjectType'+side, 'integer', default=-1) for side in ('1', '2')},
    **{name: field for side, role in zip(('1', '2'), OBJECT_ROLES) for name, field in _object_fields(side, role).items()},
    **{name: field for side, role in zip(('1', '2'), CLASS_ROLES)
       for name, field in optional_reference_fields('NetClass'+side, 'ObjectNetClass'+side, role).items()},
    **optional_reference_fields('RuleLayer', 'RuleLay', 'drc-rule-layer'),
}, children={'Layers': Child('Layers', 'PcbErrorLayers'),
             **{'UnresolvedTarget'+side: Child('UnresolvedTarget'+side, UNRESOLVED.name) for side in ('1', '2')}})
LAYER = Record('PcbErrorLayer', optional_reference_fields('Layer', 'Index', 'drc-layer'))
LAYERS = Record('PcbErrorLayers', {}, children={'Layer': Child('Layer', LAYER.name, maximum=None)})
ERRORS = Record('PcbDesignErrors', {}, children={'DesignError': Child('DesignError', ERROR.name, maximum=None)})


def definition(node):
    parent = node.parent
    if parent is None:
        return None
    if node.kind == 'DesignErrors' and parent.kind == 'Board':
        return ERRORS
    if node.kind == 'DesignError' and parent.kind == 'DesignErrors':
        return ERROR
    if parent.schema is ERROR:
        if node.kind in ('UnresolvedTarget1', 'UnresolvedTarget2'):
            return UNRESOLVED
        if node.kind == 'Layers':
            return LAYERS
    if node.kind == 'Layer' and parent.schema is LAYERS:
        return LAYER
    return None


def _matches(document, row, side, target):
    board, parent, mode = document.one('/Board'), target.parent, row['ObjectType'+side]
    if parent is None:
        return False
    if mode in PAD_TYPES or mode in HOLE_TYPES:
        pattern = parent.parent
        component = pattern.parent if pattern is not None else None
        kind = 'Pad' if mode in PAD_TYPES else 'Hole'
        collection = {'Pad': 'Pads', 'Hole': 'Holes'}[kind]
        return (target.kind == kind and pattern is not None and pattern.kind == 'Pattern'
                and parent is pattern.child(collection) and component is not None
                and component.parent is board.child('Components') and component['Enabled'])
    if mode in TRACE_TYPES:
        trace = target if target.kind == 'Trace' else parent.parent
        if trace is None or trace.kind != 'Trace':
            return False
        net = trace.parent.parent if trace is not None and trace.parent is not None else None
        selected = target is trace or target.kind == 'Point' and parent is trace.child('Points')
        return (trace is not None and trace.kind == 'Trace' and selected and net is not None
                and net.parent is board.child('Nets') and net['Enabled'])
    if mode in SHAPE_TYPES:
        return ((target.kind == 'Shape' and parent is board.child('Shapes') or
                 target.kind == 'Component' and parent is board.child('Components')) and target['Enabled'])
    if mode == 7:
        return target.kind == 'CopperPour' and parent is board.child('CopperPours') and target['Enabled']
    if mode == 1:
        return target is board or target.kind == 'pt' and parent is board.child('Points')
    if mode == 21:
        net = parent.parent
        return (target.kind == 'Teardrop' and net is not None and net.kind == 'Net'
                and parent is net.child('Teardrops') and net.parent is board.child('Nets') and net['Enabled'])
    if mode == 17:
        segment = parent.parent
        pair = segment.parent.parent if segment is not None and segment.parent is not None else None
        return (target.kind == 'CenterPoint' and segment is not None and segment.kind == 'Segment'
                and parent is segment.child('CenterPoints') and pair is not None
                and pair.kind == 'DifferentialPair' and segment.parent is pair.child('Segments')
                and pair.parent is board.child('DifferentialPairs') and pair['Enabled'])
    if mode == 18 and target.schema is length_matching.CONNECTION:
        owner = parent.parent
        return (owner is not None and parent is owner.child('Rules') and
                (owner.kind == 'LengthRule' and owner.parent is board.child('LengthRules') or
                 owner.kind == 'LengthResults' and owner.parent is not None and
                 owner.parent.parent is board.child('NetClasses') and owner.parent.get('CheckLength', False)))
    return False


def validate_reference(document, reference, target):
    role, source = reference.role, reference.source
    if role not in (*OBJECT_ROLES, *CLASS_ROLES, 'drc-rule-layer', 'drc-layer'):
        return
    board = document.one('/Board')
    if role == 'drc-layer':
        error = source.parent.parent if source.parent is not None else None
        valid = (source.schema is LAYER and error is not None and error.schema is ERROR
                 and error.parent is board.child('DesignErrors') and target.parent is board.child('Layers'))
    else:
        valid = source.schema is ERROR and source.parent is board.child('DesignErrors')
        if role in OBJECT_ROLES:
            valid = valid and _matches(document, source, role[-1], target)
        else:
            collection = 'NetClasses' if role in CLASS_ROLES else 'Layers'
            valid = valid and target.parent is board.child(collection)
    if not valid or target._owner() is not document:
        raise ReferenceError('design-check result requires a compatible target in its own PCB')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=role)):
        raise ReferenceError('design-check selector already has a target')
    if role == 'drc-layer' and any(link.source is not source for link in
            document.references.incoming(target, role=role) if link.source.parent is source.parent):
        raise ReferenceError('design-check layer is already included')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate_field(document, node, name):
    if node.schema is ERROR and name in ('ObjectType1', 'ObjectType2'):
        validate_references(document, document.references.outgoing(node))
    elif name in ('Enabled', 'Type', 'CheckLength'):
        validate_references(document, document.references._content_references(node.walk(include_self=True)))


def validate_move(document, node, parent):
    if node.schema is ERRORS:
        valid = parent is document.one('/Board')
    elif node.schema is ERROR:
        valid = parent is document.one('/Board').child('DesignErrors')
    elif node.schema is LAYERS:
        valid = parent.schema is ERROR
    elif node.schema is LAYER:
        valid = parent.schema is LAYERS
    elif node.schema is UNRESOLVED:
        valid = parent.schema is ERROR and node.kind in ('UnresolvedTarget1', 'UnresolvedTarget2')
    else:
        return
    if not valid:
        raise ReferenceError('design-check data must remain in its result collection')


def requires_attachment(parent, node):
    return (node.schema in (ERRORS, ERROR, LAYERS, LAYER, UNRESOLVED) or
            (parent.kind, node.kind) in (('Board', 'DesignErrors'), ('DesignErrors', 'DesignError')) or
            parent.schema is ERROR and node.kind in ('Layers', 'UnresolvedTarget1', 'UnresolvedTarget2') or
            parent.schema is LAYERS and node.kind == 'Layer')


def prepare_attachment(node):
    for child in node.walk(include_self=True):
        if (schema := definition(child)) is not None:
            child.bind_schema(schema)
