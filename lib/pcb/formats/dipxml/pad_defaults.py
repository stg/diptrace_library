"""Resolve omitted placement style declarations after XML side installation."""
from ..assembly.pad_defaults import matches_defaults
from ....common.conversion import warn


def infer_defaults(component, pads):
    """Infer only selected physical pads whose placement omitted DefStyle.

    The caller distinguishes omission from an explicit custom declaration while
    consuming XML. That syntax distinction is not retained in the editable model.
    Via construction uses independent pad defaults and does not call this helper.
    """
    pattern = component.one('Pattern')
    for pad in pads:
        if pad['PadShape_New'] != 20:
            mirrored = component['BottomSide'] != pad['Sided']
            pad.set_field('Standard', matches_defaults(pattern, pad, mirrored=mirrored))


def report_legacy_inference(board, *, report=None):
    """Report declarations an older XML destination cannot express explicitly."""
    changed = []
    for component in board.select('Components/Component'):
        pattern = component.one('Pattern')
        for pad in pattern.select('Pads/Pad'):
            if pattern['Type'] == 16:
                inherited = False
            elif pad['PadShape_New'] != 20:
                inherited = matches_defaults(pattern, pad,
                    mirrored=component['BottomSide'] != pad['Sided'])
            else:
                continue
            if inherited != pad['Standard']:
                changed.append(pad)
    if changed:
        warn(report, 'pad-style-inheritance', 'dipxml',
             'Destination infers ordinary pad inheritance and initializes via pads as custom', changed,
             recoverability='physical geometry remains; an independent Standard selection can change')
