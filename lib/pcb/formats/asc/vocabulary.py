"""Shared ASC field spellings for the PCB reader and writer."""

PAD_FIELD_NAMES = {
    'Number': 'Number_New', 'Angle': 'PadAngle', 'PadWidth': 'PadWidth_New',
    'PadHeight': 'PadHeight_New', 'PadShape': 'PadShape_New', 'PadPoints': 'PadPoints_New',
    'CustomSwell': 'CustomSwell_New', 'CustomShrink': 'CustomShrink_New',
    'IntOwner': 'InternalConnection', 'TopMask_State': 'DisableTopMask',
    'BotMask_State': 'DisableBottomMask', 'TopPaste_State': 'DisableTopPaste',
    'BotPaste_State': 'DisableBottomPaste',
}
