"""Inspect and edit the example design, including identity-based relationships."""
import argparse

from lib import new_net, new_pin, read, write


def edit(design):
    parts = design.select('/Schematic/Components/Part')
    for part in parts:
        print(part['RefDes'], part.get('Value', ''), len(part.child('Pins').children('Pin')))
    for part in design.select('/Schematic/Components/Part[Value="Signal input"]'):
        part['Value'] = 'Edited input'
    part = design.one('/Schematic/Components/Part[RefDes="J1"]')
    field = part.child('UserFields').add('UserField')
    field['Name'], field['Value'] = 'Assembly', 'Fit'

    nets = design.one('/Schematic/Nets')
    alternate = nets.append(new_net('ALTERNATE'))
    pin = part.one('Pins/Pin')
    pin['Net'] = alternate
    member = design.references.incoming(pin, role='net-member')[0]
    replacement = part.child('Pins').append(new_pin())
    replacement['Number'], replacement['StringNumber'] = 2, '2'
    design.references.retarget(member, replacement)
    alternate.move_to(nets, 0)  # Membership still names this same net.

    # Copy owned links and geometry; incoming users still refer to the original.
    drawing = design.copy(design.one('/Schematic/Shapes/Shape'))
    drawing.one('Points_New/pt[1]')['Y'] = 18
    design.validate()
    return design


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='A file produced by examples.schematic.create')
    parser.add_argument('output')
    args = parser.parse_args()
    write(edit(read(args.input)), args.output)
