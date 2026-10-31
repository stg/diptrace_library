"""Supplied check snapshots with selectors generated from current identities."""
from ....common.conversion import warn
from ....common.model import Element
from ...model import drc_results as model, rule_records
from ..output_indices import OutputIndices
from .projection import check, collection, fields, flag
from ..result_targets import target, net_class, layer_mask
from ..result_types import object_type_to_file


def project_results(board, *, indices=None, report=None):
    """Preserve measurements and references without rerunning any design check."""
    indices = indices or OutputIndices(board)
    copper = board.select('Layers/Layer')
    output = Element('DesignErrors')
    if (last := board.child('LastDRC')) is not None:
        check(last, rule_records.DRC)
        warn(report, 'last-design-rules', 'asc', 'ASC omits the last-used design-rule snapshot', (last,),
             recoverability='current rules and supplied check results remain; the independent previous-rule snapshot is omitted')
    for row in collection(board, 'DesignErrors', model.ERRORS, model.ERROR):
        record = output.add('DesignError')
        fields(row, record, exclude=('ObjectType1', 'ObjectType2', 'UnresolvedRuleLay',
                                    'UnresolvedObjectNetClass1', 'UnresolvedObjectNetClass2'))
        for side in ('1', '2'):
            kind, data = target(row, side, indices=indices, destination='asc', report=report,
                                footprint_boundaries=True)
            record.add('ObjectType'+side, object_type_to_file(kind))
            for name, current in data.items():
                record.add(name+side, current)
            record.add('ObjectNetClass'+side, net_class(row, side, indices=indices, destination='asc', report=report))
        record.add('RuleLayer', row['RuleLay'])
        if row.child('UnresolvedRuleLay') is not None:
            warn(report, 'unresolved-design-error-layer', 'asc', 'Saved check rule layer is unavailable', (row,),
                 recoverability='the explicit unresolved layer index is retained')
        flags = layer_mask(row, copper=copper, destination='asc', report=report)
        mask = record.add('Layers', len(flags))
        for enabled in flags:
            mask.add('pt', flag(enabled))
    return output
