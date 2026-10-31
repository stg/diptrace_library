"""Keep unavailable symbol-pad assignments from selecting unrelated output pads."""
from ...common.conversion import warn


def number(pin, *, destination, report=None):
    value = pin['Number']
    document = pin._owner()
    field = pin.child('Number')
    if document is None or field is None or not document.references.unresolved_slot(field):
        return value
    part = pin.parent.parent
    definitions = part.parent.parent.children('Definition')
    primary = definitions[0].child('Pattern') if definitions else None
    count = len(primary.select('Pads/Pad')) if primary is not None else 0
    # Positional outputs must not turn an unavailable saved key into a current
    # assignment. XML readers normalize missing public pin-pad keys to unassigned.
    result = -1 if destination == 'dipxml' or 1 <= value <= count else value
    warn(report, 'unresolved-cached-pin', destination,
         'Cached symbol pin assignment is unavailable', (pin,),
         recoverability=('the explicit unresolved pad selector remains' if result == value else
                         'the pin is unassigned; symbol text and geometry remain'))
    return result
