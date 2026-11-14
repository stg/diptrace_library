"""Build an editable footprint library without a template file."""
import argparse

from lib import write
from lib.pattern import new_library, new_pattern, new_pad


def build():
    library = new_library('Example footprints')
    pattern = library.one('/Library/Patterns').append(new_pattern('Two pads'))
    # Shared lengths are three units per millimetre: these centres are 1 mm apart.
    for number, x in (('1', -1.5), ('2', 1.5)):
        pad = pattern.one('Pads').append(new_pad(number, x=x))
        pad['SurfacePad'] = True
        pad['PadShape_New'] = 2  # Rectangle.
        pad['PadWidth_New'], pad['PadHeight_New'] = 1.8, 2.4
    library.validate()
    return library


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', help='Output .lib, .asc or .libxml file')
    args = parser.parse_args()
    write(build(), args.output)
