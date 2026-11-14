"""Ownership and anchor constraints for PCB dimension attachments."""
from ...common.references import ReferenceError
from ...common.dimension_refs import matches_local_attachment as _matches


LOCAL_ROLES = ('pattern-dimension-1', 'pattern-dimension-2')
BOARD_ROLES = ('board-dimension-1', 'board-dimension-2')
BOARD_VERTEX_TYPES = (0, 1, 8, 9)


def _owner(source):
    return source.parent.parent if source.parent is not None else None


def validate_reference(document, reference, target):
    if reference.role not in (*LOCAL_ROLES, *BOARD_ROLES):
        return
    source, side = reference.source, reference.role[-1]
    pattern = _owner(source)
    if reference.role in BOARD_ROLES:
        board = document.one('/Board')
        mode = source['Connected'+side]
        if mode == 7:
            compatible = (target.kind == 'Component' and target.parent is board.child('Components')
                          and target['Enabled'])
        elif mode == 6:
            compatible = board.get('Enabled', True) and target.kind == 'pt' and target.parent is board.child('Points')
        elif mode == 3:
            points = target.parent
            trace = points.parent if points is not None else None
            traces = trace.parent if trace is not None else None
            net = traces.parent if traces is not None else None
            compatible = (target.kind == 'Point' and net is not None and net.kind == 'Net'
                and points is trace.child('Points') and trace.kind == 'Trace'
                and traces is net.child('Traces') and net.parent is board.child('Nets')
                and net['Enabled'] and (source['Type'] != 3 or 0 < target._ordinal() < len(points.children('Point'))-1))
        elif mode == 4:
            points = target.parent
            pour = points.parent if points is not None else None
            compatible = (target.kind == 'pt' and pour is not None and pour.kind == 'CopperPour'
                and points is pour.child('Points')
                and pour.parent is board.child('CopperPours') and pour['Enabled'])
        elif mode == 5:
            shape = target if target.kind == 'Shape' else target.parent.parent if target.parent is not None else None
            compatible = (shape is not None and shape.kind == 'Shape' and shape.parent is board.child('Shapes')
                and shape['Enabled'] and ((target.kind == 'pt' and target.parent in (
                    shape.child('Points'), shape.child('Points_New')))
                    if shape['Type'] in BOARD_VERTEX_TYPES else target is shape))
        else:
            current = target
            while current is not None and current.kind != 'Pattern':
                current = current.parent
            component = current.parent if current is not None else None
            matches = current is not None and _matches(current, mode, source['Point'+side], target)
            if mode == 0 and source['Point'+side] >= 10:
                pad = target.parent.parent if target.parent is not None else None
                matches = (current is not None and pad is not None and target.kind == 'pt'
                    and target.parent.kind == 'PadPoints_New' and pad.kind == 'Pad'
                    and pad.parent is current.child('Pads') and pad['PadShape_New'] == 3)
            compatible = (component is not None and component.kind == 'Component'
                and component.parent is board.child('Components') and component['Enabled']
                and matches)
        if (source.kind != 'Dimension' or pattern is not board
                or source.parent is not board.child('Dimensions') or not source['Enabled']
                or target._owner() is not document or not compatible):
            raise ReferenceError('board dimension requires a compatible target in its own board')
        if any(link.uid != reference.uid for link in document.references.outgoing(source, role=reference.role)):
            raise ReferenceError('dimension endpoint already has an attachment')
        return
    if (source.kind != 'Dimension' or pattern is None or pattern.kind != 'Pattern'
            or source.parent is not pattern.child('Dimensions') or not source['Enabled']
            or target._owner() is not document
            or not _matches(pattern, source['Connected'+side], source['Point'+side], target)):
        raise ReferenceError('dimension attachment requires a compatible target in its own footprint')
    if any(link.uid != reference.uid for link in document.references.outgoing(source, role=reference.role)):
        raise ReferenceError('dimension endpoint already has an attachment')


def validate_references(document, references):
    for reference in references:
        validate_reference(document, reference, reference.target)


def validate_field(document, node, name):
    if node.kind == 'Board' and name == 'Enabled':
        outline = node.child('Points')
        if outline is not None:
            validate_references(document, document.references._content_references(outline.walk(include_self=True)))
        return
    if ((node.kind in ('Shape', 'PadTerminal', 'Hole', 'Component', 'CopperPour', 'Net') and name in ('Type', 'Enabled'))
            or node.kind == 'Pad' and name == 'PadShape_New'
            or node.kind == 'Dimension' and name in ('Type', 'Enabled', 'Connected1', 'Connected2', 'Point1', 'Point2')):
        validate_references(document, document.references._content_references(node.walk(include_self=True)))
