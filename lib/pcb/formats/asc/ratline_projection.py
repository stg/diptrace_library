"""ASC connection guides projected from current geometry and placed-pad links."""
from ....common.model import Element
from ...model import ratlines as model
from ..output_indices import pad_number
from .projection import flag, rows, value


def project_ratlines(source):
    output = Element('Connections')
    for row in rows(source, model.RATLINES, model.RATLINE):
        output.add('Connection', flag(value(row, 'Enabled')),
                   *(value(row, name) for name in ('X1', 'Y1', 'X2', 'Y2')),
                   row['ComponentIndex1'], row['ComponentIndex2'],
                   pad_number(row['Pad1']), pad_number(row['Pad2']), flag(value(row, 'Hidden')))
    return output
