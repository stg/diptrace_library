"""Convert PCB files, optionally selecting units and an output revision."""
import argparse

from lib import ConversionReport
from lib.pcb import ExportContext, read, write


def convert(source, target, *, version=None, units=None):
    report = ConversionReport()
    design = read(source, report=report, label='load')
    write(design, target, version=version, context=ExportContext(units=units),
          report=report, label='save')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('output')
    parser.add_argument('--version', type=int, help='Explicit output schema; omitted selects the adapter default')
    parser.add_argument('--units', choices=('mm', 'mil', 'inch'))
    args = parser.parse_args()
    report = convert(args.input, args.output, version=args.version, units=args.units)
    for notice in (*report.warnings, *report.errors):
        print(f'{notice.severity}: {notice.message}')
