"""Current physical pad mask/paste choices, independent of serialization."""

MASK_FIELDS = ('DisableTopMask', 'DisableBottomMask', 'DisableTopPaste', 'DisableBottomPaste')
MASK_DATA_FIELDS = (*MASK_FIELDS, 'CustomSwell_New', 'CustomShrink_New',
                    'PadMask_Percent', 'PadMask_EdgeGap', 'PadMask_SegmentGap', 'PadMask_SegmentSide')
MASK_COLLECTIONS = ('PadMask_TopSegments', 'PadMask_BotSegments')


def mask_state(pad, name):
    field = pad.one(name)
    if len(field.arguments) != 1:
        raise ValueError(f'{field.path}: expected one current mask state')
    value = field.arguments[0]
    if value.kind != 'number' or value.unit or isinstance(value.value, bool):
        raise TypeError(f'{field.path}: mask state requires an unqualified integer')
    try:
        state = int(value.value)
    except (ValueError, OverflowError):
        raise ValueError(f'{field.path}: mask state requires a finite integer') from None
    if state != value.value:
        raise ValueError(f'{field.path}: mask state requires an integer')
    return state
