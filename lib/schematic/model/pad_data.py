"""Current pad mask modes and their redundant ASC compatibility spelling."""

MASK_FIELDS=('DisableTopMask','DisableBottomMask','DisableTopPaste','DisableBottomPaste')


def mask_state(pad,name):
    field=pad.one(name)
    if len(field.arguments)!=1:
        raise ValueError(f'{field.path}: expected one current mask state')
    value=field.arguments[0]
    if value.kind!='number' or value.unit or isinstance(value.value,bool):
        raise TypeError(f'{field.path}: mask state requires an unqualified integer')
    try:
        state=int(value.value)
    except (ValueError,OverflowError):
        raise ValueError(f'{field.path}: mask state requires a finite integer') from None
    if state!=value.value:
        raise ValueError(f'{field.path}: mask state requires an integer')
    return state


def compatibility_mask(state):
    return (True,2) if state==2 else (False,state if state<3 else 0,state)
