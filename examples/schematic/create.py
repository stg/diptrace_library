"""Create component, pin, net and drawing data without a template file."""
import argparse

from lib import (new_schematic, new_symbol, new_pin, new_net,
                        new_schematic_shape, write)


def build():
    design = new_schematic(sheet_name='Example')
    part = design.one('/Schematic/Components').append(new_symbol('Connector', 'J1'))
    part['Value'] = 'Signal input'
    part['Width'], part['Height'] = 12, 9
    pin = part.child('Pins').append(new_pin())
    pin['Number'], pin['StringNumber'] = 1, '1'
    net = design.one('/Schematic/Nets').append(new_net('SIGNAL'))
    pin['Net'] = net

    drawing = design.one('/Schematic/Shapes').append(new_schematic_shape())
    drawing['Type'] = 1  # Line. Lengths are three units per millimetre.
    for x, y in ((0, 15), (30, 15)):
        point = drawing.child('Points_New').add('pt')
        point['X'], point['Y'] = x, y
    design.validate()
    return design


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', help='Output .dch, .asc or .dchxml file')
    args = parser.parse_args()
    write(build(), args.output)
