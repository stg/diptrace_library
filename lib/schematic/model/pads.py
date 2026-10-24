"""Declared pad construction defaults."""
from ...common.model import (Element)


def empty_pad(index):
    """An explicit empty boundary slot, absent from placed-footprint ASC."""
    pad = Element('Pad', index, '', '', 0, 0)
    zero = '''Number_New PadAngle PadWidth_New PadHeight_New PadHole PadHoleH
PadHoleType PadShape_New PadCorner PadShape_X PadShape_Y'''.split()
    for name in zero:
        pad.add(name, 0)
    for name in ('SurfacePad', 'Standard', 'Locked', 'Sided'):
        pad.add(name, False)
    pad.add('Group', -1)
    pad.add('PadPoints_New')
    for name in ('DisableTopMask', 'DisableBottomMask', 'DisableTopPaste', 'DisableBottomPaste'):
        pad.add(name, 0)
    for name in ('CustomSwell_New', 'CustomShrink_New'):
        pad.add(name, -1000)
    for name, value in (('PadMask_Percent', 50), ('PadMask_EdgeGap', .9),
                        ('PadMask_SegmentGap', .6), ('PadMask_SegmentSide', 3)):
        pad.add(name, value)
    for name in ('PadMask_TopSegments', 'PadMask_BotSegments'):
        pad.add(name)
    pad.annotations.update(reserved=True, asc_omit='empty boundary pad',
                           generated_default='boundary pad omitted from ASC')
    from .definitions import PAD
    return pad.bind_schema(PAD)
