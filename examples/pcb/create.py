"""Create component, pad, net and explicit trace data without a template file."""
import argparse
from decimal import Decimal

from lib.pcb import new_document, new_component, new_pad, new_net, new_point, new_trace, write


def build():
    design = new_document()
    board = design.one('/Board')
    connector = board.one('Components').append(new_component('Connector', 'J1'))
    connector['Value'] = 'Signal input'
    connector['X'], connector['Y'] = 30, 60
    pads = []
    for number, x in (('1', -3), ('2', 3)):
        pad = connector.one('Pattern/Pads').append(new_pad(number, x=x))
        pad['SurfacePad'] = True
        pad['PadWidth_New'], pad['PadHeight_New'] = 3, 3  # One millimetre.
        pads.append(pad)

    signal = board.one('Nets').append(new_net('SIGNAL'))
    for pad in pads:
        pad['Net'] = signal

    # Trace coordinates are supplied explicitly in board space. The library
    # stores this geometry; it does not choose a route between the pads.
    trace = signal.one('Traces').append(new_trace())
    top = board.one('Layers/Layer[1]')
    for x in (27, 33):
        point = trace.one('Points').append(new_point(x=x, y=60, width=Decimal('.6')))
        point['Layer'] = top
    trace['Target1'], trace['Target2'] = pads
    design.validate()
    return design


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', help='Output .dip, .asc or .dipxml file')
    args = parser.parse_args()
    write(build(), args.output)
