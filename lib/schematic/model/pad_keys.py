"""Public pad keys remain distinct from positional footprint assignments."""
from .local_keys import reserved_keys, missing_key
from ...common.key_allocation import allocate_keys, _key


def public_pad_keys(pattern, part=None):
    if part is None and pattern.parent is not None:
        owner = pattern.parent
        part = owner if owner.kind == 'Part' else owner.child('Part') if owner.kind == 'Definition' else None
    pads = pattern.select('Pads/Pad')[1:-1]
    reserved = set()
    reserved.update(reserved_keys(pattern.select('Shapes/Shape'), ('PadId',)))
    reserved.update(reserved_keys(pattern.select('InternalConnections/IntCon'), ('X', 'Y')))
    for dimension in pattern.select('Dimensions/Dimension'):
        for side in ('1', '2'):
            if dimension.scalar('Connected'+side) == 0:
                field = missing_key(dimension, 'SubObject'+side)
                if field is not None:
                    reserved.add(_key(field.values[1]))
    if part is not None and part.scalar('PartType') == 0:
        for pin in part.select('Pins/Pin'):
            missing = missing_key(pin, 'PadId')
            number = missing.values[1] if missing is not None else pin.scalar('Number')
            if missing is not None or number >= 0 and not 1 <= number <= len(pads):
                reserved.add(_key(number))
    keys = allocate_keys(pads,reserved=reserved)
    return {index:keys[pad] for index,pad in enumerate(pads,1)}



def project_pad_id(pin, keys):
    missing = missing_key(pin, 'PadId')
    if missing is not None:
        return missing.values[1]
    number = pin.scalar('Number')
    return keys.get(number, number) if keys is not None else number
