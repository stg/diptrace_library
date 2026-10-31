"""Electrical and layer-specific placed-pad XML over current identities."""
from decimal import Decimal

from ....common.xml import set_attribute
from ....common.xml_output import field, numeric
from ....common.xml_pad_output import project_mask_paste
from ....common.conversion import warn
from ...model.static_via import pad_geometry
from ...model.pad_records import TEARDROP
from ..output_validation import field_value


def project_options(pad, result, *, units, via=False, report=None):
    """Project pad overlays; static vias carry mask/paste on their placement."""
    set_attribute(result, 'DefStyle', field_value(pad, 'Standard'))
    if via:
        defaults = dict(StringNumber=str(pad._ordinal()+1), Name='', X=0, Y=0,
                        Locked=False, Sided=False, Group=-1, PadAngle=0)
        component = pad.parent.parent.parent
        if component['Via'] is None:
            defaults.update(pad_geometry(-1, Decimal('.5')))
        if (any(field_value(pad, name) != value for name, value in defaults.items()) or
                pad.select('PadPoints_New/pt') or pad.children('PadTerminal')):
            warn(report, 'xml-via-pad-data', 'dipxml',
                 'XML via initialization replaces independent template-pad data', (pad,),
                 recoverability='placed connectivity and mask/thermal options remain; pad labels and defaults regenerate')
        result.append(project_mask_paste(pad, units=units, complete=True))
    set_attribute(result, 'SignalDelay', field_value(pad, 'SignalDelay'))
    if field_value(pad, 'ShieldGroup') >= 0:
        set_attribute(result, 'ShieldGroup', field_value(pad, 'ShieldGroup'))
    for own, public in (('HideLayer', 'HideRingLay'), ('BlindLayer', 'BlindLay')):
        members = pad.select(own+'/Item')
        if members:
            target = result.add(public)
            for member in members:
                field(target, 'Item', member['Lay'])
    if (source := pad.child('TeardropParams')) is not None:
        target = result.add('TeardropParams')
        for name in TEARDROP.fields:
            set_attribute(target, name, field_value(source, name))
    members = pad.select('CustomSpokes/CustomSpoke')
    if members:
        target = result.add('CustomSpokes')
        for source in members:
            row = target.add('CustomSpoke')
            for name in ('Lay', 'Type', 'Spoke'):
                set_attribute(row, name, source[name])
            set_attribute(row, 'Width', numeric(units.length(source['Width'])))
