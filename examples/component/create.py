"""Build a logical component with explicit symbol-pin and physical-pad links."""
import argparse

from lib import write
from lib.component import new_library, new_component, new_pattern, new_pad, new_pin


def build():
    library = new_library('Example components')
    component = library.one('/Library/Components').append(new_component('Two terminals', 'J'))
    component['Manufacturer'] = 'Example Devices'
    pattern = component.append(new_pattern('Two pads'))
    part = component.one('Parts/Part')
    # Physical geometry and symbol geometry are independent definitions.
    for number, x, label in (('1', -3, 'SIGNAL'), ('2', 3, 'RETURN')):
        pad = pattern.one('Pads').append(new_pad(number, x=x))
        pad['SurfacePad'] = True
        pad['PadShape_New'] = 2
        pad['PadWidth_New'], pad['PadHeight_New'] = 1.8, 2.4
        pin = part.one('Pins').append(new_pin())
        pin['X'], pin['Name'], pin['StringNumber'] = x * 3, label, number
        pin['Orientation'] = 0 if x < 0 else 2
        pin['Pad'] = pad  # Select by identity; reordering pads keeps this link.
    library.validate()
    return library


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', help='Output .eli, .asc or .elixml file')
    args = parser.parse_args()
    write(build(), args.output)
