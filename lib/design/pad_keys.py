"""Public pad keys remain distinct from positional footprint assignments."""
from .local_keys import reserved_keys, missing_key


def _key(value):
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('public pad keys must be nonnegative integers') from None
    if isinstance(value, bool) or result != value or result < 0:
        raise ValueError('public pad keys must be nonnegative integers')
    return result


def public_pad_keys(pattern, part=None):
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
    result, used = {}, set()
    for index, pad in enumerate(pads, 1):
        field = pad.child('Id')
        if field is not None:
            if len(field.arguments) != 1 or field.arguments[0].kind != 'number' or field.arguments[0].unit:
                raise ValueError(f'{field.path}: public pad key requires one nonnegative integer')
            key = _key(field.values[0])
            if key in used or key in reserved:
                raise ValueError('public pad key duplicates another key or an unresolved assignment')
            result[index] = key
            used.add(key)
    for index in range(1, len(pads)+1):
        if index not in result:
            key = index
            while key in used or key in reserved:
                key += 1
            result[index] = key
            used.add(key)
    return result


def project_pad_id(pin, keys):
    missing = missing_key(pin, 'PadId')
    if missing is not None:
        return missing.values[1]
    number = pin.scalar('Number')
    return keys.get(number, number) if keys is not None else number
