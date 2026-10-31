"""Compose a detached PCB ASC document from current model data."""
from ....common.asc_text import project_text
from ....common.conversion import info
from ....common.model import Document, Value
from ...model.definitions import BOARD, DOCUMENT
from ..capabilities import ASC
from ..errors import PcbError
from ..output_indices import OutputIndices
from .cache_projection import project_cache
from .component_projection import project_components
from .dimension_projection import project_dimensions
from .document_projection import project_document_settings
from .global_projection import project_globals
from .graphic_projection import project_graphics
from .net_projection import project_nets
from .pair_projection import project_pairs
from .projection import check, value
from .ratline_projection import project_ratlines
from .result_projection import project_results
from .rule_projection import project_rules
from .table_projection import project_tables


def _merge(target, section):
    """Combine section-owned fields, requiring one owner for each output fact."""
    for child in tuple(section.children()):
        previous = target.child(child.kind)
        if previous is None:
            child.move_to(target)
        elif child.kind == 'Settings':
            _merge(previous, child)
        else:
            raise PcbError(f'{target.path}: duplicate ASC projection for {child.kind}')


def _component_header(node, index):
    return (node.kind == 'Component' and index < 2 and node.parent is not None
            and node.parent.kind == 'Components' and node.parent.parent is not None
            and node.parent.parent.kind == 'Board')


def _unquoted_text(node, index):
    if index == 1 and _component_header(node, index):
        return True
    return (index == 0 and node.kind == 'Name' and node.parent is not None
            and node.parent.kind == 'Layers' and node.parent.parent is not None
            and node.parent.parent.kind == 'Board')


def project(document, *, report=None, legacy_picture_files=None, encoding='cp1252'):
    """Build the whole text tree without retained input syntax or companion I/O.

    The result is serialization data, separate from the editable source model.
    Supplied routing, fill and measurements are projected rather than calculated.
    Unsupported destination facts produce the individual section diagnostics.
    """
    check(document.root, DOCUMENT)
    board = document.one('/Board')
    check(board, BOARD)
    indices = OutputIndices(board)
    output = Document(representation='asc')
    output.root.add('Source', 'DipTrace-PCBN', ASC.default_write_version)
    output.root.add('Units', document.root['Units'])
    output.root.add('Scale', Value(value(document.root, 'Scale'), 'number', '%'))
    rounded = []
    for name in ('Xpos', 'Ypos'):
        current = value(document.root, name)
        output.root.add(name, round(current))
        if round(current) != current:
            rounded.append(document.root.one(name))
    if rounded:
        info(report, 'viewport-position', 'asc', 'ASC rounds the canvas position to whole units', rounded,
             recoverability='design coordinates are unchanged')
    target = output.root.add('Board')
    for section in (
            project_globals(board, report=report),
            project_graphics(board, report=report, legacy_picture_files=legacy_picture_files),
            project_document_settings(board, report=report),
            project_rules(board, indices=indices, report=report)):
        _merge(target, section)
    target.append(project_components(board, report=report))
    target.append(project_nets(board, indices=indices, report=report))
    target.append(project_pairs(board, indices=indices, report=report))
    if board.child('RemovedDifferentialPairs') is not None:
        target.append(project_pairs(board, indices=indices, report=report, removed=True))
    if (ratlines := board.child('Ratlines')) is not None:
        target.append(project_ratlines(ratlines))
    target.append(project_dimensions(board, report=report))
    target.append(project_tables(board, report=report))
    target.append(project_results(board, indices=indices, report=report))
    _merge(target, project_cache(board, report=report))
    project_text(output, encoding=encoding, report=report,
                 receiver_normalizes=_component_header, unquoted_text=_unquoted_text)
    return output
