"""Saved PCB check measurements and current target identities in XML."""
from ....common.conversion import warn
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import enum_text, field, numeric, point_attributes
from ...model import drc_results as model
from ..errors import PcbError
from ..output_validation import check_tree, field_value
from ..result_targets import target, net_class, layer_mask
from .drc_results import ERROR_TYPES, OBJECT_TYPES, RULE_TYPES


def _physical_member(row, side, kind, data, *, board, keys):
    if kind not in (*model.PAD_TYPES, *model.HOLE_TYPES):
        return
    if row.child('UnresolvedTarget'+side) is None:
        member = row['Target'+side]
        if member is None:
            return
    else:
        owner, index = data['Object'], data['SubObject']
        if owner < 0 or index < 0:
            return
        components = board.select('Components/Component')
        if owner >= len(components):
            raise PcbError(f'{row.path}: unresolved physical check owner needs an XML mapping')
        members = components[owner].select('Pattern/'+('Pads/Pad' if kind in model.PAD_TYPES else 'Holes/Hole'))
        if index >= len(members):
            raise PcbError(f'{row.path}: unresolved physical check member needs an XML mapping')
        member = members[index]
    data['Object'], data['SubObject'] = (keys.pad if kind in model.PAD_TYPES else keys.hole)(member)


def project_results(board, *, keys, units, report=None):
    result = Element('DesignErrors')
    for source in board.select('DesignErrors/DesignError'):
        check_tree(source, model.ERROR, destination='DIPXML')
        if not field_value(source, 'Enabled'):
            raise PcbError(f'{source.path}: inactive check result needs output normalization')
        row = result.add('DesignError')
        point_attributes(row, field_value(source, 'X'), field_value(source, 'Y'), units)
        kind = field_value(source, 'Type')
        # Distinct values sharing a display label require the numeric spelling.
        label = enum_text(kind, ERROR_TYPES)
        set_attribute(row, 'Type', str(kind) if label in ERROR_TYPES[:kind] else label)
        set_attribute(row, 'RuleType', enum_text(field_value(source, 'RuleType'), RULE_TYPES))
        for name in ('Value', 'Rule'):
            set_attribute(row, name, numeric(units.length(field_value(source, name))))
        set_attribute(row, 'RuleLay', source['RuleLay'])
        if source.child('UnresolvedRuleLay') is not None:
            warn(report, 'unresolved-design-error-layer', 'dipxml', 'Saved check rule layer is unavailable', (source,))
        for side in ('1', '2'):
            kind, data = target(source, side, indices=keys.indices, destination='dipxml', report=report)
            _physical_member(source, side, kind, data, board=board, keys=keys)
            set_attribute(row, 'ObjectType'+side, enum_text(kind, OBJECT_TYPES))
            for name, value in data.items():
                set_attribute(row, name+side, value)
            set_attribute(row, 'ObjectNetClass'+side,
                          net_class(source, side, indices=keys.indices, destination='dipxml', report=report))
        mask = row.add('Lays')
        for enabled in layer_mask(source, copper=board.select('Layers/Layer'), destination='dipxml', report=report):
            field(mask, 'Item', enabled)
    return result
