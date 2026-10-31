"""Authored copper-pour XML; calculated fill is omitted on the export view."""
from ....common.conversion import info
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import enum_text, numeric, point_attributes
from ...model import graphic_records
from ..errors import PcbError
from ..output_validation import check_tree, field_value
from .pours import TYPES, SPOKES, RATLINES


def project_pours(board, *, units, report=None):
    result = Element('CopperPours')
    for source in board.select('CopperPours/CopperPour'):
        check_tree(source, graphic_records.POUR, destination='DIPXML')
        if not field_value(source, 'Enabled'):
            raise PcbError(f'{source.path}: inactive copper pour needs output normalization')
        if source['Layer'] is None:
            raise PcbError(f'{source.path}: select a copper layer before export')
        area = field_value(source, 'MinimumArea')
        if area < 0:
            raise PcbError(f'{source.path}: minimum copper area must not be negative')
        target = result.add('CopperPour')
        for name, value in (('Id', source['Id']), ('Lay', source['Lay']),
                            ('NetId', source['NetNumber']), ('Priority', field_value(source, 'Priority'))):
            set_attribute(target, name, value)
        if source['GroupId'] >= 0:
            set_attribute(target, 'Group', source['GroupId'])
        for name, labels in (('Type', TYPES), ('Spoke', SPOKES), ('SMD_Spoke', SPOKES), ('RatlineMode', RATLINES)):
            set_attribute(target, name, enum_text(field_value(source, name), labels))
        for name, definition in graphic_records.POUR.fields.items():
            if definition.kind == 'boolean' and name != 'Enabled':
                set_attribute(target, name, field_value(source, name))
            elif definition.unit == 'shared length':
                set_attribute(target, name, numeric(units.length(field_value(source, name))))
        set_attribute(target, 'MinimumArea', numeric(units.area(area)))
        for name in ('ShieldGroup', 'TraceShieldGroup'):
            if field_value(source, name) >= 0:
                set_attribute(target, name, field_value(source, name))
        points = target.add('Points')
        for point in source.select('Points/pt'):
            point_attributes(points.add('Point'), point['X'], point['Y'], units)
        if (fill := source.child('Fill')) is not None:
            info(report, 'pour-fill-recalculation', 'dipxml', 'XML omits calculated copper-pour fill', (fill,),
                 recoverability='pour geometry and settings remain; a receiving editor can calculate fill')
    return result
