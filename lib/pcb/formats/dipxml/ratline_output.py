"""Supplied PCB connection guides with current physical pad references."""
from ....common.conversion import info
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import point_attributes
from ...model import ratlines
from ..errors import PcbError
from ..output_validation import check_tree, field_value


def project_ratlines(board, *, keys, units, report=None):
    result = Element('Ratlines')
    if (source := board.child('Ratlines')) is None:
        return result
    check_tree(source, ratlines.RATLINES, destination='DIPXML')
    for guide in source.children('Ratline'):
        if not field_value(guide, 'Enabled'):
            info(report, 'inactive-ratline', 'dipxml', 'Omitted an inactive connection guide', (guide,))
            continue
        row = result.add('Ratline')
        set_attribute(row, 'Id', guide['Id'])
        set_attribute(row, 'Hidden', field_value(guide, 'Hidden'))
        for end in ('1', '2'):
            point_attributes(row, field_value(guide, 'X'+end), field_value(guide, 'Y'+end),
                             units, names=('X'+end, 'Y'+end))
            component, pad = keys.pad(guide['Pad'+end])
            if pad == 0:
                raise PcbError(f'{guide.path}: a connection guide requires a positive XML pad key')
            set_attribute(row, 'Comp'+end, component)
            set_attribute(row, 'Pad'+end, pad)
    return result
