"""Supplied design-check results with selectors derived from current identities."""
from ....common.conversion import warn
from ...model import drc_results
from ..output_indices import OutputIndices
from ..output_validation import check_tree
from ..result_targets import target, net_class, layer_mask
from ..result_types import object_type_to_file


def _rows(board):
    if (source := board.child('DesignErrors')) is not None:
        check_tree(source, drc_results.ERRORS, destination='DIP')
    return board.select('DesignErrors/DesignError')


def write_initial_results(writer, board, *, indices=None):
    """Write measurements and base targets; this never reruns a design check."""
    indices = indices or OutputIndices(board)
    drc = board.one('DRC')
    writer.field(drc, 'RealTimeMode', 'integer')
    writer.field(drc, 'DRCDone', 'boolean')
    rows = _rows(board)
    writer.integer(len(rows))
    for row in rows:
        writer.field(row, 'Enabled', 'boolean')
        writer.fields(row, 'number', 'X Y Value Rule')
        writer.field(row, 'Type', 'integer')
        targets = []
        for side in ('1', '2'):
            kind, data = target(row, side, indices=indices, destination='dip', report=writer.report,
                                footprint_boundaries=True)
            writer.integer(object_type_to_file(kind))
            targets.append(data)
        for data in targets:
            for name in ('Object', 'SubObject', 'Point'):
                writer.integer(data[name])
        for data in targets:
            writer.integer(data['ExtObject'])
        flags = layer_mask(row, copper=board.select('Layers/Layer'), destination='dip', report=writer.report)
        writer.integer(len(flags))
        for flag in flags:
            writer.boolean(flag)


def write_result_qualifications(writer, board, *, indices=None):
    """Rule selectors arrive alongside the first differential-pair extension."""
    indices = indices or OutputIndices(board)
    for row in _rows(board):
        writer.fields(row, 'integer', 'RuleType RuleLay')
        if row.child('UnresolvedRuleLay') is not None:
            warn(writer.report, 'unresolved-design-error-layer', 'dip', 'Saved check rule layer is unavailable',
                 (row,), recoverability='the explicit unresolved layer index is retained')
        for side in ('1', '2'):
            writer.integer(net_class(row, side, indices=indices, destination='dip', report=writer.report))
