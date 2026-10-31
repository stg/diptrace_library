"""Inspect and edit PCB data while the model maintains references."""
import argparse

from lib.pcb import new_net, new_user_field, read, write


def edit(design):
    for part in design.select('/Board/Components/Component', where=lambda part: part['X'] >= 0):
        print(part['RefDes'], part.get('Value', ''))
        for pad in part.select('Pattern/Pads/Pad'):
            net = pad['Net']
            print(' ', pad['StringNumber'], net['Name'] if net is not None else '(unassigned)')

    connector = design.one('/Board/Components/Component[RefDes="J1"]')
    connector['RefDes'] = design.refdes('J').first_free()
    connector['Value'] = 'Edited input'
    connector.one('UserFields').append(new_user_field('Assembly', 'Fit'))

    pad = connector.one('Pattern/Pads/Pad[1]')
    signal = pad['Net']
    signal['Name'] = 'INPUT'
    nets = design.one('/Board/Nets')
    nets.append(new_net('UNUSED'))
    signal.move_to(nets, 1)
    # Pads and trace endpoints still reference the same objects. Serialized
    # selectors follow the new order without a rebuild or manual renumbering.
    assert pad['Net'] is signal
    assert signal.one('Traces/Trace')['Target1'] is pad
    design.validate()
    return design


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='A file produced by examples.pcb.create')
    parser.add_argument('output')
    args = parser.parse_args()
    write(edit(read(args.input)), args.output)
